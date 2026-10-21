proxy_pass http://api:8000;
proxy_http_version 1.1;
proxy_set_header Host $host;
# Затираем клиентский X-Forwarded-For: API доверяет только адресу, который видит прокси.
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto https;
proxy_read_timeout 30s;
