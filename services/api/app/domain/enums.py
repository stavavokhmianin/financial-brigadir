from enum import StrEnum

from forecast_core import AccountType, Coverage, ObligationStatus, TxStatus, TxType

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
    "TxStatus",
    "TxType",
]


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


class Recurrence(StrEnum):
    NONE = "none"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


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
