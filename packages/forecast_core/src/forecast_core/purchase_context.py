"""Контекст конкретной покупки по истории пользователя.

Это не прогноз денежного потока и не классификатор «хороших» покупок. Модуль отвечает на
более узкий вопрос: есть ли в истории достаточно похожих операций, чтобы сравнить сумму с
личным обычным диапазоном. При разреженных данных оценка откатывается на более общий уровень.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Literal
from zoneinfo import ZoneInfo

from forecast_core.recurring import RECURRING_TYPES, merchant_key
from forecast_core.types import HistoricalTransaction, TxStatus

Basis = Literal[
    "merchant_weekday",
    "merchant",
    "category_weekday",
    "category",
    "amount_only",
]
AmountPosition = Literal["below", "typical", "above", "unknown"]

MIN_MERCHANT_SAMPLES = 2
MIN_CATEGORY_SAMPLES = 3


@dataclass(frozen=True, slots=True)
class PurchaseContextAnalysis:
    basis: Basis
    observations: int
    median_minor: int | None
    lower_minor: int | None
    upper_minor: int | None
    amount_position: AmountPosition
    normalized_merchant: str | None


def _quantile(values: list[int], share: float) -> int:
    """Ближайшая порядковая статистика без интерполяции и ложных копеек."""
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * share)]


def _position(amount_minor: int, lower: int, upper: int) -> AmountPosition:
    # Небольшое отличие от квартилей не называется аномалией: нужен запас 25 %.
    if amount_minor > upper * 1.25:
        return "above"
    if amount_minor < lower * 0.75:
        return "below"
    return "typical"


def analyze_purchase_context(
    history: Iterable[HistoricalTransaction],
    *,
    amount_minor: int,
    day: date,
    timezone: str,
    merchant: str | None = None,
    category: str | None = None,
) -> PurchaseContextAnalysis:
    """Сравнивает покупку с личной историей, используя строгий backoff.

    Метка ``one_off`` исключает операцию из обучения повторению. Отменённые, входящие и
    нерасходные события также не участвуют. Магазин нормализуется тем же правилом, что и
    детектор регулярных платежей.
    """
    tz = ZoneInfo(timezone)
    wanted_merchant = merchant_key(merchant, None) or None
    wanted_category = category.strip().casefold() if category and category.strip() else None
    weekday = day.weekday()
    rows: list[tuple[str, str | None, int, int]] = []
    for tx in history:
        if tx.status != TxStatus.POSTED or tx.type not in RECURRING_TYPES:
            continue
        if tx.amount_minor >= 0 or tx.label == "one_off":
            continue
        rows.append(
            (
                merchant_key(tx.description, tx.category),
                tx.category.strip().casefold() if tx.category else None,
                tx.occurred_at.astimezone(tz).weekday(),
                -tx.amount_minor,
            )
        )

    scopes: list[tuple[Basis, int, list[int]]] = []
    if wanted_merchant:
        merchant_rows = [row for row in rows if row[0] == wanted_merchant]
        scopes.extend(
            [
                (
                    "merchant_weekday",
                    MIN_MERCHANT_SAMPLES,
                    [row[3] for row in merchant_rows if row[2] == weekday],
                ),
                ("merchant", MIN_MERCHANT_SAMPLES, [row[3] for row in merchant_rows]),
            ]
        )
    if wanted_category:
        category_rows = [row for row in rows if row[1] == wanted_category]
        scopes.extend(
            [
                (
                    "category_weekday",
                    MIN_CATEGORY_SAMPLES,
                    [row[3] for row in category_rows if row[2] == weekday],
                ),
                ("category", MIN_CATEGORY_SAMPLES, [row[3] for row in category_rows]),
            ]
        )

    selected = next(
        ((basis, values) for basis, minimum, values in scopes if len(values) >= minimum),
        None,
    )
    if selected is None:
        return PurchaseContextAnalysis(
            basis="amount_only",
            observations=0,
            median_minor=None,
            lower_minor=None,
            upper_minor=None,
            amount_position="unknown",
            normalized_merchant=wanted_merchant,
        )

    basis, values = selected
    lower = _quantile(values, 0.25)
    upper = _quantile(values, 0.75)
    return PurchaseContextAnalysis(
        basis=basis,
        observations=len(values),
        median_minor=int(median(values)),
        lower_minor=lower,
        upper_minor=upper,
        amount_position=_position(amount_minor, lower, upper),
        normalized_merchant=wanted_merchant,
    )
