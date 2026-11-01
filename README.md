# Финансовый бригадир

Monorepo финансового прогнозирования: независимый Python SDK, расчётный API и
reference-клиент для web, Android и iOS.

**Публичный демо-стенд:** https://5-35-98-96.sslip.io

Сервис принимает счета, историю операций, доходы и будущие обязательства, после чего
строит прогноз денежных потоков, оценивает риск нарушения неснижаемого остатка и считает
сценарии «что если». Текущий публичный стенд использует только синтетические данные и не
предназначен для реальных банковских выписок — точная граница описана в
[документе безопасности](docs/security-readiness.md).

## Что реализовано

- регистрация, вход и отдельные пользовательские профили;
- гостевой учебный аккаунт с ускоренным временем и синтетическими операциями;
- прогноз на 30 дней: модели `baseline-0.2` и `mc-0.3`, резерв, минимум и сценарный
  диапазон;
- расчёт «можно потратить» и проверка конкретной покупки без изменения реестра;
- интерактивный разбор только значимых трат: «обычная» / «разовая», свайп, пропуск,
  необязательный комментарий и отмена последнего ответа;
- поиск регулярных платежей с подтверждением пользователя и защитой от двойного учёта;
- счета, операции, обязательства, доходы, CSV-импорт, дедупликация и банковский mock;
- предупреждения под колокольчиком, тихие часы, лимиты и точечное отключение напоминаний;
- экспорт и удаление профиля, retention демо-данных и изоляция пользователей;
- самостоятельный `financial-sdk`, не зависящий от FastAPI, UI, банка или хранилища.

Продукт не является банком и не проводит платежи. Прогнозы — модельные оценки, а не
гарантированный будущий остаток.

## Структура

```text
apps/client/                   Expo Router: web + Android + iOS
services/api/                  FastAPI, REST API /api/v1, SQLAlchemy, Alembic
services/worker/               retention и фоновые операции
packages/financial_sdk/        публичный SDK и адаптеры данных
packages/forecast_core/        расчётное ядро
packages/synthetic_generator/  воспроизводимая учебная синтетика
packages/api_contracts/        OpenAPI и примеры входных данных
infra/                         Docker и CI-контур
infra/pilot/                   изолированный пилотный контур
infra/stand/                   публичный демо-стенд
docs/                          актуальная продуктовая и техническая документация
```

Навигация по документации: [docs/README.md](docs/README.md).

## Быстрый старт

Требования: Python 3.12+, Node.js 22+, Docker — для полного контура.

### Полный backend в Docker

```bash
cp .env.example .env
docker compose up --build
```

Будут запущены PostgreSQL, API на `http://localhost:8000`, worker и smoke-проверка.
Swagger в demo-режиме: `http://localhost:8000/api/v1/docs`.

Клиент запускается отдельно:

```bash
cd apps/client
npm ci
EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

### Backend без Docker

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cd services/api
alembic upgrade head
uvicorn app.main:app --reload
```

SQLite используется по умолчанию. Для PostgreSQL задайте `DATABASE_URL`.

### SDK без приложения

```bash
pip install ./packages/forecast_core ./packages/financial_sdk
python packages/financial_sdk/examples/basic_forecast.py
```

Публичный интерфейс и примеры: [docs/sdk.md](docs/sdk.md).

## Проверки

```bash
ruff check .
ruff format --check .
mypy packages services/api/app services/worker/fb_worker
pytest

cd apps/client
npm ci
npm run typecheck
npm test
npm run build:web
```

GitHub Actions дополнительно проверяет PostgreSQL, Docker Compose, OpenAPI, web/Android/iOS
export, аудит зависимостей и пилотный TLS-контур. Критерии:
[docs/quality-gates.md](docs/quality-gates.md).

## Разработка и релиз

- Основная ветка — `master`; изменения должны оставлять CI зелёным.
- Деньги передаются целыми minor units (`*_minor`), время хранится в UTC.
- Новый API-маршрут требует обновления `packages/api_contracts/openapi.yaml`.
- Изменение архитектурной границы фиксируется ADR в `docs/ADR/`.
- Публичный стенд выкатывается из текущего коммита командой
  `./infra/stand/deploy.sh`; эксплуатация — [docs/stand.md](docs/stand.md).
- Пилотный/on-prem-профиль — [docs/pilot.md](docs/pilot.md).
