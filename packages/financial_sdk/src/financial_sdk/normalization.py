"""Нормализация универсального словарного контракта в типы SDK."""

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from financial_sdk.models import FinancialData
from forecast_core import (
    AccountSnapshot,
    AccountType,
    Coverage,
    HistoricalTransaction,
    IncomeExpectation,
    ObligationEvent,
    ObligationStatus,
    TxStatus,
    TxType,
)


class NormalizationError(ValueError):
    """Вход не соответствует нейтральному контракту SDK."""


def _datetime(value: Any, field: str) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NormalizationError(f"{field}: datetime должен содержать часовой пояс")
    return parsed


def _date(value: Any, field: str) -> date:
    try:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise NormalizationError(f"{field}: ожидалась дата ISO") from exc


def _id(record: Mapping[str, Any], plain: str, external: str) -> str:
    value = record.get(plain, record.get(external))
    if value is None or not str(value).strip():
        raise NormalizationError(f"обязательное поле {plain}")
    return str(value)


def _unique(items: Iterable[Any], kind: str) -> tuple[Any, ...]:
    result = tuple(items)
    ids = [item.id for item in result]
    if len(ids) != len(set(ids)):
        raise NormalizationError(f"повторяющийся id в {kind}")
    return result


def normalize_financial_data(payload: Mapping[str, Any]) -> FinancialData:
    """Принять JSON-подобный документ без привязки к банку или БД.

    Денежные значения передаются целыми копейками в полях ``*_minor``.
    Идентификаторы допускают как короткое ``id``, так и доменные варианты
    ``account_id``/``transaction_id``/``obligation_id``/``income_id``.
    """

    root = payload.get("known", payload)
    if not isinstance(root, Mapping):
        raise NormalizationError("known должен быть объектом")
    as_of = _datetime(payload.get("as_of", root.get("as_of")), "as_of")
    timezone = str(payload.get("timezone", "UTC"))
    currency = str(payload.get("currency", "RUB"))

    accounts = _unique(
        (
            AccountSnapshot(
                id=_id(row, "id", "account_id"),
                type=AccountType(row["type"]),
                currency=str(row.get("currency", currency)),
                balance_minor=int(row.get("balance_minor", row.get("available_balance_minor"))),
                data_as_of=_datetime(row.get("data_as_of", as_of), "accounts.data_as_of"),
                is_liquid=bool(row.get("is_liquid", True)),
                credit_limit_minor=(
                    None
                    if row.get("credit_limit_minor") is None
                    else int(row["credit_limit_minor"])
                ),
                blocked_minor=int(row.get("blocked_minor", 0)),
            )
            for row in root.get("accounts", ())
        ),
        "accounts",
    )
    account_ids = {account.id for account in accounts}

    transactions = _unique(
        (
            HistoricalTransaction(
                id=_id(row, "id", "transaction_id")
                if row.get("transaction_id") is not None or row.get("id") is not None
                else _id(row, "id", "external_id"),
                account_id=str(row["account_id"]),
                occurred_at=_datetime(row["occurred_at"], "transactions.occurred_at"),
                amount_minor=int(row["amount_minor"]),
                type=TxType(row["type"]),
                status=TxStatus(row.get("status", "posted")),
                category=row.get("category"),
                label=row.get("label"),
                description=row.get("description"),
                obligation_id=row.get("obligation_id"),
            )
            for row in root.get("transactions", ())
        ),
        "transactions",
    )
    unknown_accounts = {tx.account_id for tx in transactions} - account_ids
    if unknown_accounts:
        raise NormalizationError(
            f"операции с неизвестными account_id: {', '.join(sorted(unknown_accounts))}"
        )

    obligations = _unique(
        (
            ObligationEvent(
                id=_id(row, "id", "obligation_id"),
                account_id=row.get("account_id"),
                due_date=_date(row["due_date"], "obligations.due_date"),
                amount_minor=int(row["amount_minor"]),
                status=ObligationStatus(row.get("status", "confirmed")),
                kind=str(row.get("kind", "manual")),
                critical=bool(row.get("critical", row.get("priority", "critical") == "critical")),
                movable=bool(row.get("movable", False)),
                amount_min_minor=(
                    None if row.get("amount_min_minor") is None else int(row["amount_min_minor"])
                ),
                amount_max_minor=(
                    None if row.get("amount_max_minor") is None else int(row["amount_max_minor"])
                ),
                recurrence=str(row.get("recurrence", "none")),
                recurrence_day=row.get("recurrence_day"),
                title=str(row.get("title", "")),
            )
            for row in root.get("obligations", ())
        ),
        "obligations",
    )
    incomes = _unique(
        (
            IncomeExpectation(
                id=_id(row, "id", "income_id"),
                account_id=row.get("account_id"),
                date_from=_date(row["date_from"], "incomes.date_from"),
                date_to=_date(row.get("date_to", row["date_from"]), "incomes.date_to"),
                amount_min_minor=int(row.get("amount_min_minor", row.get("amount_minor"))),
                amount_max_minor=int(row.get("amount_max_minor", row.get("amount_minor"))),
                probability=float(row.get("probability", 1.0)),
                confirmed=bool(row.get("confirmed", True)),
                recurrence=str(row.get("recurrence", "none")),
                title=str(row.get("title", "")),
                kind=str(row.get("kind", "other")),
            )
            for row in root.get("incomes", ())
        ),
        "incomes",
    )
    if not accounts:
        raise NormalizationError("нужен хотя бы один счёт")
    return FinancialData(
        as_of=as_of,
        timezone=timezone,
        accounts=accounts,
        transactions=transactions,
        obligations=obligations,
        incomes=incomes,
        coverage=Coverage(payload.get("coverage", "unknown")),
        currency=currency,
        notes=tuple(str(note) for note in payload.get("notes", ())),
    )
