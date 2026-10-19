# REPORT 1.1 — Скелет monorepo, инфраструктура, CI

- **Этап:** 1 (19–22 октября 2026), раздел 16.2 ТЗ
- **Ответственные по 16.1:** все трое (A — `services/api`, B — `apps/client`, C — `packages/*`, CI, Docker)
- **Коммит:** [`5f5ad6a`](https://github.com/stavavokhmianin/financial-brigadir/commit/5f5ad6a) в `step4ik`

## Что сделано

**Структура (раздел 14)**: `apps/client`, `services/api`, `services/worker`, `packages/forecast_core`,
`packages/synthetic_generator`, `packages/api_contracts`, `infra`, `docs/ADR`, `.github/workflows`.

**C — forecasting/infra**
- `forecast_core` — пакет на чистом Python. Деньги в копейках: разбор строк вида
  «1 234,56» с округлением half-up, float не принимается. Добавлены неизменяемый
  `ForecastInputSnapshot` (раздел 22.1), расчёт ликвидного остатка и SHA-256-отпечаток
  снимка для воспроизводимости (13.3). Ликвидный остаток не учитывает кредитные лимиты,
  депозиты и заблокированные суммы (инвариант 23.2.3).
- Тест следит, чтобы `forecast_core` не импортировал FastAPI, SQLAlchemy, Pydantic и `app`.
- `infra/Dockerfile.api`, `infra/Dockerfile.worker` (non-root, healthcheck), `infra/compose.yaml`
  (Postgres 16 → API с `alembic upgrade head` → воркер → одноразовый `smoke`). Корневой `compose.yaml`,
  поэтому `docker compose up --build` работает из корня, как требует раздел 14.
- CI `.github/workflows/ci.yml`: ruff (lint + format), mypy strict, pytest на SQLite и на
  PostgreSQL-сервисе, `tsc` и сборка web-бандла клиента, `docker compose` со smoke-тестом.

**A — backend**
- FastAPI-приложение `create_app()`: CORS для Expo web и OpenAPI на `/api/v1/openapi.json`.
- `GET /api/v1/health` (liveness) и `GET /api/v1/health/ready` (readiness с проверкой БД)
  разделены, как требует 22.2.
- Настройки через `pydantic-settings` и `.env.example` (секретов в репозитории нет),
  SQLAlchemy-engine (в SQLite включены foreign keys), Alembic.

**B — client**
- Expo SDK 54 + Expo Router, одна кодовая база для web, Android и iOS; `typedRoutes`, strict TS,
  алиас `@/*`. Тесты на встроенном раннере Node без лишних зависимостей.

**Общее**: README с быстрым стартом, ADR-0001 (стек и границы модулей), ADR-0002 (ветки
`step4ik` и `master`), черновики `docs/threat-model.md` и `docs/experiment-plan.md`.

## Проверка

```bash
git checkout step4ik
pip install -r requirements-dev.txt
ruff check . && mypy packages/forecast_core/src services/api/app services/worker/fb_worker
pytest
```

Локально (Python 3.13, Windows): ruff — чисто, mypy strict — 0 ошибок, pytest — **23 passed**.

CI (GitHub Actions, прогоны 1.1 и 1.2) — все три задачи зелёные:
- Python: ruff, mypy, pytest. На CI 35 passed, тест миграций на PostgreSQL 16 не пропускается.
- Client: `npm install` (811 пакетов, Expo SDK 54), `tsc`, node-тесты, `expo export --platform web`.
- Compose: сборка образов с нуля, Postgres → API (`alembic upgrade head`) → smoke, код выхода 0.

## Отклонения и решения

- Вместо `feat/*` → PR → `main` код идёт в `step4ik`, отчёты — в `master` (ADR-0002).
- Воркер — простой цикл без Redis и брокера (раздел 7.9). Ошибка одной задачи не роняет цикл.

## Дальше

1.2 — схема данных; 1.3 — генератор; 1.4 — OpenAPI и эндпоинты; 1.5 — экран запуска демо.
