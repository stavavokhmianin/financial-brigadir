"""Публичные типы фасада SDK.

Расчётные структуры остаются неизменяемыми dataclass из ``forecast_core``. Этот
модуль добавляет стабильный вход верхнего уровня и результаты use-case'ов, не
привязанные к HTTP, ORM или конкретному источнику данных.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from typing import cast

from forecast_core import (
    AccountSnapshot,
    Coverage,
    ForecastInputSnapshot,
    HistoricalTransaction,
    IncomeExpectation,
    ObligationEvent,
)
from forecast_core.baseline import ForecastResult
from forecast_core.scenarios import SafeSpend, ScenarioComparison
from forecast_core.types import IncomeShift, ScenarioExpense


class ForecastModel(StrEnum):
    """Стратегия расчёта.

    ``AUTO`` и ``MONTE_CARLO`` используют ``mc-0.3``; само ядро честно
    откатывается на ``baseline-0.2``, если истории меньше четырёх недель.
    """

    AUTO = "auto"
    BASELINE = "baseline"
    MONTE_CARLO = "monte_carlo"


@dataclass(frozen=True, slots=True)
class FinancialData:
    """Нормализованные финансовые данные без параметров конкретного прогноза."""

    as_of: datetime
    timezone: str
    accounts: tuple[AccountSnapshot, ...]
    transactions: tuple[HistoricalTransaction, ...] = ()
    obligations: tuple[ObligationEvent, ...] = ()
    incomes: tuple[IncomeExpectation, ...] = ()
    coverage: Coverage = Coverage.UNKNOWN
    currency: str = "RUB"
    notes: tuple[str, ...] = ()

    def snapshot(
        self,
        *,
        horizon_days: int = 30,
        reserve_minor: int = 0,
        expenses: tuple[ScenarioExpense, ...] = (),
        income_shifts: tuple[IncomeShift, ...] = (),
    ) -> ForecastInputSnapshot:
        if not 1 <= horizon_days <= 365:
            raise ValueError("horizon_days должен быть от 1 до 365")
        if reserve_minor < 0:
            raise ValueError("reserve_minor не может быть отрицательным")
        return ForecastInputSnapshot(
            as_of=self.as_of,
            timezone=self.timezone,
            horizon_days=horizon_days,
            reserve_minor=reserve_minor,
            accounts=self.accounts,
            obligations=self.obligations,
            incomes=self.incomes,
            history=self.transactions,
            coverage=self.coverage,
            currency=self.currency,
            notes=self.notes,
            extra_expenses=expenses,
            income_shifts=income_shifts,
        )


@dataclass(frozen=True, slots=True)
class ForecastOptions:
    """Параметры одного воспроизводимого расчёта."""

    model: ForecastModel = ForecastModel.AUTO
    horizon_days: int | None = None
    reserve_minor: int | None = None
    simulations: int = 1000
    seed: int = 0
    safe_spend_day: date | None = None

    def __post_init__(self) -> None:
        if self.horizon_days is not None and not 1 <= self.horizon_days <= 365:
            raise ValueError("horizon_days должен быть от 1 до 365")
        if self.reserve_minor is not None and self.reserve_minor < 0:
            raise ValueError("reserve_minor не может быть отрицательным")
        if self.simulations < 1:
            raise ValueError("simulations должен быть положительным")


@dataclass(frozen=True, slots=True)
class Scenario:
    """Изменения для what-if без записи в исходную историю."""

    expenses: tuple[ScenarioExpense, ...] = ()
    income_shifts: tuple[IncomeShift, ...] = ()

    def __post_init__(self) -> None:
        if not self.expenses and not self.income_shifts:
            raise ValueError("сценарий должен содержать хотя бы одно изменение")


@dataclass(frozen=True, slots=True)
class ForecastReport:
    """Прогноз и рассчитанная на нём безопасная сумма."""

    result: ForecastResult
    safe_to_spend: SafeSpend
    requested_model: ForecastModel

    @property
    def model_version(self) -> str:
        return self.result.model_version

    def to_dict(self, *, include_internal: bool = False) -> dict[str, object]:
        from financial_sdk.serialization import to_jsonable

        return cast(
            dict[str, object],
            to_jsonable(self, include_internal=include_internal),
        )


@dataclass(frozen=True, slots=True)
class ScenarioReport:
    """Сравнение исходного и изменённого будущего на одинаковом seed."""

    base: ForecastReport
    scenario: ForecastReport
    comparison: ScenarioComparison

    def to_dict(self, *, include_internal: bool = False) -> dict[str, object]:
        from financial_sdk.serialization import to_jsonable

        return cast(
            dict[str, object],
            to_jsonable(self, include_internal=include_internal),
        )


def with_options(
    source: FinancialData | ForecastInputSnapshot,
    options: ForecastOptions,
) -> ForecastInputSnapshot:
    """Привести оба поддерживаемых входа к одному снимку ядра."""

    if isinstance(source, FinancialData):
        return source.snapshot(
            horizon_days=options.horizon_days or 30,
            reserve_minor=options.reserve_minor or 0,
        )
    return replace(
        source,
        horizon_days=options.horizon_days or source.horizon_days,
        reserve_minor=(
            source.reserve_minor if options.reserve_minor is None else options.reserve_minor
        ),
    )
