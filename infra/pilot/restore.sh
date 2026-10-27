#!/bin/sh
# Восстановление: ./restore.sh <файл>. После загрузки дампа удаления, сделанные позже
# бэкапа, применяются снова по журналу на отдельном томе (раздел 25 ТЗ).
set -eu
cd "$(dirname "$0")"
[ -f "${1:-}" ] || { echo "использование: ./restore.sh backups/<файл>.sql.gz.enc" >&2; exit 2; }
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass file:secrets/backup_key -in "$1" |
  gunzip |
  docker compose exec -T db psql -U brigadir -d brigadir -v ON_ERROR_STOP=1 -q >/dev/null
docker compose exec -T api python -m app.cli reapply-erasures
