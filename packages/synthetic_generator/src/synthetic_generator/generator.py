"""Сборка датасета профиля: ``known`` (что известно на дату прогноза) отдельно от
``hidden_future`` (что произойдёт на самом деле). Утечки будущего в ``known`` нет.
"""

from datetime import date, datetime, timedelta
from typing import Any

from synthetic_generator.dates import MSK, clamp_day
from synthetic_generator.ledger import Ledger, Tx
from synthetic_generator.profiles import PROFILES, ProfileInfo

SCHEMA_VERSION = "1"
DEFAULT_SEED = 42
DEFAULT_AS_OF = datetime(2026, 10, 19, 10, 0, tzinfo=MSK)
DEFAULT_MONTHS = 8
DEFAULT_HORIZON_DAYS = 45


def list_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": info.id,
            "title": info.title,
            "description": info.description,
            "segment": info.segment,
            "mvp": info.mvp,
            "anomalies": list(info.anomalies),
        }
        for info in PROFILES.values()
    ]


def generate(
    profile_id: str,
    seed: int = DEFAULT_SEED,
    as_of: datetime = DEFAULT_AS_OF,
    months: int = DEFAULT_MONTHS,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> dict[str, Any]:
    """Строит профиль. Одинаковые аргументы → побайтно одинаковый результат."""
    if profile_id not in PROFILES:
        raise KeyError(f"неизвестный профиль: {profile_id}")
    if not 6 <= months <= 12:
        raise ValueError("история профиля должна быть 6–12 месяцев (раздел 12.2)")
    if not 1 <= horizon_days <= 120:
        raise ValueError("горизонт скрытого будущего: 1–120 дней")
    info = PROFILES[profile_id]
    ledger = Ledger(profile_id, info.prefix, seed, as_of, months, horizon_days)
    info.build(ledger)
    return _assemble(info, ledger, seed, months)


def _iso(value: datetime | date) -> str:
    return value.isoformat()


def _tx_dict(ledger: Ledger, tx: Tx) -> dict[str, Any]:
    data: dict[str, Any] = {
        "transaction_id": f"tx_{tx.external_id}",
        "account_id": ledger.account_id(tx.account),
        "occurred_at": _iso(tx.occurred_at),
        "booked_at": _iso(tx.booked_at),
        "amount_minor": tx.amount_minor,
        "currency": "RUB",
        "type": tx.type,
        "category": tx.category,
        "status": tx.status,
        "source": "synthetic",
        "external_id": tx.external_id,
        "description": tx.description,
        "transfer_group_id": tx.transfer_group_id,
        "related_external_id": tx.related_external_id,
    }
    if tx.extra:
        data["extra"] = dict(sorted(tx.extra.items()))
    return data


def _sorted(txs: list[Tx]) -> list[Tx]:
    return sorted(txs, key=lambda t: (t.occurred_at, t.external_id))


def _next_due(today: date, day: int, starts: date | None, ends: date | None) -> date | None:
    year, month = today.year, today.month
    for _ in range(14):
        due = clamp_day(year, month, day)
        if due > today and (starts is None or due >= starts):
            return None if ends is not None and due > ends else due
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return None


def _assemble(info: ProfileInfo, ledger: Ledger, seed: int, months: int) -> dict[str, Any]:
    as_of = ledger.as_of
    known_txs = _sorted([t for t in ledger.txs if t.occurred_at <= as_of])
    hidden_txs = _sorted([t for t in ledger.txs if t.occurred_at > as_of])

    accounts = []
    for key, spec in ledger.accounts.items():
        account_known = [t for t in known_txs if t.account == key]
        accounts.append(
            {
                "account_id": ledger.account_id(key),
                "name": spec.name,
                "bank_name": spec.bank_name,
                "type": spec.type,
                "currency": "RUB",
                "balance_minor": ledger.balance_at(key, as_of),
                "credit_limit_minor": spec.credit_limit_minor,
                "blocked_minor": ledger.pending_minor(key),
                "is_liquid": spec.is_liquid,
                "data_as_of": _iso(as_of),
                "history_from": _iso(
                    min((t.occurred_at.date() for t in account_known), default=ledger.today)
                ),
                "is_partial": key in ledger.partial_accounts,
                "owner": spec.owner,
            }
        )

    obligations: list[dict[str, Any]] = []
    for obligation in ledger.obligations:
        due = _next_due(ledger.today, obligation.day, obligation.starts, obligation.ends)
        if due is None or due > ledger.horizon_end:
            continue
        has_range = obligation.jitter_minor > 0
        obligations.append(
            {
                "obligation_id": f"obl_{info.prefix}_{obligation.key}",
                "account_id": ledger.account_id(obligation.account),
                "kind": obligation.kind,
                "title": obligation.title,
                "amount_minor": obligation.amount_minor,
                "amount_min_minor": obligation.amount_minor - obligation.jitter_minor
                if has_range
                else None,
                "amount_max_minor": obligation.amount_minor + obligation.jitter_minor
                if has_range
                else None,
                "due_date": _iso(due),
                "recurrence": "monthly",
                "recurrence_day": obligation.day,
                "status": obligation.status,
                "priority": obligation.priority,
                "confidence": obligation.confidence,
                "movable": obligation.movable,
            }
        )
    for extra in ledger.extra_obligations:
        item = {k: v for k, v in extra.items() if k not in ("key", "account")}
        item["obligation_id"] = f"obl_{info.prefix}_{extra['key']}"
        item["account_id"] = ledger.account_id(extra["account"])
        item["due_date"] = _iso(extra["due_date"])
        obligations.append(item)

    incomes: list[dict[str, Any]] = []
    for income in ledger.incomes:
        due = _next_due(ledger.today, income.day, None, None)
        if due is None:
            continue
        incomes.append(
            {
                "income_id": f"inc_{info.prefix}_{income.key}",
                "account_id": ledger.account_id(income.account),
                "kind": income.kind,
                "title": income.title,
                "date_from": _iso(due),
                "date_to": _iso(due + timedelta(days=income.max_delay_days)),
                "amount_min_minor": income.amount_minor - income.jitter_minor,
                "amount_max_minor": income.amount_minor + income.jitter_minor,
                "probability": income.probability,
                "confirmed": income.confirmed,
                "recurrence": "monthly",
            }
        )
    for extra in ledger.extra_incomes:
        item = {k: v for k, v in extra.items() if k not in ("key", "account")}
        item["income_id"] = f"inc_{info.prefix}_{extra['key']}"
        item["account_id"] = ledger.account_id(extra["account"])
        item["date_from"] = _iso(extra["date_from"])
        item["date_to"] = _iso(extra["date_to"])
        incomes.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "profile": {
            "id": info.id,
            "title": info.title,
            "description": info.description,
            "segment": info.segment,
            "mvp": info.mvp,
            "coverage": info.coverage,
            "timezone": "Europe/Moscow",
        },
        "seed": seed,
        "months": months,
        "as_of": _iso(as_of),
        "history_from": _iso(ledger.history_from),
        "horizon_end": _iso(ledger.horizon_end),
        "known": {
            "accounts": accounts,
            "transactions": [_tx_dict(ledger, t) for t in known_txs],
            "obligations": sorted(obligations, key=lambda o: (o["due_date"], o["obligation_id"])),
            "incomes": sorted(incomes, key=lambda i: (i["date_from"], i["income_id"])),
            "reupload": [_tx_dict(ledger, t) for t in _sorted(ledger.reupload)],
            "manual_balances": {
                ledger.account_id(k): v for k, v in sorted(ledger.manual_balances.items())
            },
        },
        "hidden_future": {
            "transactions": [_tx_dict(ledger, t) for t in hidden_txs],
            "events": ledger.hidden_events,
        },
        "anomalies": ledger.anomalies,
        "truth": {
            "opening_balances": {
                ledger.account_id(k): v for k, v in sorted(ledger.openings.items())
            },
            "duplicate_external_ids": sorted(ledger.duplicates),
            "missing_transactions": [_tx_dict(ledger, t) for t in _sorted(ledger.missing)],
        },
    }
