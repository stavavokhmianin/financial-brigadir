# ADR-0001. Monorepo, стек и границы модулей

- Статус: принято
- Дата: 2026-10-19
- Основание: ТЗ v2.0, разделы 1.3, 7, 14, 22.1

## Решение

1. Один репозиторий со структурой из раздела 14:
   `apps/client` (Expo Router: web + Android + iOS), `services/api` (FastAPI, модульный монолит),
   `services/worker`, `packages/forecast_core`, `packages/synthetic_generator`,
   `packages/api_contracts`, `infra`, `docs`.
2. `forecast_core` — чистый Python без FastAPI/ORM/UI/LLM. Это проверяет тест
   `packages/forecast_core/tests/test_core.py::test_core_does_not_import_framework_or_orm`.
   На вход ядро получает неизменяемый `ForecastInputSnapshot`.
3. `synthetic_generator` не зависит от `forecast_core`: генератор и движок не должны
   использовать один алгоритм как эталон качества (раздел 23.1).
4. Деньги — целые копейки (`*_minor`, int64), время — UTC, валюта MVP — RUB.
5. Python 3.12+ (CI работает на 3.12), PostgreSQL 16 в compose, SQLite для быстрых
   unit-тестов и локального запуска без Docker. Схема одна (SQLAlchemy 2 + Alembic);
   миграции проверяются на обеих СУБД.
6. Контракт клиента и сервера — `packages/api_contracts/openapi.yaml`, который экспортируется
   из FastAPI. Тест не пропускает расхождение кода и файла, TypeScript-типы клиента
   генерируются из этого файла.

## Последствия

- Добавить эндпоинт — значит обновить код, перегенерировать `openapi.yaml` и
  пройти ревью; иначе CI упадёт.
- Микросервисы, Kafka, Kubernetes и feature store не вводятся до подтверждения нагрузки (раздел 7.9).
