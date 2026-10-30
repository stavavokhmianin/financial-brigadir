"""Cashflow & Risk Engine.

Независимое расчётное ядро (раздел 7 ТЗ). Пакет не импортирует FastAPI, ORM,
клиентский код или LLM: на вход получает нормализованный
:class:`ForecastInputSnapshot` и не знает, пришли данные из CSV, демо или API.
"""

from forecast_core.liquidity import liquid_balance_minor
from forecast_core.money import format_rub, parse_rub_to_minor
from forecast_core.purchase_context import PurchaseContextAnalysis, analyze_purchase_context
from forecast_core.snapshot import snapshot_fingerprint
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

__version__ = "0.1.0"

__all__ = [
    "AccountSnapshot",
    "AccountType",
    "Coverage",
    "ForecastInputSnapshot",
    "HistoricalTransaction",
    "IncomeExpectation",
    "ObligationEvent",
    "ObligationStatus",
    "PurchaseContextAnalysis",
    "TxStatus",
    "TxType",
    "analyze_purchase_context",
    "format_rub",
    "liquid_balance_minor",
    "parse_rub_to_minor",
    "snapshot_fingerprint",
]
