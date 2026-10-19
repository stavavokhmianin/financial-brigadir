# Модель данных (этап 1)

Код: `services/api/app/db/models.py`, миграция `services/api/migrations/versions/0001_initial_schema.py`.

```
users ─┬─ auth_sessions            (token_hash, expires_at)
       ├─ data_sources ─┬─ accounts ── transactions ──┐ related_transaction_id (возврат → покупка)
       │                └─ import_batches ────────────┘ transfer_group_id (две стороны перевода)
       ├─ obligations       (rent, loan, credit_card, …; confirmed | inferred | uncertain | canceled)
       ├─ income_events     (диапазон дат и сумм, вероятность)
       ├─ forecast_runs ── forecast_points (day, p10/p50/p90, risk_probability)
       │        └─ scenarios (base_run_id, delta_events, result_run_id)
       ├─ alerts            (send | defer | suppress, reason, event_key)
       ├─ notification_settings (quiet | smart | active, тихие часы, лимит в неделю)
       └─ audit_events      (действие и id объекта, без финансовых подробностей)
```

## Сущности раздела 8.1 и их таблицы

| ТЗ | Таблица | Примечание |
|----|---------|------------|
| User | `users` | `risk_preferences` хранит резерв и допустимый риск, `plan` — free/plus (FR-28) |
| Account | `accounts` | `available_balance_minor`, `credit_limit_minor`, `blocked_minor`, `is_liquid`, `updated_at`, `source_id` |
| Transaction | `transactions` | поля из 8.2 плюс `booked_at`, `transfer_group_id`, `related_transaction_id`, `needs_review` |
| Obligation | `obligations` | `owner_id` из ТЗ называется `user_id`; есть диапазон суммы, `recurrence_day` (31-е → последний день месяца), `movable` |
| IncomeEvent | `income_events` | `date_range` и `amount_range` разложены на `*_from/*_to` и `*_min/*_max` |
| ForecastRun | `forecast_runs` | `input_snapshot`, `input_fingerprint`, `model_version`, `seed`, `quality_flags`, `idempotency_key` |
| ForecastPoint | `forecast_points` | уникальная пара `(run_id, day)` |
| Scenario | `scenarios` | история операций не меняется, хранится только дельта |
| Alert | `alerts` | `action` + `reason`, журнал без исходной выписки |
| Household | — | после MVP |

Служебные таблицы: `auth_sessions`, `data_sources` (тип источника и свежесть данных — FR-04),
`import_batches` (fingerprint файла для идемпотентного импорта), `notification_settings`,
`audit_events`.

## Инварианты, которые держит сама БД

- Деньги — `BIGINT` в копейках, у списаний отрицательный знак. Сумма обязательства положительна.
- `UNIQUE(account_id, source_id, external_id)`: повторная доставка не удваивает операцию (23.2.6).
- `UNIQUE(user_id, fingerprint)` для импортов и `UNIQUE(user_id, idempotency_key)` для расчётов.
- CHECK на перечисления (VARCHAR + CHECK одинаково работает в SQLite и PostgreSQL), диапазоны
  вероятностей, порядок `min ≤ max` и `date_from ≤ date_to`.
- Время хранится только в UTC: `UTCDateTime` отклоняет naive-значения.
- `ON DELETE CASCADE` от пользователя: удаление по запросу стирает все персональные данные.

Тесты: `services/api/tests/test_schema.py`, `services/api/tests/test_migrations.py`.
Тест миграций проверяет `upgrade → нет расхождений с моделями → downgrade` на SQLite и PostgreSQL.
