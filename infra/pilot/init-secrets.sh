#!/bin/sh
# Генерирует секреты пилотного стенда в infra/pilot/secrets (в git не попадают).
# Повторный запуск ничего не перезаписывает: потеря backup_key = потеря бэкапов.
set -eu
cd "$(dirname "$0")"
umask 077
mkdir -p secrets
[ -f secrets/db_password ] || printf '%s' "$(openssl rand -hex 24)" > secrets/db_password
[ -f secrets/database_url ] ||
  printf 'postgresql+psycopg://brigadir:%s@db:5432/brigadir' "$(cat secrets/db_password)" > secrets/database_url
[ -f secrets/backup_key ] || printf '%s' "$(openssl rand -hex 32)" > secrets/backup_key
# Файлы читают процессы в контейнерах (uid 70 у postgres, 10001 у API); доступ к ним
# ограничивает каталог 0700 на хосте.
chmod 700 secrets
chmod 644 secrets/db_password secrets/database_url
chmod 600 secrets/backup_key
echo "секреты в $(pwd)/secrets; backup_key храните отдельно от бэкапов"
