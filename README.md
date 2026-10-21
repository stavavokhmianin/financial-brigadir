# Финансовый бригадир — monorepo

Прогноз личных денежных потоков и вероятности кассового разрыва (ТЗ v2.0, 19.10.2026).
Код живёт в ветке `step4ik`, отчёты по этапам — в `master/reports`.

Приватность, экспорт, удаление и сроки хранения: [docs/privacy.md](docs/privacy.md).
Критерии приёмки: [docs/quality-gates.md](docs/quality-gates.md).
Плановая экономика: [docs/business-model.md](docs/business-model.md)
(`python scripts/business_model.py`).

> Продукт не банк и не проводит платежи. Прогнозы — модельные оценки, а не гарантированный остаток.

## Структура

```
apps/client/                 Expo Router: web + Android + iOS (одна кодовая база)
services/api/                FastAPI, модульный монолит, /api/v1
  app/api/v1/                REST-контроллеры
  app/domain/                типы и инварианты
  app/modules/               accounts, demo, auth …
  app/adapters/              demo (синтетика), bank_mock
  app/db/                    модели SQLAlchemy
  migrations/                Alembic
services/worker/             простой фоновый воркер
packages/forecast_core/      расчётное ядро: чистый Python
packages/synthetic_generator/  воспроизводимые демо-профили
packages/api_contracts/      openapi.yaml — контракт клиента и сервера
infra/                       Dockerfile'ы и compose
docs/ADR/                    архитектурные решения
```

## Быстрый старт

### Всё в Docker

```bash
cp .env.example .env
docker compose up --build
```

Поднимаются PostgreSQL, API (`http://localhost:8000/api/v1/docs`), воркер и одноразовый
`smoke`, который проверяет готовность API и создание демо-профиля.

Клиент:

```bash
cd apps/client
npm install
npx expo start --web      # или --android / --ios в среде Expo
```

### Без Docker (SQLite)

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cd services/api
alembic upgrade head
uvicorn app.main:app --reload
```

## Демо (раздел 16.4)

Сценарий выступления, тайминги и план Б — `docs/demo-script.md`.

```bash
python scripts/demo_walkthrough.py --api http://localhost:8000   # против стенда
python scripts/demo_walkthrough.py --offline                     # План Б: без сети и Docker
```

## Проверки

```bash
ruff check . && ruff format --check .
mypy packages/forecast_core/src packages/synthetic_generator/src services/api/app services/worker/fb_worker
pytest                                  # SQLite; при TEST_DATABASE_URL ещё и PostgreSQL
cd apps/client && npm run typecheck && npm test
```

CI (`.github/workflows/ci.yml`) прогоняет то же самое, собирает web-бандл клиента и
запускает `docker compose` со smoke-тестом.

## Команда (раздел 16.1 ТЗ)

| Роль | Зона |
|------|------|
| A — backend/data | `services/api`: модель данных, миграции, API, адаптеры, авторизация |
| B — client/product | `apps/client`: экраны, онбординг, состояния ошибок |
| C — forecasting/QA/infra | `packages/forecast_core`, `packages/synthetic_generator`, CI, Docker |

Правила: деньги — целые копейки, время — UTC, новый эндпоинт только вместе с обновлённым
`openapi.yaml`, архитектурные изменения — через `docs/ADR/`.
