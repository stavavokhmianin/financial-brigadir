# Публичный демо-стенд

**https://5-35-98-96.sslip.io** — web-клиент и API (`/api/v1`) в демо-режиме.
Swagger: https://5-35-98-96.sslip.io/api/v1/docs.

`5-35-98-96.sslip.io` — DNS-имя, которое указывает на IP `5.35.98.96`; своего домена не нужно.
Сертификат Let's Encrypt выпускает и продлевает Caddy.

## Как устроено

Сервер — VPS с Ubuntu 24.04: 1 vCPU, 1 ГБ памяти, панель хостинга ISPmanager. Порт 80 занят
nginx панели, поэтому стенд работает только на 443, а сертификат подтверждается через TLS-ALPN.
Docker не используется: сборка образов на 1 ГБ памяти не помещается, а нативные сервисы
занимают ~85 МБ.

| Компонент | Где | Как |
|---|---|---|
| Caddy | `:443` | HTTPS, HSTS, CSP; статика `/var/www/brigadir`, `/api/*` → `127.0.0.1:8010` |
| API | `127.0.0.1:8010` | systemd `brigadir-api`, пользователь `brigadir`, песочница systemd, `MemoryMax=350M` |
| Данные | `/var/lib/brigadir/brigadir.db` | SQLite; миграции применяются при каждом старте |
| Обслуживание | таймер `brigadir-maintenance` | раз в 6 часов: удаление заброшенных демо-профилей старше 7 дней и онлайн-бэкап базы (хранятся 7 последних) |
| Код | `/opt/brigadir/releases/<коммит>` | `current` — ссылка на активный релиз, хранятся 3 последних |

Наружу открыт только 443. API слушает только localhost. Настройки — в
`/etc/brigadir/api.env` (создаётся один раз, при выкатке не перезаписывается).

## Выкатка

С рабочей машины, из корня репозитория, на закоммиченном коде:

```bash
infra/stand/deploy.sh
```

Что делает скрипт:
- собирает web-клиент под адрес стенда;
- упаковывает код из `git`;
- на сервере запускает `remote-setup.sh`: он ставит недостающее, обновляет venv, переключает
  релиз и перезапускает сервисы;
- проверяет стенд снаружи по HTTPS.

Повторный запуск безопасен. Доступ — по ключу `~/.ssh/brigadir_deploy`, пароль сервера не
используется. Другой сервер или домен задаются через `STAND_TARGET` и `STAND_HOST`.

После выкатки:

```bash
python scripts/demo_walkthrough.py --api https://5-35-98-96.sslip.io
```

```bash
python scripts/qa_screens.py --web https://5-35-98-96.sslip.io
```

## Телефон

APK со вшитым адресом стенда: в Actions → «Stand APK» → артефакт
`financial-brigadir-stand-apk`. Его собирают ручной запуск и каждый push клиента в `master`.
Установить и открыть — адрес вводить не нужно.

## Эксплуатация

```bash
ssh -i ~/.ssh/brigadir_deploy root@5.35.98.96
```

- **Логи API:** `journalctl -u brigadir-api -f`.
- **Логи Caddy:** `/var/log/caddy/brigadir.log`.
- **Перезапуск:** `systemctl restart brigadir-api caddy`.
- **Обслуживание вручную:** `systemctl start brigadir-maintenance`.
- **Восстановление из бэкапа:**
  1. `systemctl stop brigadir-api`;
  2. скопировать файл из `/var/lib/brigadir/backups/` в `brigadir.db`;
  3. `systemctl start brigadir-api`;
  4. `sudo -u brigadir … python -m app.cli reapply-erasures` — повторить удаления, сделанные
     после этого бэкапа.

## Режим пилота

Для пилота с добровольцами:
1. Поставить в `/etc/brigadir/api.env` значение `APP_MODE=pilot`.
2. Перезапустить API.
3. Выдать коды: `python -m app.cli invite` (см. `docs/pilot.md`).

Для реальных данных площадка должна выполнить условия из `docs/pilot.md`:
- шифрование диска;
- срок хранения бэкапов;
- согласие и условия по 152-ФЗ.

Демо-стенд с синтетикой этого не требует.
