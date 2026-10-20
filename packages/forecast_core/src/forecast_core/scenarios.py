"""Сравнение сценариев и сумма условно безопасной покупки (разделы 7.6, 9.4, 23.3).

Разовая покупка ``x`` в день ``d`` уменьшает остаток каждой траектории ровно на
``x`` начиная с ``d`` (траты и доходы от неё не зависят). Поэтому граница
считается без перебора.

* Детерминированная модель: ``x* = min_{t ≥ d} (B_t − R_t)`` для базового и
  пессимистичного сценария.
* Симуляция — формула 9.4: максимальный ``x``, при котором доля траекторий с
  ``min_t (B_t − x·[t ≥ d] − R_t) < 0`` остаётся ниже порога. Порог 50 % даёт
  «можно потратить» (риск не становится высоким), 10 % — «с запасом».

Возвращается диапазон, а при недостатке данных — отказ (раздел 9.4).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from forecast_core.baseline import ForecastResult

LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}
BASE_RISK_LIMIT = 0.5  # совпадает с порогом уровня high у симуляции
CAREFUL_RISK_LIMIT = 0.1  # совпадает с порогом уровня medium


@dataclass(frozen=True, slots=True)
class SafeSpend:
    day: date
    base_minor: int  # покупка не делает риск высоким
    conservative_minor: int  # покупка не создаёт даже умеренного риска
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
    gap_probability_before: float | None = None
    gap_probability_after: float | None = None

    @property
    def worsened(self) -> bool:
        return LEVEL_ORDER[self.risk_level_after] > LEVEL_ORDER[self.risk_level_before]

    @property
    def delta_risk(self) -> float | None:
        if self.gap_probability_before is None or self.gap_probability_after is None:
            return None
        return round(self.gap_probability_after - self.gap_probability_before, 3)


def _limit_from_trajectories(
    trajectories: tuple[tuple[int, ...], ...], start_index: int, reserve: int, limit: float
) -> int:
    """Максимальная покупка, при которой доля траекторий с нарушением < ``limit``."""
    allowed = limit * len(trajectories)
    already = 0  # нарушение до дня покупки от неё не зависит
    suffix_mins: list[int] = []
    for path in trajectories:
        if any(value < reserve for value in path[:start_index]):
            already += 1
            continue
        suffix_mins.append(min(path[start_index:]) - reserve)
    if already >= allowed:
        return 0
    suffix_mins.sort()
    # Покупка x нарушает резерв в тех траекториях, где запас < x (строго).
    room = int(allowed - already)
    if room * 1.0 == allowed - already:
        room -= 1  # доля должна остаться строго ниже порога
    if room < 0 or not suffix_mins:
        return 0
    return max(0, suffix_mins[min(room, len(suffix_mins) - 1)])


def safe_to_spend(result: ForecastResult, day: date | None = None) -> SafeSpend:
    """Сколько можно потратить в ``day`` (по умолчанию — завтра), не нарушая резерв."""
    target = day or result.today + timedelta(days=1)
    start_index = next(
        (i for i, p in enumerate(result.points) if p.day >= target), len(result.points)
    )
    window = result.points[start_index:]
    available = result.confidence != "insufficient" and bool(window)
    reserve = result.reserve_minor
    if not window:
        return SafeSpend(target, 0, 0, available=False)
    if result.trajectories:
        base = _limit_from_trajectories(result.trajectories, start_index, reserve, BASE_RISK_LIMIT)
        careful = _limit_from_trajectories(
            result.trajectories, start_index, reserve, CAREFUL_RISK_LIMIT
        )
    else:
        base = max(0, min(p.p50_minor for p in window) - reserve)
        careful = max(0, min(p.p10_minor for p in window) - reserve)
    return SafeSpend(target, base, min(careful, base), available)


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
        gap_probability_before=base.gap_probability,
        gap_probability_after=scenario.gap_probability,
    )
