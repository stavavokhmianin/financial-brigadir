#!/bin/sh
# Установка или обновление демо-стенда на Ubuntu 24.04. Идемпотентно, запускается от root
# скриптом deploy.sh: remote-setup.sh <каталог релиза> <хост>.
set -eu
RELEASE=$1
HOST=$2
HERE="$RELEASE/infra/stand"
export DEBIAN_FRONTEND=noninteractive

echo "== пакеты"
# Caddy стартует сразу после установки: конфиг и окружение кладём до неё, иначе
# дефолтный сайт на :80 упрётся в занятый панелью порт.
install -d -m 755 /etc/caddy /etc/systemd/system/caddy.service.d /var/log/caddy
cp "$HERE/Caddyfile" /etc/caddy/Caddyfile
printf '[Service]\nEnvironment=STAND_HOST=%s\n' "$HOST" > /etc/systemd/system/caddy.service.d/brigadir.conf
systemctl daemon-reload
missing=""
for pkg in python3.12-venv caddy sqlite3 curl; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing="$missing $pkg"
done
if [ -n "$missing" ]; then
  apt-get update -qq
  # shellcheck disable=SC2086
  apt-get install -y -qq -o Dpkg::Options::=--force-confold $missing
fi
# Каталог создан до пакета, то есть root-ом: без этого Caddy не может писать журнал.
chown caddy:caddy /var/log/caddy

echo "== пользователь и каталоги"
id brigadir >/dev/null 2>&1 ||
  useradd --system --home-dir /var/lib/brigadir --shell /usr/sbin/nologin brigadir
install -d -o brigadir -g brigadir -m 750 /var/lib/brigadir /var/lib/brigadir/backups
install -d -m 755 /etc/brigadir /opt/brigadir

echo "== окружение API"
if [ ! -f /etc/brigadir/api.env ]; then
  cat > /etc/brigadir/api.env <<EOF
APP_MODE=demo
DATABASE_URL=sqlite:////var/lib/brigadir/brigadir.db
CORS_ORIGINS=https://$HOST
ERASURE_LOG_PATH=/var/lib/brigadir/erasures.log
DEMO_SESSION_TTL_HOURS=24
LOG_LEVEL=INFO
EOF
  chgrp brigadir /etc/brigadir/api.env
  chmod 640 /etc/brigadir/api.env
fi

echo "== Python-окружение"
[ -x /opt/brigadir/venv/bin/python ] || python3.12 -m venv /opt/brigadir/venv
/opt/brigadir/venv/bin/pip install -q --upgrade pip
/opt/brigadir/venv/bin/pip install -q \
  "$RELEASE/packages/forecast_core" "$RELEASE/packages/synthetic_generator" "$RELEASE/services/api"
ln -sfn "$RELEASE" /opt/brigadir/current

echo "== web-клиент"
rm -rf /var/www/brigadir.next
cp -r "$RELEASE/web" /var/www/brigadir.next
rm -rf /var/www/brigadir.prev
[ -d /var/www/brigadir ] && mv /var/www/brigadir /var/www/brigadir.prev
mv /var/www/brigadir.next /var/www/brigadir

echo "== сервисы"
cp "$HERE/brigadir-api.service" "$HERE/brigadir-maintenance.service" \
  "$HERE/brigadir-maintenance.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable -q brigadir-api.service brigadir-maintenance.timer caddy.service
systemctl restart brigadir-api.service
systemctl start brigadir-maintenance.timer
STAND_HOST="$HOST" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
systemctl restart caddy.service

echo "== http → https"
if [ -d /etc/nginx/conf.d ] && command -v nginx >/dev/null 2>&1; then
  sed "s/STAND_HOST/$HOST/" "$HERE/nginx-redirect.conf" > /etc/nginx/conf.d/brigadir-redirect.conf
  if nginx -t -q 2>/dev/null; then
    systemctl reload nginx
  else
    rm -f /etc/nginx/conf.d/brigadir-redirect.conf
    echo "nginx отверг редирект, пропускаю" >&2
  fi
fi

echo "== проверка API"
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8010/api/v1/health/ready >/dev/null 2>&1; then
    echo "API готов"
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:8010/api/v1/health/ready

echo "== старые релизы"
ls -1dt /opt/brigadir/releases/* | tail -n +4 | xargs -r rm -rf
echo
echo "готово: https://$HOST"
