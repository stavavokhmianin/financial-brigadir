"""Вероятностная симуляция — уровень 2 раздела 23.1 (FR-18, раздел 9.3).

Для каждой из ``K`` траекторий разыгрываются:

* повседневные траты дня — бутстреп дневных сумм истории того же дня недели
  (сохраняет асимметрию и редкие крупные дни), плюс разовые крупные покупки с
  исторической частотой (то, что базовая модель исключает из среднего);
* доходы — поступают с вероятностью ``probability``; если пришли, то в первый
  день окна с долей ``ON_TIME_SHARE``, иначе в случайный более поздний день окна;
* неточные обязательства — сумма из диапазона ``[min, max]``; предполагаемые
  (``inferred``) случаются с вероятностью ``INFERRED_INCLUSION``.

Оценивается ``p_gap = 1/K · Σ 1{min_t (B_t,k − R_t) < 0}`` и вероятность по каждому
дню. Это **модельная** оценка: калибровка проверяется на скрытом будущем
генератора (``scripts/backtest_baseline.py``), на реальных данных — отдельно.
Результат воспроизводим: генератор случайных чисел детерминирован по ``seed``,
а сценарии считаются на тех же случайных числах, что и база.
"""

import random
from dataclasses import replace
from datetime import timedelta

from forecast_core.baseline import (
    P50_MIN_PROBABILITY,
    SHORT_HISTORY_DAYS,
    DayPoint,
    ForecastResult,
    _quantile,
    finalize,
    prepare_plan,
    run_baseline,
)
from forecast_core.types import ForecastInputSnapshot, ObligationStatus

MODEL_VERSION = "mc-0.1"
DEFAULT_SIMULATIONS = 1000
ON_TIME_SHARE = 0.6  # допущение; уточняется по истории поступлений
INFERRED_INCLUSION = 0.9
HIGH_PROBABILITY = 0.5
MEDIUM_PROBABILITY = 0.1


def run_monte_carlo(
    snapshot: ForecastInputSnapshot,
    simulations: int = DEFAULT_SIMULATIONS,
    seed: int = 0,
) -> ForecastResult:
    """Прогноз с вероятностями; при истории короче 4 недель — базовая модель (честнее)."""
    plan = prepare_plan(snapshot, "mean")
    spending = plan.spending
    if spending.history_days < SHORT_HISTORY_DAYS or not plan.liquid_ids:
        fallback = run_baseline(snapshot)
        return replace(fallback, flags=(*fallback.flags, "simulation_skipped"))

    rng = random.Random(f"mc:{seed}")  # noqa: S311 — моделирование, не криптография
    pools: list[list[int]] = [[] for _ in range(7)]
    for day, total in spending.daily_history:
        pools[day.weekday()].append(total)
    everything = [total for _, total in spending.daily_history]
    pools = [pool or everything for pool in pools]
    large = list(spending.large_amounts_minor)
    large_rate = len(large) / spending.history_days

    horizon = len(plan.days)
    reserve = snapshot.reserve_minor
    columns: list[list[int]] = [[] for _ in range(horizon)]
    trajectories: list[tuple[int, ...]] = []
    below = [0] * horizon
    gaps = 0
    weekdays = [day.weekday() for day in plan.days]

    for _ in range(simulations):
        flow = [0] * horizon
        for hit in plan.obligations:
            if hit.status == ObligationStatus.INFERRED and rng.random() > INFERRED_INCLUSION:
                continue
            low = min(hit.low_minor, hit.amount_minor)
            high = max(hit.high_minor, hit.amount_minor)
            flow[plan.index[hit.day]] -= rng.randint(low, high) if high > low else hit.amount_minor
        for income in plan.incomes:
            if rng.random() >= income.probability:
                continue
            spread = (income.last - income.first).days
            offset = 0 if spread == 0 or rng.random() < ON_TIME_SHARE else rng.randint(1, spread)
            day = income.first + timedelta(days=offset)
            if day in plan.index:
                low, high = income.min_minor, income.max_minor
                flow[plan.index[day]] += rng.randint(low, high) if high > low else low
        for day, amount, _ in plan.scenarios:
            if day in plan.index:
                flow[plan.index[day]] -= amount

        balance = plan.start
        breached = False
        path: list[int] = []
        for i in range(horizon):
            balance += flow[i] - rng.choice(pools[weekdays[i]])
            if large and rng.random() < large_rate:
                balance -= rng.choice(large)
            columns[i].append(balance)
            path.append(balance)
            if balance < reserve:
                below[i] += 1
                breached = True
        gaps += breached
        trajectories.append(tuple(path))

    expected_in = [0] * horizon
    expected_out = [0] * horizon
    for hit in plan.obligations:
        expected_out[plan.index[hit.day]] += hit.amount_minor
    for income in plan.incomes:
        if income.probability >= P50_MIN_PROBABILITY and income.first in plan.index:
            expected_in[plan.index[income.first]] += (income.min_minor + income.max_minor) // 2
    for day, amount, _ in plan.scenarios:
        if day in plan.index:
            expected_out[plan.index[day]] += amount

    points: list[DayPoint] = []
    for i, day in enumerate(plan.days):
        values = sorted(columns[i])
        points.append(
            DayPoint(
                day=day,
                p10_minor=_quantile(values, 0.1),
                p50_minor=_quantile(values, 0.5),
                p90_minor=_quantile(values, 0.9),
                inflow_minor=expected_in[i],
                outflow_minor=expected_out[i],
                spending_minor=spending.daily(day),
                risk_probability=round(below[i] / simulations, 3),
            )
        )

    gap_probability = round(gaps / simulations, 3)
    if gap_probability >= HIGH_PROBABILITY:
        level, threshold = "high", HIGH_PROBABILITY
    elif gap_probability >= MEDIUM_PROBABILITY:
        level, threshold = "medium", MEDIUM_PROBABILITY
    else:
        level, threshold = "low", 1.1
    risk_date = next((p.day for p in points if (p.risk_probability or 0) >= threshold), None)
    if level == "high":
        shortfall = reserve - min(p.p50_minor for p in points)
    elif level == "medium":
        shortfall = reserve - min(p.p10_minor for p in points)
    else:
        shortfall = 0
    return finalize(
        plan,
        points,
        level,
        risk_date,
        shortfall,
        MODEL_VERSION,
        gap_probability,
        tuple(trajectories),
    )
