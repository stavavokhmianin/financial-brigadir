#!/usr/bin/env bash
# Деплой публичного демо-стенда текущего коммита.
#
#   infra/stand/deploy.sh                         # root@5.35.98.96, https://5-35-98-96.sslip.io
#   STAND_TARGET=root@1.2.3.4 STAND_HOST=example.ru infra/stand/deploy.sh
#
# Web-клиент собирается здесь (на сервере 1 ГБ памяти), код — из git, без незакоммиченных
# правок. Готовую сборку можно передать через STAND_WEB_DIR.
set -euo pipefail

# macOS добавляет AppleDouble-файлы `._*` при упаковке xattr. Python/Alembic пытается
# импортировать такие файлы как миграции и падает на содержащихся в них NUL-байтах.
export COPYFILE_DISABLE=1

TARGET=${STAND_TARGET:-root@5.35.98.96}
HOST=${STAND_HOST:-5-35-98-96.sslip.io}
KEY=${STAND_KEY:-$HOME/.ssh/brigadir_deploy}
ROOT=$(git rev-parse --show-toplevel)
SHA=$(git -C "$ROOT" rev-parse --short HEAD)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
SSH=(ssh -i "$KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$TARGET")

echo "== релиз $SHA → $TARGET (https://$HOST)"
mkdir -p "$WORK/release"
git -C "$ROOT" archive --format=tar HEAD \
  packages/forecast_core packages/synthetic_generator services/api infra/stand |
  tar -x -C "$WORK/release"

if [ -n "${STAND_WEB_DIR:-}" ]; then
  cp -r "$STAND_WEB_DIR" "$WORK/release/web"
else
  (cd "$ROOT/apps/client" &&
    EXPO_PUBLIC_API_URL="https://$HOST" npx expo export --platform web \
      --output-dir "$WORK/release/web" --clear)
fi
grep -rq "https://$HOST" "$WORK/release/web/_expo" ||
  { echo "web-сборка не указывает на https://$HOST" >&2; exit 1; }

find "$WORK/release" -name '._*' -delete
tar --no-xattrs -C "$WORK/release" -czf "$WORK/release.tgz" .
"${SSH[@]}" "mkdir -p /opt/brigadir/releases/$SHA && tar -xz -C /opt/brigadir/releases/$SHA && find /opt/brigadir/releases/$SHA -name '._*' -delete" \
  < "$WORK/release.tgz"
"${SSH[@]}" "sh /opt/brigadir/releases/$SHA/infra/stand/remote-setup.sh /opt/brigadir/releases/$SHA $HOST"

echo "== проверка снаружи"
for _ in $(seq 1 60); do
  if curl -fsS "https://$HOST/api/v1/health/ready" >/dev/null 2>&1; then break; fi
  sleep 3  # первый запуск: Caddy получает сертификат
done
curl -fsS "https://$HOST/api/v1/health/ready"
echo
curl -fsS -o /dev/null -w "web: %{http_code}\n" "https://$HOST/"
