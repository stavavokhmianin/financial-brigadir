"""Базовый прогноз остатка по дням: уровни 0 и 1 раздела 23.1.

* Уровень 0 — достоверный календарь: текущий ликвидный остаток, подтверждённые
  и ожидаемые доходы и обязательства по датам. Работает и без истории.
* Уровень 1 — статистическая база: медиана повседневных трат по дням недели
  (раздел 9.2). Из истории исключаются переводы между своими счетами, возвраты,
  погашения кредитки, оплаты обязательств и аномально крупные покупки.

Коридор p10/p90 здесь — не вероятность, а сценарии: пессимистичный (траты на уровне
90-го перцентиля исторических скользящих сумм, доход в последний день окна,
верхняя граница неточных платежей) и оптимистичный. Вероятность нарушения
резерва появится вместе с симуляцией (уровень 2) и калибровкой; до этого
результат помечается как иллюстративный.
"""

import math
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise
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

MODEL_VERSION = "baseline-0.2"
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
# Метки пользователя (ADR-0007). «Разовая» не участвует в обучении повторению; остальные
# метки подтверждают, что трата — часть обычного поведения, и снимают автоотсечение крупных.
LABEL_ONE_OFF = "one_off"
LABELS_KEEP = frozenset({"mandatory", "regular", "reducible"})
# Поступление засчитывается как уже пришедший доход, если оно не меньше этой доли минимума.
RECEIVED_INCOME_SHARE = 0.5
# Насколько раньше окна мог прийти доход, чтобы считаться его поступлением.
RECEIVED_INCOME_EARLY_DAYS = 3
LIQUID_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS})

# Пороги включения дохода в сценарий по вероятности поступления.
P50_MIN_PROBABILITY = 0.5
P10_MIN_PROBABILITY = 0.9
P90_MIN_PROBABILITY = 0.3
RECENCY_HALF_LIFE_DAYS = 56
MIN_PHASE_SAMPLES = 6
MIN_PHASE_RATIO = 0.5


Estimator = Literal["mean", "median"]


def _income_phase(day: date, income_days: Sequence[date]) -> int | None:
    """0 — до 3 дней после дохода, 1 — 4–10, 2 — 11–20, 3 — позднее."""
    index = bisect_right(income_days, day) - 1
    if index < 0:
        return None
    distance = (day - income_days[index]).days
    if distance <= 3:
        return 0
    if distance <= 10:
        return 1
    if distance <= 20:
        return 2
    return 3


def _weighted_mean(rows: Sequence[tuple[date, int]], today: date) -> int:
    """Свежие дни весомее; 56 дней назад наблюдение имеет половину веса."""
    if not rows:
        return 0
    weighted = [
        (value, 0.5 ** (max(0, (today - day).days) / RECENCY_HALF_LIFE_DAYS)) for day, value in rows
    ]
    total_weight = sum(weight for _, weight in weighted)
    return round(sum(value * weight for value, weight in weighted) / total_weight)


def _stable_recent_trend(rows: Sequence[tuple[date, int]], today: date) -> bool:
    """Свежесть включается лишь при согласованном сдвиге последних четырёх недель."""
    recent = [(day, value) for day, value in rows if 1 <= (today - day).days <= 28]
    previous = [(day, value) for day, value in rows if 29 <= (today - day).days <= 56]
    if len(recent) < 21 or len(previous) < 21:
        return False
    recent_mean = mean(value for _, value in recent)
    previous_mean = mean(value for _, value in previous)
    if previous_mean <= 0:
        return recent_mean > 0
    change = recent_mean / previous_mean - 1
    if abs(change) < 0.5:
        return False
    direction = 1 if change > 0 else -1
    agreeing = 0
    compared = 0
    for weekday in range(7):
        fresh = [value for day, value in recent if day.weekday() == weekday]
        old = [value for day, value in previous if day.weekday() == weekday]
        if not fresh or not old:
            continue
        compared += 1
        if (mean(fresh) - mean(old)) * direction > 0:
            agreeing += 1
    return compared == 7 and agreeing == 7


def _stable_income_schedule(income_days: Sequence[date]) -> bool:
    """Фаза имеет смысл только для достаточно регулярного цикла поступлений."""
    if len(income_days) < 3:
        return False
    recent = income_days[-4:]
    gaps = [(right - left).days for left, right in pairwise(recent)]
    typical = median(gaps)
    return 10 <= typical <= 40 and all(abs(gap - typical) <= 5 for gap in gaps)


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
    income_anchors: tuple[date, ...]
    phase_daily_minor: tuple[int | None, ...]
    phase_weekday_daily_minor: tuple[tuple[int | None, ...], ...]
    recency_half_life_days: int | None
    # Для симуляции (уровень 2): дневные траты истории и исключённые крупные покупки.
    daily_history: tuple[tuple[date, int], ...] = ()
    large_amounts_minor: tuple[int, ...] = ()
    excluded_one_off: int = 0  # отмечены пользователем как разовые

    def daily(self, day: date) -> int:
        base = self.weekday_daily_minor[day.weekday()]
        phase = self.phase(day)
        if phase is not None:
            exact = self.phase_weekday_daily_minor[phase][day.weekday()]
            if exact is not None:
                # Иерархическое сглаживание: узкий срез не вытесняет устойчивый weekday.
                return round(base * 0.5 + exact * 0.5)
            fallback = self.phase_daily_minor[phase]
            if fallback is not None:
                return round(base * 0.75 + fallback * 0.25)
        return base

    def phase(self, day: date) -> int | None:
        return _income_phase(day, self.income_anchors)


@dataclass(frozen=True, slots=True)
class DayPoint:
    day: date
    p10_minor: int
    p50_minor: int
    p90_minor: int
    inflow_minor: int
    outflow_minor: int
    spending_minor: int
    risk_probability: float | None = None  # только у вероятностной модели


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
    gap_probability: float | None = None  # P(min_t (B_t - R_t) < 0), только у симуляции
    # Траектории остатка симуляции (для суммы безопасной покупки по формуле 9.4).
    trajectories: tuple[tuple[int, ...], ...] = field(default=(), compare=False, repr=False)


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
    future_income_anchors: Iterable[date] = (),
) -> SpendingModel:
    transactions = list(history)
    window_start = today - timedelta(days=HISTORY_WINDOW_DAYS)
    candidates: list[tuple[date, int, bool]] = []
    card_daily: dict[date, int] = {}
    earliest: date | None = None
    excluded_obligation_like = 0
    excluded_one_off = 0
    actual_income_anchors = sorted(
        {
            _local_date(tx, tz)
            for tx in transactions
            if tx.status == TxStatus.POSTED
            and tx.type == TxType.INCOME
            and tx.amount_minor > 0
            and tx.account_id in liquid_ids
            and _local_date(tx, tz) < today
        }
    )
    income_anchors = tuple(sorted({*actual_income_anchors, *future_income_anchors}))
    for tx in transactions:
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
        if tx.obligation_id or (tx.category and tx.category in obligation_categories):
            excluded_obligation_like += 1
            continue
        if tx.label == LABEL_ONE_OFF:
            excluded_one_off += 1
            continue
        candidates.append((day, -tx.amount_minor, tx.label in LABELS_KEEP))

    history_days = (today - earliest).days if earliest else 0
    typical = median([amount for _, amount, _ in candidates]) if candidates else 0
    threshold = max(LARGE_TX_FLOOR_MINOR, int(typical * LARGE_TX_FACTOR))
    days = [earliest + timedelta(days=i) for i in range(history_days)] if earliest else []
    totals = dict.fromkeys(days, 0)
    excluded_large = 0
    large_amounts: list[int] = []
    for day, amount, kept in candidates:
        if amount > threshold and not kept:
            excluded_large += 1
            large_amounts.append(amount)
            continue
        totals[day] = totals.get(day, 0) + amount
    daily = [totals[d] for d in days]

    rows = [(day, totals[day]) for day in days]
    by_weekday: list[list[tuple[date, int]]] = [[] for _ in range(7)]
    for day in days:
        by_weekday[day.weekday()].append((day, totals[day]))

    use_recency = estimator == "mean" and _stable_recent_trend(rows, today)

    def estimate(values: Sequence[tuple[date, int]]) -> int:
        if use_recency:
            return _weighted_mean(values, today)
        if estimator == "mean":
            return round(mean(value for _, value in values)) if values else 0
        return round(median(value for _, value in values)) if values else 0

    overall = estimate(rows)
    weekday_daily = tuple(estimate(values) if values else overall for values in by_weekday)

    by_phase: list[list[tuple[date, int]]] = [[] for _ in range(4)]
    by_cycle: dict[int, list[tuple[date, int]]] = {}
    phase_by_cycle: list[dict[int, list[tuple[date, int]]]] = [{} for _ in range(4)]
    for day, value in rows:
        cycle = bisect_right(actual_income_anchors, day) - 1
        if cycle < 0:
            continue
        phase = _income_phase(day, actual_income_anchors)
        if phase is None:
            continue
        by_phase[phase].append((day, value))
        by_cycle.setdefault(cycle, []).append((day, value))
        phase_by_cycle[phase].setdefault(cycle, []).append((day, value))

    def stable_phase(phase: int) -> bool:
        """Фаза включается лишь при одном направлении эффекта минимум в трёх циклах."""
        ratios: list[float] = []
        for cycle, phase_rows in phase_by_cycle[phase].items():
            cycle_center = mean(value for _, value in by_cycle[cycle])
            if cycle_center > 0:
                ratios.append(mean(value for _, value in phase_rows) / cycle_center)
        return len(ratios) >= 3 and (
            all(ratio >= 1 + MIN_PHASE_RATIO for ratio in ratios)
            or all(ratio <= 1 - MIN_PHASE_RATIO for ratio in ratios)
        )

    stable_schedule = _stable_income_schedule(actual_income_anchors)
    phase_daily = tuple(
        estimate(values)
        if estimator == "mean"
        and stable_schedule
        and len(values) >= MIN_PHASE_SAMPLES
        and stable_phase(phase)
        else None
        for phase, values in enumerate(by_phase)
    )
    phase_weekday = tuple(tuple(None for _ in range(7)) for _ in range(4))

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
            middle = int(mean(sums) if estimator == "mean" else median(sums))
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
        income_anchors=income_anchors,
        phase_daily_minor=phase_daily,
        phase_weekday_daily_minor=phase_weekday,
        recency_half_life_days=RECENCY_HALF_LIFE_DAYS if use_recency else None,
        daily_history=tuple((d, totals[d]) for d in days),
        large_amounts_minor=tuple(large_amounts),
        excluded_one_off=excluded_one_off,
    )


def _income_received(
    history: Iterable[HistoricalTransaction],
    income: IncomeExpectation,
    liquid_ids: set[str],
    window: tuple[date, date],
    tz: ZoneInfo,
) -> bool:
    """Доход этого окна уже есть в выписке — второй раз в прогноз он не идёт."""
    first, today = window
    since = first - timedelta(days=RECEIVED_INCOME_EARLY_DAYS)
    floor = int(income.amount_min_minor * RECEIVED_INCOME_SHARE)
    for tx in history:
        if tx.type != TxType.INCOME or tx.amount_minor < floor or tx.status != TxStatus.POSTED:
            continue
        if income.account_id is not None and tx.account_id != income.account_id:
            continue
        if income.account_id is None and tx.account_id not in liquid_ids:
            continue
        if since <= _local_date(tx, tz) <= today:
            return True
    return False


@dataclass(frozen=True, slots=True)
class ObligationHit:
    source_id: str
    day: date
    amount_minor: int  # базовая сумма (с учётом трат по кредитке)
    low_minor: int
    high_minor: int
    status: ObligationStatus
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class IncomeHit:
    source_id: str
    source_day: date  # дата в исходном расписании, до сценарного сдвига
    first: date  # самая ранняя дата окна
    last: date  # самая поздняя дата окна
    min_minor: int
    max_minor: int
    probability: float
    label: str


@dataclass
class Plan:
    """Всё, что известно о горизонте до расчёта траекторий: общий вход обеих моделей."""

    snapshot: ForecastInputSnapshot
    today: date
    days: list[date]
    index: dict[date, int]
    spending: SpendingModel
    start: int
    liquid_ids: set[str]
    flags: list[str]
    obligations: list[ObligationHit]
    incomes: list[IncomeHit]
    scenarios: list[tuple[date, int, str]]


def prepare_plan(snapshot: ForecastInputSnapshot, estimator: Estimator = "mean") -> Plan:
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
    start = liquid_balance_minor(snapshot.accounts, snapshot.currency)
    flags: list[str] = []

    incomes: list[IncomeHit] = []
    shifts = {shift.income_id: shift.shift_days for shift in snapshot.income_shifts}
    for income in snapshot.incomes:
        shift = timedelta(days=shifts.get(income.id, 0))
        shifted_from = income.date_from + shift
        spread = income.date_to - income.date_from
        for first in occurrences(shifted_from, income.recurrence, today - spread, end):
            # Окно уже открылось, и доход пришёл: он в остатке, повторно его не ждём.
            if first <= today and _income_received(
                snapshot.history, income, liquid_ids, (first - shift, today), tz
            ):
                continue
            incomes.append(
                IncomeHit(
                    income.id,
                    first - shift,
                    first,
                    first + spread,
                    income.amount_min_minor,
                    income.amount_max_minor,
                    income.probability,
                    income.title or income.kind,
                )
            )

    spending = build_spending_model(
        snapshot.history,
        liquid_ids,
        card_ids,
        obligation_categories,
        today,
        tz,
        horizon,
        estimator,
        (
            hit.first
            for hit in incomes
            if hit.probability >= P50_MIN_PROBABILITY and hit.first > today
        ),
    )

    obligations: list[ObligationHit] = []
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
            amount, worst = base, high
            if obligation.kind == "credit_card" and spending.card_daily_minor > 0:
                # Траты по кредитке до даты платежа увеличат сумму погашения (9.5).
                amount = base + spending.card_daily_minor * (day - today).days
                worst = max(high, amount)
                if "card_spending_accrual" not in flags:
                    flags.append("card_spending_accrual")
            obligations.append(
                ObligationHit(
                    obligation.id,
                    day,
                    amount,
                    low,
                    worst,
                    obligation.status,
                    obligation.kind,
                    obligation.title or obligation.kind,
                )
            )

    scenarios: list[tuple[date, int, str]] = []
    for expense in snapshot.extra_expenses:
        if expense.day in index:
            scenarios.append((expense.day, expense.amount_minor, expense.label))
        elif today >= expense.day:
            # Покупка сегодня (или «прямо сейчас») сразу уменьшает остаток.
            start -= expense.amount_minor
            scenarios.append((today, expense.amount_minor, expense.label))

    return Plan(
        snapshot,
        today,
        days,
        index,
        spending,
        start,
        liquid_ids,
        flags,
        obligations,
        incomes,
        scenarios,
    )


def finalize(
    plan: Plan,
    points: list[DayPoint],
    level: str,
    risk_date: date | None,
    shortfall: int,
    model_version: str,
    gap_probability: float | None = None,
    trajectories: tuple[tuple[int, ...], ...] = (),
) -> ForecastResult:
    """Минимумы, причины риска (раздел 9.6), флаги качества и итоговый результат."""
    snapshot, today, spending = plan.snapshot, plan.today, plan.spending
    if points:
        min50 = min(points, key=lambda p: (p.p50_minor, p.day))
        min10 = min(points, key=lambda p: (p.p10_minor, p.day))
        min50_value, min50_day = min50.p50_minor, min50.day
        min10_value, min10_day = min10.p10_minor, min10.day
    else:
        min50_value = min10_value = plan.start
        min50_day = min10_day = today

    income_days = [
        (hit.first, hit.label)
        for hit in plan.incomes
        if hit.probability >= P50_MIN_PROBABILITY and hit.first in plan.index
    ]
    target = risk_date or min50_day
    drivers: list[RiskDriver] = []
    before = sorted(
        (hit for hit in plan.obligations if hit.day <= target),
        key=lambda h: (-h.amount_minor, h.day),
    )
    for hit in before[:3]:
        drivers.append(RiskDriver("obligation", hit.kind, hit.label, hit.amount_minor, hit.day))
    for day, amount, label in plan.scenarios:
        if day <= target:
            drivers.append(RiskDriver("scenario", "scenario_expense", label, amount, day))
    spend_until = sum(spending.daily(p.day) for p in points if p.day <= target)
    if spend_until > 0:
        drivers.append(
            RiskDriver("daily_spending", "daily_spending", "Повседневные траты", spend_until, None)
        )
    later_income = min((d for d, _ in income_days if d > target), default=None)
    next_income = min((d for d, _ in income_days), default=None)
    if later_income is not None and level != "low":
        title = next(t for d, t in income_days if d == later_income)
        drivers.append(RiskDriver("income_after_risk", "income_after_risk", title, 0, later_income))

    flags = list(plan.flags)
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

    insufficient = not plan.liquid_ids or (
        spending.history_days < MIN_HISTORY_DAYS and not snapshot.obligations
    )
    return ForecastResult(
        model_version=model_version,
        today=today,
        start_balance_minor=plan.start,
        reserve_minor=snapshot.reserve_minor,
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
        gap_probability=gap_probability,
        trajectories=trajectories,
    )


def run_baseline(snapshot: ForecastInputSnapshot, estimator: Estimator = "mean") -> ForecastResult:
    """Детерминированный прогноз (уровни 0–1) на ``horizon_days`` дней от ``as_of``."""
    plan = prepare_plan(snapshot, estimator)
    horizon = len(plan.days)
    # Потоки по дням для трёх сценариев: 0 — p10 (плохой), 1 — p50, 2 — p90 (хороший).
    inflow = [[0] * horizon for _ in range(3)]
    outflow = [[0] * horizon for _ in range(3)]
    for hit in plan.obligations:
        i = plan.index[hit.day]
        outflow[0][i] += hit.high_minor
        outflow[1][i] += hit.amount_minor
        outflow[2][i] += hit.low_minor
    for income in plan.incomes:
        middle = (income.min_minor + income.max_minor) // 2
        if income.probability >= P50_MIN_PROBABILITY and income.first in plan.index:
            inflow[1][plan.index[income.first]] += middle
        if income.probability >= P10_MIN_PROBABILITY and income.last in plan.index:
            inflow[0][plan.index[income.last]] += income.min_minor
        if income.probability >= P90_MIN_PROBABILITY and income.first in plan.index:
            inflow[2][plan.index[income.first]] += income.max_minor
    for day, amount, _ in plan.scenarios:
        if day in plan.index:
            for band in range(3):
                outflow[band][plan.index[day]] += amount

    spending = plan.spending
    points: list[DayPoint] = []
    cum_in = [0, 0, 0]
    cum_out = [0, 0, 0]
    cum_spend = 0
    for i, day in enumerate(plan.days):
        for band in range(3):
            cum_in[band] += inflow[band][i]
            cum_out[band] += outflow[band][i]
        spend_today = spending.daily(day)
        cum_spend += spend_today
        start = plan.start
        p50 = start + cum_in[1] - cum_out[1] - cum_spend
        p10 = start + cum_in[0] - cum_out[0] - (cum_spend + spending.band_high_minor[i])
        p90 = start + cum_in[2] - cum_out[2] - max(0, cum_spend - spending.band_low_minor[i])
        p10 = min(p10, p50)
        p90 = max(p90, p50)
        points.append(DayPoint(day, p10, p50, p90, inflow[1][i], outflow[1][i], spend_today))

    reserve = snapshot.reserve_minor
    min50 = min((p.p50_minor for p in points), default=plan.start)
    min10 = min((p.p10_minor for p in points), default=plan.start)
    breach50 = next((p.day for p in points if p.p50_minor < reserve), None)
    breach10 = next((p.day for p in points if p.p10_minor < reserve), None)
    if breach50 is not None:
        level, risk_date, shortfall = "high", breach50, reserve - min50
    elif breach10 is not None:
        level, risk_date, shortfall = "medium", breach10, reserve - min10
    else:
        level, risk_date, shortfall = "low", None, 0
    return finalize(plan, points, level, risk_date, shortfall, MODEL_VERSION)
