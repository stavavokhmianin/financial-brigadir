# Финансовый бригадир — monorepo

Прогноз личных денежных потоков и вероятности кассового разрыва (ТЗ v2.0, 19.10.2026).
В `master` лежат код и отчёты по этапам: [reports/](reports/README.md), отчёты
именуются `REPORT_<этап>.<задача>.md` по плану 16.2 ТЗ. Рабочая ветка — `step4ik`,
она вливается в `master` целиком.

**Демо-стенд:** https://5-35-98-96.sslip.io — выкатка `infra/stand/deploy.sh`, устройство и эксплуатация: [docs/stand.md](docs/stand.md).

Приватность, экспорт, удаление и сроки хранения: [docs/privacy.md](docs/privacy.md).
Критерии приёмки: [docs/quality-gates.md](docs/quality-gates.md).
Android APK и нативный E2E: [docs/mobile-verification.md](docs/mobile-verification.md).
Возможности Free/Plus: [docs/plans.md](docs/plans.md).
Самостоятельный финансовый SDK: [docs/sdk.md](docs/sdk.md).
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
packages/financial_sdk/      публичный SDK: данные → прогноз, риск и сценарии
packages/synthetic_generator/  воспроизводимые демо-профили
packages/api_contracts/      openapi.yaml — контракт клиента и сервера
infra/                       Dockerfile'ы и compose (демо)
infra/pilot/                 пилотный/on-prem-контур: TLS-прокси, изоляция, бэкапы
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

### Пилотный контур

```bash
cd infra/pilot && ./init-secrets.sh && ./make-dev-cert.sh
PUBLIC_ORIGIN=https://localhost:8443 docker compose up -d --build --wait
docker compose exec api python -m app.cli invite --count 5
```

Вход по коду участника, только TLS, API без выхода в интернет, зашифрованные бэкапы с повтором
удалений. Подробно — `docs/pilot.md`.

## Демо (раздел 16.4)

Сценарий выступления, тайминги и план Б — `docs/demo-script.md`.

```bash
python scripts/demo_walkthrough.py --api http://localhost:8000   # против стенда
python scripts/demo_walkthrough.py --offline                     # План Б: без сети и Docker
python scripts/record_demo.py --web http://127.0.0.1:8081        # видео-страховка (Playwright)
```

Презентация для защиты — `docs/pitch/deck.md` (Marp), план развития — `docs/roadmap.md`.

## Проверки

```bash
ruff check . && ruff format --check .
mypy packages/forecast_core/src packages/financial_sdk/src packages/synthetic_generator/src services/api/app services/worker/fb_worker
pytest                                  # SQLite; при TEST_DATABASE_URL ещё и PostgreSQL
cd apps/client && npm run typecheck && npm test
```

CI (`.github/workflows/ci.yml`) прогоняет то же самое, собирает web-бандл клиента и
запускает `docker compose` со smoke-тестом демо и отдельно — пилотный контур
(`pilot-smoke`: TLS, изоляция сети, limiter, бэкап → удаление → восстановление).

## Команда (раздел 16.1 ТЗ)

| Роль | Зона |
|------|------|
| A — backend/data | `services/api`: модель данных, миграции, API, адаптеры, авторизация |
| B — client/product | `apps/client`: экраны, онбординг, состояния ошибок |
| C — forecasting/QA/infra | `packages/forecast_core`, `packages/financial_sdk`, `packages/synthetic_generator`, CI, Docker |

Правила: деньги — целые копейки, время — UTC, новый эндпоинт только вместе с обновлённым
`openapi.yaml`, архитектурные изменения — через `docs/ADR/`.
