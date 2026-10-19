# ADR-0003. Контракт API этапа 1

- Статус: принято
- Дата: 2026-10-19
- Основание: разделы 8.3, 22 ТЗ

## Решение

1. Все пути раздела 22.2 есть в `packages/api_contracts/openapi.yaml` с полными схемами
   запросов и ответов.
2. Реализованы эндпоинты, нужные для экрана запуска демо и ручного ввода:
   `demo/sessions`, `accounts` (GET/POST), `transactions`, `obligations` (GET/POST),
   `notification-settings` (PATCH), `health`.
3. Остальные (`imports/csv`, `forecasts`, `scenarios`, `alerts`, `connectors/bank-mock/sync`)
   уже проверяют авторизацию и валидируют тело. Отвечают они `501` с кодом `not_implemented`
   и `details.planned_stage`. Клиент показывает честное состояние «скоро», а схема ответа
   уже зафиксирована: B и C могут работать параллельно.
4. Добавлены пути, которых нет в 22.2:
   - `GET /api/v1/demo/profiles` — список профилей для экрана запуска демо (FR-01);
   - `GET /api/v1/health/ready` — readiness отдельно от liveness (требование 22.2).
5. Формат ошибок — `{"error": {"code", "message", "details?"}}`. Ошибки валидации остаются
   стандартными `422` FastAPI.
6. Авторизация: `Authorization: Bearer <token>`. Токен выдаёт демо-сессия, в БД хранится
   только SHA-256. Чужой объект → `404`, а не `403`, чтобы не раскрывать его существование.
7. Пагинация операций — курсор `(occurred_at, id)`, а не offset: результат стабилен при
   поступлении новых операций.
8. `GET /obligations` возвращает и сами обязательства, и развёрнутый календарь в окне дат
   (`forecast_core.calendar.occurrences`, 31-е число → последний день месяца).

## Как менять контракт

Изменить код → `python services/api/scripts/export_openapi.py` → закоммитить `openapi.yaml`
→ ревью. Тест `test_openapi_contract.py` не даёт разойтись коду и файлу.
