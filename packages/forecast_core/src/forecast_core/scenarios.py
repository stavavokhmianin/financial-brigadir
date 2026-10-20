"""Сравнение сценариев и сумма условно безопасной покупки (разделы 7.6, 9.4, 23.3).

Разовая покупка ``x`` в день ``d`` уменьшает остаток всех трёх сценариев ровно на
``x`` начиная с ``d`` (траты и доходы от неё не зависят). Поэтому максимальная
покупка, не нарушающая резерв, считается без перебора:
``x* = min_{t ≥ d} (B_t − R_t)``. Для базового сценария это «можно потратить»,
для пессимистичного — «осторожная» оценка. Вместо одной «безопасной суммы»
возвращается диапазон, а при недостатке данных — отказ (раздел 9.4).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from forecast_core.baseline import ForecastResult

LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True, slots=True)
class SafeSpend:
    day: date
    base_minor: int  # покупка не опускает базовый сценарий ниже резерва
    conservative_minor: int  # не опускает даже пессимистичный сценарий
    available: bool  # False — данных недостаточно, сумму не показываем


@dataclass(frozen=True, slots=True)
class ScenarioComparison:
    min_balance_delta_minor: int
    pessimistic_min_delta_minor: int
    risk_level_before: str
    risk_level_after: str
    risk_date_before: date | None
    risk_date_after: date | None
    days_below_reserve_before: int
    days_below_reserve_after: int

    @property
    def worsened(self) -> bool:
        return LEVEL_ORDER[self.risk_level_after] > LEVEL_ORDER[self.risk_level_before]


def safe_to_spend(result: ForecastResult, day: date | None = None) -> SafeSpend:
    """Сколько можно потратить в ``day`` (по умолчанию — завтра), не нарушая резерв."""
    target = day or result.today + timedelta(days=1)
    window = (
        [p for p in result.points if p.day >= target]
        if target > result.today
        else list(result.points)
    )
    reserve = result.reserve_minor
    if not window:
        return SafeSpend(target, 0, 0, available=False)
    base = max(0, min(p.p50_minor for p in window) - reserve)
    conservative = max(0, min(p.p10_minor for p in window) - reserve)
    return SafeSpend(
        day=target,
        base_minor=base,
        conservative_minor=min(conservative, base),
        available=result.confidence != "insufficient",
    )


def _below(result: ForecastResult) -> int:
    return sum(1 for p in result.points if p.p50_minor < result.reserve_minor)


def compare(base: ForecastResult, scenario: ForecastResult) -> ScenarioComparison:
    if base.reserve_minor != scenario.reserve_minor or len(base.points) != len(scenario.points):
        raise ValueError("сценарии сравниваются при одинаковых резерве и горизонте")
    return ScenarioComparison(
        min_balance_delta_minor=scenario.min_p50_minor - base.min_p50_minor,
        pessimistic_min_delta_minor=scenario.min_p10_minor - base.min_p10_minor,
        risk_level_before=base.risk_level,
        risk_level_after=scenario.risk_level,
        risk_date_before=base.risk_date,
        risk_date_after=scenario.risk_date,
        days_below_reserve_before=_below(base),
        days_below_reserve_after=_below(scenario),
    )
