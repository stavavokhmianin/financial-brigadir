#!/bin/sh
# Самоподписанный сертификат для проверки стенда. В контуре банка используйте
# сертификат его УЦ: положите tls.crt и tls.key в infra/pilot/certs.
set -eu
cd "$(dirname "$0")"
mkdir -p certs
[ -f certs/tls.crt ] && { echo "certs/tls.crt уже есть"; exit 0; }
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
  -keyout certs/tls.key -out certs/tls.crt 2>/dev/null
chmod 600 certs/tls.key
echo "сертификат: $(pwd)/certs/tls.crt (действует 30 дней)"
