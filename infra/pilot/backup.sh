#!/bin/sh
# Зашифрованный бэкап БД: ./backup.sh [файл]. Ключ — secrets/backup_key (AES-256).
# Журнал удалений в бэкап не входит намеренно — см. restore.sh.
set -eu
cd "$(dirname "$0")"
mkdir -p backups
out=${1:-backups/brigadir-$(date -u +%Y%m%dT%H%M%SZ).sql.gz.enc}
docker compose exec -T db pg_dump -U brigadir -d brigadir --clean --if-exists --no-owner |
  gzip |
  openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass file:secrets/backup_key -out "$out"
echo "$out"
