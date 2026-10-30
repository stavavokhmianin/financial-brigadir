"""Поиск повторяющихся трат (FR-11, ADR-0007 этап B).

Повторение не становится обязательством само: детектор предлагает кандидата с
оценкой регулярности, а в календарь его переносит только пользователь. После этого
операции того же получателя на том же счёте привязываются к обязательству и выходят
из модели повседневных трат — один платёж не считается дважды.

Оценка регулярности — не вероятность повторения: это доля интервалов, попавших в
период, с поправкой на разброс сумм и число наблюдений. Интерфейс показывает её
словами (ADR-0006).
"""

import hashlib
import itertools
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from forecast_core.calendar import clamp_day
from forecast_core.types import HistoricalTransaction, TxStatus, TxType

WINDOW_DAYS = 200
MIN_OCCURRENCES = 3
MIN_SHARE = 0.75  # доля интервалов, попавших в период
MAX_AMOUNT_SPREAD = 0.25  # медианное отклонение суммы от медианы, доля
PERIODS = {"monthly": (25, 35), "weekly": (6, 8)}
FULL_CONFIDENCE_AT = {"monthly": 6, "weekly": 8}
RECURRING_TYPES = frozenset({TxType.EXPENSE, TxType.FEE, TxType.CREDIT_PURCHASE})

_NOISE = re.compile(r"[\d#№*.,:;!?«»\"'()\-_/\\]+")


def merchant_key(description: str | None, category: str | None) -> str:
    """Нормализованный получатель: регистр, цифры, знаки и лишние пробелы не важны."""
    text = _NOISE.sub(" ", (description or category or "").lower())
    return " ".join(text.split())


@dataclass(frozen=True, slots=True)
class RecurringCandidate:
    key: str  # стабильный: счёт + получатель + период
    merchant: str
    title: str
    account_id: str
    category: str | None
    period: str  # monthly | weekly
    anchor: int  # день месяца (monthly) или день недели, 0 — понедельник (weekly)
    amount_minor: int  # медиана, положительная
    amount_min_minor: int
    amount_max_minor: int
    occurrences: int
    last_day: date
    next_day: date
    confidence: float
    transaction_ids: tuple[str, ...]


def candidate_key(account_id: str, merchant: str, period: str) -> str:
    raw = f"{account_id}|{merchant}|{period}".encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def _month_after(day: date, anchor: int) -> date:
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return clamp_day(year, month, anchor)


def _next(period: str, anchor: int, last: date, today: date) -> date:
    if period == "weekly":
        step = last + timedelta(days=7)
        while step <= today:
            step += timedelta(days=7)
        return step
    step = _month_after(last, anchor)
    while step <= today:
        step = _month_after(step, anchor)
    return step


def detect_recurring(
    history: Iterable[HistoricalTransaction], today: date, tz: ZoneInfo
) -> list[RecurringCandidate]:
    """Кандидаты в регулярные платежи по истории до ``today`` включительно."""
    since = today - timedelta(days=WINDOW_DAYS)
    groups: dict[tuple[str, str], list[tuple[date, HistoricalTransaction]]] = defaultdict(list)
    for tx in history:
        if tx.type not in RECURRING_TYPES or tx.amount_minor >= 0:
            continue
        if tx.status != TxStatus.POSTED:
            continue
        day = tx.occurred_at.astimezone(tz).date()
        if since <= day <= today:
            groups[(tx.account_id, merchant_key(tx.description, tx.category))].append((day, tx))

    found: list[RecurringCandidate] = []
    for (account_id, merchant), items in groups.items():
        if not merchant or len(items) < MIN_OCCURRENCES:
            continue
        items.sort(key=lambda item: (item[0], item[1].id))
        days = [day for day, _ in items]
        gaps = [(b - a).days for a, b in itertools.pairwise(days)]
        best: tuple[float, str] | None = None
        for period, (low, high) in PERIODS.items():
            share = sum(low <= gap <= high for gap in gaps) / len(gaps)
            if share >= MIN_SHARE and (best is None or share > best[0]):
                best = (share, period)
        if best is None:
            continue
        share, period = best
        # Остановленная подписка не повторится: последняя операция должна быть недавней.
        if (today - days[-1]).days > PERIODS[period][1] * 1.5:
            continue
        amounts = [-tx.amount_minor for _, tx in items]
        middle = int(median(amounts))
        spread = median(abs(a - middle) for a in amounts) / middle if middle else 1.0
        if spread > MAX_AMOUNT_SPREAD:
            continue
        anchor = days[-1].weekday() if period == "weekly" else int(median(d.day for d in days))
        coverage = min(1.0, len(items) / FULL_CONFIDENCE_AT[period])
        confidence = round(share * (1 - spread) * (0.5 + 0.5 * coverage), 2)
        last_tx = items[-1][1]
        found.append(
            RecurringCandidate(
                key=candidate_key(account_id, merchant, period),
                merchant=merchant,
                title=last_tx.description or last_tx.category or merchant,
                account_id=account_id,
                category=last_tx.category,
                period=period,
                anchor=anchor,
                amount_minor=middle,
                amount_min_minor=min(amounts),
                amount_max_minor=max(amounts),
                occurrences=len(items),
                last_day=days[-1],
                next_day=_next(period, anchor, days[-1], today),
                confidence=confidence,
                transaction_ids=tuple(tx.id for _, tx in items),
            )
        )
    # При равной регулярности первым — платёж, который сильнее влияет на остаток.
    found.sort(key=lambda c: (-c.confidence, -c.amount_minor, c.title))
    return found
