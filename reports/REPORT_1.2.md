# REPORT 1.2 — Схема данных и миграции

- **Этап:** 1 (19–22 октября 2026)
- **Ответственный по 16.1:** A — backend/data
- **Коммит:** [`f90af11`](https://github.com/stavavokhmianin/financial-brigadir/commit/f90af11) в `step4ik`

## Что сделано

- ORM-модели (`services/api/app/db/models.py`) для всех сущностей раздела 8.1, кроме
  `Household` (это после MVP): `users`, `accounts`, `transactions`, `obligations`, `income_events`,
  `forecast_runs`, `forecast_points`, `scenarios`, `alerts`.
- Служебные таблицы:
  - `auth_sessions` — хранится только SHA-256 токена;
  - `data_sources` — тип источника и `data_as_of` для FR-04;
  - `import_batches` — fingerprint для идемпотентного импорта (7.2);
  - `notification_settings` — режимы, тихие часы и лимит 2 сообщения в неделю (10.1);
  - `audit_events`.
- Типы:
  - деньги — `BIGINT` в копейках;
  - время — `UTCDateTime`: приводит к UTC и отклоняет naive-значения;
  - перечисления — `VARCHAR + CHECK`, одинаково в SQLite и PostgreSQL;
  - словарь типов операций и статусов общий с `forecast_core`.
- Финансовые инварианты на уровне БД:
  - `UNIQUE(account_id, source_id, external_id)` — повторная доставка или импорт не удваивают
    операцию (23.2.6);
  - переводы связаны через `transfer_group_id`, возвраты через `related_transaction_id` (23.2.1, 23.2.4);
  - у кредитной карты отдельные `credit_limit_minor` и `is_liquid`: лимит не считается деньгами (23.2.3);
  - обязательства: статусы `confirmed/inferred/uncertain/canceled` (7.4), диапазон суммы,
    `recurrence_day` для случая «31-е число в коротком месяце» (12.3);
  - `ON DELETE CASCADE` от пользователя — удаление данных по запросу (13.1).
- Миграция `0001_initial_schema`. В `env.py` есть `render_item`, поэтому миграции не
  импортируют код приложения.
- Документ `docs/data-model.md`: схема, соответствие сущностям ТЗ, список инвариантов.

## Тесты

- `test_migrations.py`: `upgrade head` → сравнение с моделями без расхождений → `downgrade base`.
  Тест параметризован для SQLite и PostgreSQL (`TEST_DATABASE_URL`, в CI — сервис Postgres 16).
- `test_schema.py`:
  - повтор `external_id` отклоняется;
  - время с +03:00 сохраняется как UTC, naive-время запрещено;
  - неизвестный тип операции отклоняется;
  - работают 4 негативных проверки обязательств и порядок дат дохода;
  - удаление пользователя каскадно удаляет его данные.

Локально: **34 passed, 1 skipped** (PostgreSQL-вариант пропускается без `TEST_DATABASE_URL`),
ruff и mypy strict чистые.

## Решения

- В ТЗ поле называется `owner_id`, в схеме `obligations.user_id`: так проверка владельца одинакова
  во всех таблицах. Семейные обязательства (P2) получат отдельную связь с `household`.
- Идентификаторы — случайные строки с префиксом (`acc_…`, `tx_…`), не автоинкремент.
  По id нельзя угадать чужой объект.
