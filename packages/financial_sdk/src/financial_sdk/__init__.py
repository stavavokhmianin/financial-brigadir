"""Financial SDK — публичная граница финансовой логики.

Пакет не импортирует FastAPI, ORM, UI или конкретный банк. ``forecast_core``
остаётся внутренним математическим engine и доступен через совместимые re-export'ы,
пока интеграции переходят на фасад ``FinancialEngine``.
"""

from financial_sdk.adapters import (
    AdapterRegistry,
    AsyncDataAdapter,
    BankConnector,
    ConsentToken,
    CSVColumns,
    CSVTransactionsAdapter,
    DataAdapter,
    InMemoryAdapter,
    OpenBankingAdapter,
    SourceAccount,
    SourceBalance,
    SourcePage,
    SourceTransaction,
)
from financial_sdk.engine import FinancialEngine, FinancialSDK
from financial_sdk.models import (
    FinancialData,
    ForecastModel,
    ForecastOptions,
    ForecastReport,
    Scenario,
    ScenarioReport,
)
from financial_sdk.normalization import NormalizationError, normalize_financial_data
from financial_sdk.serialization import dumps, to_jsonable
from forecast_core import (
    AccountSnapshot,
    AccountType,
    Coverage,
    ForecastInputSnapshot,
    HistoricalTransaction,
    IncomeExpectation,
    ObligationEvent,
    ObligationStatus,
    PurchaseContextAnalysis,
    TxStatus,
    TxType,
    analyze_purchase_context,
    format_rub,
    liquid_balance_minor,
    parse_rub_to_minor,
    snapshot_fingerprint,
)
from forecast_core.baseline import (
    DEFAULT_OBLIGATION_CATEGORIES,
    HISTORY_WINDOW_DAYS,
    DayPoint,
    ForecastResult,
    RiskDriver,
    SpendingModel,
    run_baseline,
)
from forecast_core.calendar import Recurrence, occurrences
from forecast_core.probabilistic import MODEL_VERSION as PROBABILISTIC_MODEL_VERSION
from forecast_core.probabilistic import run_monte_carlo
from forecast_core.recurring import (
    WINDOW_DAYS,
    RecurringCandidate,
    detect_recurring,
    merchant_key,
)
from forecast_core.scenarios import SafeSpend, ScenarioComparison, compare, safe_to_spend
from forecast_core.types import IncomeShift, ScenarioExpense

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_OBLIGATION_CATEGORIES",
    "HISTORY_WINDOW_DAYS",
    "PROBABILISTIC_MODEL_VERSION",
    "WINDOW_DAYS",
    "AccountSnapshot",
    "AccountType",
    "AdapterRegistry",
    "AsyncDataAdapter",
    "BankConnector",
    "CSVColumns",
    "CSVTransactionsAdapter",
    "ConsentToken",
    "Coverage",
    "DataAdapter",
    "DayPoint",
    "FinancialData",
    "FinancialEngine",
    "FinancialSDK",
    "ForecastInputSnapshot",
    "ForecastModel",
    "ForecastOptions",
    "ForecastReport",
    "ForecastResult",
    "HistoricalTransaction",
    "InMemoryAdapter",
    "IncomeExpectation",
    "IncomeShift",
    "NormalizationError",
    "ObligationEvent",
    "ObligationStatus",
    "OpenBankingAdapter",
    "PurchaseContextAnalysis",
    "Recurrence",
    "RecurringCandidate",
    "RiskDriver",
    "SafeSpend",
    "Scenario",
    "ScenarioComparison",
    "ScenarioExpense",
    "ScenarioReport",
    "SourceAccount",
    "SourceBalance",
    "SourcePage",
    "SourceTransaction",
    "SpendingModel",
    "TxStatus",
    "TxType",
    "analyze_purchase_context",
    "compare",
    "detect_recurring",
    "dumps",
    "format_rub",
    "liquid_balance_minor",
    "merchant_key",
    "normalize_financial_data",
    "occurrences",
    "parse_rub_to_minor",
    "run_baseline",
    "run_monte_carlo",
    "safe_to_spend",
    "snapshot_fingerprint",
    "to_jsonable",
]
