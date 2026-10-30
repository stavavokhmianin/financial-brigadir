from enum import StrEnum

from forecast_core import AccountType, Coverage, ObligationStatus, TxStatus, TxType
from forecast_core.calendar import Recurrence

__all__ = [
    "AccountType",
    "AlertAction",
    "CategorySource",
    "Coverage",
    "DataSourceKind",
    "ImportStatus",
    "IncomeKind",
    "NotificationMode",
    "ObligationKind",
    "ObligationStatus",
    "Plan",
    "Priority",
    "Recurrence",
    "TxLabel",
    "TxStatus",
    "TxType",
]


class TxLabel(StrEnum):
    """Смысл траты со слов пользователя (ADR-0007). Баланс и история от метки не зависят."""

    MANDATORY = "mandatory"  # нельзя просто убрать
    REGULAR = "regular"  # обычная часть поведения
    REDUCIBLE = "reducible"  # реальная, но хотелось бы меньше
    ONE_OFF = "one_off"  # повторения не ждать: в обучение ритму не идёт


class Plan(StrEnum):
    """Логическое разделение функций Free/Plus (FR-28)."""

    FREE = "free"
    PLUS = "plus"


class DataSourceKind(StrEnum):
    SYNTHETIC = "synthetic"
    CSV = "csv"
    MANUAL = "manual"
    BANK_MOCK = "bank_mock"


class CategorySource(StrEnum):
    SOURCE = "source"
    RULE = "rule"
    MANUAL = "manual"


class ObligationKind(StrEnum):
    RENT = "rent"
    LOAN = "loan"
    CREDIT_CARD = "credit_card"
    UTILITIES = "utilities"
    SUBSCRIPTION = "subscription"
    INSTALLMENT = "installment"
    MANUAL = "manual"


class Priority(StrEnum):
    CRITICAL = "critical"
    NORMAL = "normal"


class IncomeKind(StrEnum):
    SALARY = "salary"
    ADVANCE = "advance"
    FREELANCE = "freelance"
    OTHER = "other"


class ImportStatus(StrEnum):
    PREVIEW = "preview"
    IMPORTED = "imported"
    REJECTED = "rejected"


class AlertAction(StrEnum):
    """Решение Alert Policy Engine (раздел 7.7)."""

    SEND = "send"
    DEFER = "defer"
    SUPPRESS = "suppress"


class NotificationMode(StrEnum):
    QUIET = "quiet"
    SMART = "smart"
    ACTIVE = "active"
