"""Сборка снимка из унифицированного формата (разделы 8.2, 12.2) и фактическая траектория.

Модуль работает со словарями контракта, а не с кодом генератора: ядро остаётся
независимым, но его можно проверить на любых данных этого формата — синтетике,
выгрузке из БД или реальной выписке для бэктеста.
"""

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from forecast_core.types import (
    AccountSnapshot,
    AccountType,
    Coverage,
    ForecastInputSnapshot,
    HistoricalTransaction,
    IncomeExpectation,
    ObligationEvent,
    ObligationStatus,
    TxStatus,
    TxType,
)

LIQUID = {AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS}


def _transactions(records: Iterable[Mapping[str, Any]]) -> tuple[HistoricalTransaction, ...]:
    return tuple(
        HistoricalTransaction(
            id=str(r["external_id"]),
            account_id=str(r["account_id"]),
            occurred_at=datetime.fromisoformat(r["occurred_at"]),
            amount_minor=int(r["amount_minor"]),
            type=TxType(r["type"]),
            status=TxStatus(r["status"]),
            category=r.get("category"),
        )
        for r in records
    )


def snapshot_from_dataset(
    data: Mapping[str, Any],
    reserve_minor: int = 500_000,
    horizon_days: int = 30,
    *,
    without_spending: bool = False,
) -> ForecastInputSnapshot:
    """Снимок «на дату as_of» из блока ``known``; ``hidden_future`` не используется.

    ``without_spending=True`` даёт baseline A из раздела 15.2 — только календарь.
    """
    known = data["known"]
    accounts = tuple(
        AccountSnapshot(
            id=a["account_id"],
            type=AccountType(a["type"]),
            currency=a["currency"],
            balance_minor=int(a["balance_minor"]),
            data_as_of=datetime.fromisoformat(a["data_as_of"]),
            is_liquid=bool(a["is_liquid"]),
            credit_limit_minor=a.get("credit_limit_minor"),
            blocked_minor=int(a.get("blocked_minor") or 0),
        )
        for a in known["accounts"]
    )
    obligations = tuple(
        ObligationEvent(
            id=o["obligation_id"],
            account_id=o.get("account_id"),
            due_date=date.fromisoformat(o["due_date"]),
            amount_minor=int(o["amount_minor"]),
            status=ObligationStatus(o["status"]),
            kind=o["kind"],
            critical=o.get("priority", "critical") == "critical",
            movable=bool(o.get("movable", False)),
            amount_min_minor=o.get("amount_min_minor"),
            amount_max_minor=o.get("amount_max_minor"),
            recurrence=o.get("recurrence", "none"),
            recurrence_day=o.get("recurrence_day"),
            title=o.get("title", ""),
        )
        for o in known["obligations"]
    )
    incomes = tuple(
        IncomeExpectation(
            id=i["income_id"],
            account_id=i.get("account_id"),
            date_from=date.fromisoformat(i["date_from"]),
            date_to=date.fromisoformat(i["date_to"]),
            amount_min_minor=int(i["amount_min_minor"]),
            amount_max_minor=int(i["amount_max_minor"]),
            probability=float(i["probability"]),
            confirmed=bool(i["confirmed"]),
            recurrence=i.get("recurrence", "none"),
            title=i.get("title", ""),
            kind=i.get("kind", "other"),
        )
        for i in known["incomes"]
    )
    history = () if without_spending else _transactions(known["transactions"])
    coverage = Coverage(data.get("profile", {}).get("coverage", "unknown"))
    return ForecastInputSnapshot(
        as_of=datetime.fromisoformat(data["as_of"]),
        timezone=data.get("profile", {}).get("timezone", "Europe/Moscow"),
        horizon_days=horizon_days,
        reserve_minor=reserve_minor,
        accounts=accounts,
        obligations=obligations,
        incomes=incomes,
        history=history,
        coverage=coverage,
    )


def actual_liquid_path(data: Mapping[str, Any], horizon_days: int) -> dict[date, int]:
    """Фактический ликвидный остаток на конец каждого дня по ``hidden_future``.

    Нужен только для оценки качества (бэктест): в признаки модели не попадает.
    """
    known = data["known"]
    tz = ZoneInfo(data.get("profile", {}).get("timezone", "Europe/Moscow"))
    liquid = {
        a["account_id"]
        for a in known["accounts"]
        if AccountType(a["type"]) in LIQUID and a["is_liquid"]
    }
    start = sum(
        int(a["balance_minor"]) - int(a.get("blocked_minor") or 0)
        for a in known["accounts"]
        if a["account_id"] in liquid
    )
    today = datetime.fromisoformat(data["as_of"]).astimezone(tz).date()
    by_day: dict[date, int] = {}
    for tx in data["hidden_future"]["transactions"]:
        if tx["account_id"] not in liquid or tx["status"] != "posted":
            continue
        day = datetime.fromisoformat(tx["occurred_at"]).astimezone(tz).date()
        # Остаток дня выгрузки после as_of относится к первому дню прогноза.
        day = max(day, today + timedelta(days=1))
        by_day[day] = by_day.get(day, 0) + int(tx["amount_minor"])
    path: dict[date, int] = {}
    balance = start
    for offset in range(1, horizon_days + 1):
        day = today + timedelta(days=offset)
        balance += by_day.get(day, 0)
        path[day] = balance
    return path
