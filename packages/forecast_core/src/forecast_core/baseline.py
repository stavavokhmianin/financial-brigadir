"""Базовый прогноз остатка по дням: уровни 0 и 1 раздела 23.1.

* Уровень 0 — достоверный календарь: текущий ликвидный остаток, подтверждённые
  и ожидаемые доходы и обязательства по датам. Работает и без истории.
* Уровень 1 — статистическая база: медиана повседневных трат по дням недели
  (раздел 9.2). Из истории исключаются переводы между своими счетами, возвраты,
  погашения кредитки, оплаты обязательств и аномально крупные покупки.

Коридор p10/p90 — не вероятность, а сценарии: пессимистичный (траты на уровне
90-го перцентиля исторических скользящих сумм, доход в последний день окна,
верхняя граница неточных платежей) и оптимистичный. Вероятность нарушения
резерва появится вместе с симуляцией (уровень 2) и калибровкой; до этого
результат помечается как иллюстративный.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from statistics import mean, median
from typing import Literal
from zoneinfo import ZoneInfo

from forecast_core.calendar import occurrences
from forecast_core.liquidity import liquid_balance_minor
from forecast_core.types import (
    AccountType,
    Coverage,
    ForecastInputSnapshot,
    HistoricalTransaction,
    IncomeExpectation,
    ObligationStatus,
    TxStatus,
    TxType,
)

MODEL_VERSION = "baseline-0.1"
HISTORY_WINDOW_DAYS = 91
SHORT_HISTORY_DAYS = 28
MIN_HISTORY_DAYS = 7
SHORT_HISTORY_WIDENING = 1.5
LARGE_TX_FACTOR = 15
LARGE_TX_FLOOR_MINOR = 1_000_000  # 10 000 ₽
DEFAULT_OBLIGATION_CATEGORIES = frozenset(
    {
        "rent", "loan", "utilities", "subscription", "installment", "credit_card",
        "credit_card_payment", "tax", "mortgage",
    }
)  # fmt: skip
SPENDING_TYPES = frozenset({TxType.EXPENSE, TxType.FEE})
LIQUID_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS})

# Пороги включения дохода в сценарий по вероятности поступления.
P50_MIN_PROBABILITY = 0.5
P10_MIN_PROBABILITY = 0.9
P90_MIN_PROBABILITY = 0.3


Estimator = Literal["mean", "median"]


@dataclass(frozen=True, slots=True)
class SpendingModel:
    estimator: str  # mean — модель; median — baseline B раздела 15.2
    weekday_daily_minor: tuple[int, ...]  # ожидаемые траты по дню недели, понедельник = 0
    history_days: int
    excluded_large: int
    excluded_obligation_like: int
    band_low_minor: tuple[int, ...]  # насколько траты за k дней могут быть ниже p50
    band_high_minor: tuple[int, ...]  # и выше p50
    card_daily_minor: int

    def daily(self, day: date) -> int:
        return self.weekday_daily_minor[day.weekday()]


@dataclass(frozen=True, slots=True)
class DayPoint:
    day: date
    p10_minor: int
    p50_minor: int
    p90_minor: int
    inflow_minor: int
    outflow_minor: int
    spending_minor: int


@dataclass(frozen=True, slots=True)
class RiskDriver:
    kind: str  # obligation | daily_spending | scenario | income_after_risk
    code: str
    label: str
    amount_minor: int
    day: date | None


@dataclass(frozen=True, slots=True)
class ForecastResult:
    model_version: str
    today: date
    start_balance_minor: int
    reserve_minor: int
    points: tuple[DayPoint, ...]
    risk_level: str  # low | medium | high
    risk_date: date | None
    shortfall_minor: int
    min_p50_minor: int
    min_p50_day: date
    min_p10_minor: int
    min_p10_day: date
    drivers: tuple[RiskDriver, ...]
    next_income_day: date | None
    confidence: str  # insufficient | illustrative
    flags: tuple[str, ...]
    spending: SpendingModel


def _quantile(sorted_values: Sequence[int], p: float) -> int:
    if not sorted_values:
        return 0
    index = round(p * (len(sorted_values) - 1))
    return sorted_values[index]


def _local_date(tx: HistoricalTransaction, tz: ZoneInfo) -> date:
    return tx.occurred_at.astimezone(tz).date()


def build_spending_model(
    history: Iterable[HistoricalTransaction],
    liquid_ids: set[str],
    card_ids: set[str],
    obligation_categories: set[str],
    today: date,
    tz: ZoneInfo,
    horizon_days: int,
    estimator: Estimator = "mean",
) -> SpendingModel:
    window_start = today - timedelta(days=HISTORY_WINDOW_DAYS)
    candidates: list[tuple[date, int]] = []
    card_daily: dict[date, int] = {}
    earliest: date | None = None
    excluded_obligation_like = 0
    for tx in history:
        if tx.status != TxStatus.POSTED:
            continue
        day = _local_date(tx, tz)
        if not window_start <= day < today:
            continue
        if tx.account_id in card_ids and tx.type == TxType.CREDIT_PURCHASE and tx.amount_minor < 0:
            card_daily[day] = card_daily.get(day, 0) - tx.amount_minor
        if tx.account_id not in liquid_ids:
            continue
        earliest = day if earliest is None or day < earliest else earliest
        if tx.type not in SPENDING_TYPES or tx.amount_minor >= 0:
            continue
        if tx.category and tx.category in obligation_categories:
            excluded_obligation_like += 1
            continue
        candidates.append((day, -tx.amount_minor))

    history_days = (today - earliest).days if earliest else 0
    typical = median([amount for _, amount in candidates]) if candidates else 0
    threshold = max(LARGE_TX_FLOOR_MINOR, int(typical * LARGE_TX_FACTOR))
    days = [earliest + timedelta(days=i) for i in range(history_days)] if earliest else []
    totals = dict.fromkeys(days, 0)
    excluded_large = 0
    for day, amount in candidates:
        if amount > threshold:
            excluded_large += 1
            continue
        totals[day] = totals.get(day, 0) + amount
    daily = [totals[d] for d in days]

    by_weekday: list[list[int]] = [[] for _ in range(7)]
    for day in days:
        by_weekday[day.weekday()].append(totals[day])
    center = mean if estimator == "mean" else median
    overall = int(center(daily)) if daily else 0
    weekday_daily = tuple(int(center(values)) if values else overall for values in by_weekday)

    # Коридор: квантили сумм за k подряд идущих дней истории (скользящее окно).
    prefix = [0]
    for value in daily:
        prefix.append(prefix[-1] + value)
    low: list[int] = []
    high: list[int] = []
    widening = SHORT_HISTORY_WIDENING if history_days < SHORT_HISTORY_DAYS else 1.0
    last_valid: tuple[int, int, int] | None = None
    for k in range(1, horizon_days + 1):
        if k <= len(daily):
            sums = sorted(prefix[i + k] - prefix[i] for i in range(len(daily) - k + 1))
            q10, q90 = _quantile(sums, 0.1), _quantile(sums, 0.9)
            middle = int(center(sums))
            dev_low, dev_high = max(0, middle - q10), max(0, q90 - middle)
            last_valid = (k, dev_low, dev_high)
        elif last_valid is not None:
            base_k, base_low, base_high = last_valid
            scale = math.sqrt(k / base_k)
            dev_low, dev_high = int(base_low * scale), int(base_high * scale)
        else:
            dev_low = dev_high = 0
        low.append(int(dev_low * widening))
        high.append(int(dev_high * widening))

    card_mean = int(sum(card_daily.values()) / history_days) if history_days else 0
    return SpendingModel(
        estimator=estimator,
        weekday_daily_minor=weekday_daily,
        history_days=history_days,
        excluded_large=excluded_large,
        excluded_obligation_like=excluded_obligation_like,
        band_low_minor=tuple(low),
        band_high_minor=tuple(high),
        card_daily_minor=card_mean,
    )


def _shifted(
    incomes: Iterable[IncomeExpectation], snapshot: ForecastInputSnapshot
) -> list[IncomeExpectation]:
    shifts = {s.income_id: s.shift_days for s in snapshot.income_shifts}
    result = []
    for income in incomes:
        days = shifts.get(income.id, 0)
        if days:
            delta = timedelta(days=days)
            income = replace(
                income, date_from=income.date_from + delta, date_to=income.date_to + delta
            )
        result.append(income)
    return result


def run_baseline(snapshot: ForecastInputSnapshot, estimator: Estimator = "mean") -> ForecastResult:
    """Прогноз на ``horizon_days`` дней вперёд от даты ``as_of`` (без сегодняшнего дня)."""
    tz = ZoneInfo(snapshot.timezone)
    today = snapshot.as_of.astimezone(tz).date()
    horizon = snapshot.horizon_days
    end = today + timedelta(days=horizon)
    days = [today + timedelta(days=i) for i in range(1, horizon + 1)]
    index = {day: i for i, day in enumerate(days)}

    liquid_ids = {a.id for a in snapshot.accounts if a.type in LIQUID_TYPES and a.is_liquid}
    card_ids = {a.id for a in snapshot.accounts if a.type == AccountType.CREDIT_CARD}
    obligation_categories = set(DEFAULT_OBLIGATION_CATEGORIES) | {
        o.kind for o in snapshot.obligations
    }
    spending = build_spending_model(
        snapshot.history, liquid_ids, card_ids, obligation_categories, today, tz, horizon, estimator
    )
    start = liquid_balance_minor(snapshot.accounts, snapshot.currency)
    flags: list[str] = []

    # Потоки по дням для трёх сценариев: 0 — p10 (плохой), 1 — p50, 2 — p90 (хороший).
    inflow = [[0] * horizon for _ in range(3)]
    outflow = [[0] * horizon for _ in range(3)]
    obligation_hits: list[tuple[date, int, str, str]] = []  # (день, сумма p50, код, подпись)

    for obligation in snapshot.obligations:
        if obligation.status == ObligationStatus.CANCELED:
            continue
        base = obligation.amount_minor
        low = obligation.amount_min_minor or base
        high = obligation.amount_max_minor or base
        for day in occurrences(
            obligation.due_date,
            obligation.recurrence,
            today + timedelta(days=1),
            end,
            obligation.recurrence_day,
        ):
            amount50, amount_bad, amount_good = base, high, low
            if obligation.kind == "credit_card" and spending.card_daily_minor > 0:
                # Траты по кредитке до даты платежа увеличат сумму погашения (9.5).
                accrual = spending.card_daily_minor * (day - today).days
                amount50 = base + accrual
                amount_bad = max(high, amount50)
                if "card_spending_accrual" not in flags:
                    flags.append("card_spending_accrual")
            i = index[day]
            outflow[0][i] += amount_bad
            outflow[1][i] += amount50
            outflow[2][i] += amount_good
            obligation_hits.append(
                (day, amount50, obligation.kind, obligation.title or obligation.kind)
            )

    income_days_p50: list[tuple[date, str]] = []
    for income in _shifted(snapshot.incomes, snapshot):
        spread = income.date_to - income.date_from
        middle = (income.amount_min_minor + income.amount_max_minor) // 2
        for first in occurrences(income.date_from, income.recurrence, today - spread, end):
            last = first + spread
            if income.probability >= P50_MIN_PROBABILITY and first in index:
                inflow[1][index[first]] += middle
                income_days_p50.append((first, income.title or income.kind))
            if income.probability >= P10_MIN_PROBABILITY and last in index:
                inflow[0][index[last]] += income.amount_min_minor
            if income.probability >= P90_MIN_PROBABILITY and first in index:
                inflow[2][index[first]] += income.amount_max_minor

    scenario_hits: list[tuple[date, int, str]] = []
    for expense in snapshot.extra_expenses:
        if expense.day in index:
            for band in range(3):
                outflow[band][index[expense.day]] += expense.amount_minor
            scenario_hits.append((expense.day, expense.amount_minor, expense.label))
        elif today >= expense.day:
            # Покупка сегодня (или «прямо сейчас») сразу уменьшает остаток.
            start -= expense.amount_minor
            scenario_hits.append((today, expense.amount_minor, expense.label))

    points: list[DayPoint] = []
    cum_in = [0, 0, 0]
    cum_out = [0, 0, 0]
    cum_spend = 0
    for i, day in enumerate(days):
        for band in range(3):
            cum_in[band] += inflow[band][i]
            cum_out[band] += outflow[band][i]
        spend_today = spending.daily(day)
        cum_spend += spend_today
        p50 = start + cum_in[1] - cum_out[1] - cum_spend
        p10 = start + cum_in[0] - cum_out[0] - (cum_spend + spending.band_high_minor[i])
        p90 = start + cum_in[2] - cum_out[2] - max(0, cum_spend - spending.band_low_minor[i])
        p10 = min(p10, p50)
        p90 = max(p90, p50)
        points.append(DayPoint(day, p10, p50, p90, inflow[1][i], outflow[1][i], spend_today))

    reserve = snapshot.reserve_minor
    if points:
        min50 = min(points, key=lambda p: (p.p50_minor, p.day))
        min10 = min(points, key=lambda p: (p.p10_minor, p.day))
        min50_value, min50_day = min50.p50_minor, min50.day
        min10_value, min10_day = min10.p10_minor, min10.day
    else:
        min50_value = min10_value = start
        min50_day = min10_day = today
    breach50 = next((p.day for p in points if p.p50_minor < reserve), None)
    breach10 = next((p.day for p in points if p.p10_minor < reserve), None)
    if breach50 is not None:
        level, risk_date, shortfall = "high", breach50, reserve - min50_value
    elif breach10 is not None:
        level, risk_date, shortfall = "medium", breach10, reserve - min10_value
    else:
        level, risk_date, shortfall = "low", None, 0

    target = risk_date or min50_day
    drivers: list[RiskDriver] = []
    before = sorted(
        (hit for hit in obligation_hits if hit[0] <= target), key=lambda h: (-h[1], h[0])
    )
    for day, amount, code, label in before[:3]:
        drivers.append(RiskDriver("obligation", code, label, amount, day))
    for day, amount, label in scenario_hits:
        if day <= target:
            drivers.append(RiskDriver("scenario", "scenario_expense", label, amount, day))
    spend_until = sum(p.spending_minor for p in points if p.day <= target)
    if spend_until > 0:
        drivers.append(
            RiskDriver("daily_spending", "daily_spending", "Повседневные траты", spend_until, None)
        )
    later_income = min((d for d, _ in income_days_p50 if d > target), default=None)
    next_income = min((d for d, _ in income_days_p50), default=None)
    if later_income is not None and level != "low":
        title = next(t for d, t in income_days_p50 if d == later_income)
        drivers.append(RiskDriver("income_after_risk", "income_after_risk", title, 0, later_income))

    if spending.history_days == 0:
        flags.append("no_history")
    elif spending.history_days < SHORT_HISTORY_DAYS:
        flags.append("short_history")
    if spending.excluded_large:
        flags.append("large_expenses_excluded")
    unconfirmed = any(
        o.status in (ObligationStatus.INFERRED, ObligationStatus.UNCERTAIN)
        for o in snapshot.obligations
    ) or any(not i.confirmed for i in snapshot.incomes)
    if unconfirmed:
        flags.append("unconfirmed_events")
    if snapshot.coverage == Coverage.PARTIAL:
        flags.append("partial_coverage")
    if snapshot.extra_expenses or snapshot.income_shifts:
        flags.append("scenario_applied")

    insufficient = not liquid_ids or (
        spending.history_days < MIN_HISTORY_DAYS and not snapshot.obligations
    )
    return ForecastResult(
        model_version=MODEL_VERSION,
        today=today,
        start_balance_minor=start,
        reserve_minor=reserve,
        points=tuple(points),
        risk_level=level,
        risk_date=risk_date,
        shortfall_minor=max(0, shortfall),
        min_p50_minor=min50_value,
        min_p50_day=min50_day,
        min_p10_minor=min10_value,
        min_p10_day=min10_day,
        drivers=tuple(drivers),
        next_income_day=next_income,
        confidence="insufficient" if insufficient else "illustrative",
        flags=tuple(flags),
        spending=spending,
    )
