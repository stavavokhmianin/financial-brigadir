"""Типы входного снимка расчёта (раздел 22.1 ТЗ: ``ForecastInputSnapshot``).

Снимок неизменяем: сценарий — это копия снимка с добавленным событием,
исходные операции не переписываются (раздел 7.6).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class AccountType(StrEnum):
    DEBIT = "debit"
    CREDIT_CARD = "credit_card"
    SAVINGS = "savings"
    DEPOSIT = "deposit"
    CASH = "cash"


class TxType(StrEnum):
    """Экономический тип операции (FR-09)."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    REFUND = "refund"
    CREDIT_PURCHASE = "credit_purchase"
    CREDIT_PAYMENT = "credit_payment"
    FEE = "fee"


class TxStatus(StrEnum):
    POSTED = "posted"
    PENDING = "pending"
    CANCELED = "canceled"


class ObligationStatus(StrEnum):
    """Статус будущего события (раздел 7.4)."""

    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNCERTAIN = "uncertain"
    CANCELED = "canceled"


class Coverage(StrEnum):
    """Полнота охвата счетов пользователя (раздел 13.2)."""

    FULL = "full"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    id: str
    type: AccountType
    currency: str
    balance_minor: int
    data_as_of: datetime
    is_liquid: bool = True
    credit_limit_minor: int | None = None
    blocked_minor: int = 0


@dataclass(frozen=True, slots=True)
class HistoricalTransaction:
    id: str
    account_id: str
    occurred_at: datetime
    amount_minor: int
    type: TxType
    status: TxStatus
    category: str | None = None
    # Метка пользователя (ADR-0007): mandatory | regular | reducible | one_off.
    label: str | None = None
    description: str | None = None
    # Платёж по подтверждённому обязательству: он уже в календаре, в модель трат не идёт.
    obligation_id: str | None = None


@dataclass(frozen=True, slots=True)
class ObligationEvent:
    id: str
    account_id: str | None
    due_date: date
    amount_minor: int
    status: ObligationStatus
    kind: str
    critical: bool = True
    movable: bool = False
    amount_min_minor: int | None = None
    amount_max_minor: int | None = None
    recurrence: str = "none"
    recurrence_day: int | None = None
    title: str = ""


@dataclass(frozen=True, slots=True)
class IncomeExpectation:
    id: str
    account_id: str | None
    date_from: date
    date_to: date
    amount_min_minor: int
    amount_max_minor: int
    probability: float
    confirmed: bool
    recurrence: str = "none"
    title: str = ""
    kind: str = "other"


@dataclass(frozen=True, slots=True)
class ScenarioExpense:
    """Гипотетическая трата (US-04): не записывается в историю операций."""

    day: date
    amount_minor: int
    label: str = "Покупка"


@dataclass(frozen=True, slots=True)
class IncomeShift:
    """Сдвиг ожидаемого дохода на N дней (US-05, демо 16.4: «зарплата на два дня позже»)."""

    income_id: str
    shift_days: int


@dataclass(frozen=True, slots=True)
class ForecastInputSnapshot:
    as_of: datetime
    timezone: str
    horizon_days: int
    reserve_minor: int
    accounts: tuple[AccountSnapshot, ...]
    obligations: tuple[ObligationEvent, ...] = ()
    incomes: tuple[IncomeExpectation, ...] = ()
    history: tuple[HistoricalTransaction, ...] = ()
    coverage: Coverage = Coverage.UNKNOWN
    currency: str = "RUB"
    notes: tuple[str, ...] = field(default=())
    extra_expenses: tuple[ScenarioExpense, ...] = ()
    income_shifts: tuple[IncomeShift, ...] = ()
