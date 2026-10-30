from datetime import UTC, date, datetime

from forecast_core.purchase_context import analyze_purchase_context
from forecast_core.types import HistoricalTransaction, TxStatus, TxType

RUB = 100


def _tx(
    number: int,
    day: int,
    amount: int,
    merchant: str,
    category: str = "groceries",
    label: str | None = None,
) -> HistoricalTransaction:
    return HistoricalTransaction(
        id=f"tx_{number}",
        account_id="acc",
        occurred_at=datetime(2026, 10, day, 12, tzinfo=UTC),
        amount_minor=-amount * RUB,
        type=TxType.EXPENSE,
        status=TxStatus.POSTED,
        category=category,
        description=merchant,
        label=label,
    )


def _income(number: int, day: int, amount: int = 100_000) -> HistoricalTransaction:
    return HistoricalTransaction(
        id=f"income_{number}",
        account_id="acc",
        occurred_at=datetime(2026, 10, day, 8, tzinfo=UTC),
        amount_minor=amount * RUB,
        type=TxType.INCOME,
        status=TxStatus.POSTED,
        description="Зарплата",
    )


def test_same_merchant_and_weekday_is_most_specific_basis() -> None:
    # 5, 12 и 19 октября 2026 — понедельники.
    history = [_tx(1, 5, 1_000, "Лента 001"), _tx(2, 12, 1_200, "ЛЕНТА #77")]
    result = analyze_purchase_context(
        history,
        amount_minor=1_100 * RUB,
        day=date(2026, 10, 19),
        timezone="Europe/Moscow",
        merchant="Лента",
        category="groceries",
    )
    assert result.basis == "merchant_weekday"
    assert result.observations == 2
    assert result.median_minor == 1_100 * RUB
    assert result.amount_position == "typical"


def test_sparse_merchant_falls_back_to_category() -> None:
    history = [
        _tx(1, 5, 900, "Магнит"),
        _tx(2, 6, 1_100, "Пятёрочка"),
        _tx(3, 7, 1_000, "Перекрёсток"),
    ]
    result = analyze_purchase_context(
        history,
        amount_minor=1_050 * RUB,
        day=date(2026, 10, 20),
        timezone="Europe/Moscow",
        merchant="Новый магазин",
        category="groceries",
    )
    assert result.basis == "category"
    assert result.observations == 3


def test_same_phase_after_income_is_more_specific_than_weekday() -> None:
    history = [
        _income(1, 1),
        _tx(1, 2, 1_000, "Лента"),
        _income(2, 15),
        _tx(2, 17, 1_200, "Лента"),
        _tx(3, 12, 4_000, "Лента"),
    ]
    result = analyze_purchase_context(
        history,
        amount_minor=1_100 * RUB,
        day=date(2026, 10, 16),
        timezone="Europe/Moscow",
        merchant="Лента",
    )
    assert result.basis == "merchant_income_phase"
    assert result.observations == 2
    assert result.median_minor == 1_100 * RUB


def test_income_after_purchase_does_not_define_its_phase() -> None:
    history = [
        _tx(1, 2, 1_000, "Лента"),
        _income(1, 10),
        _tx(2, 12, 1_100, "Лента"),
    ]
    result = analyze_purchase_context(
        history,
        amount_minor=1_050 * RUB,
        day=date(2026, 10, 13),
        timezone="Europe/Moscow",
        merchant="Лента",
    )
    assert result.basis == "merchant"
    assert result.observations == 2


def test_one_off_does_not_train_purchase_context() -> None:
    history = [
        _tx(1, 5, 20_000, "М.Видео", "electronics", "one_off"),
        _tx(2, 12, 22_000, "М.Видео", "electronics", "one_off"),
    ]
    result = analyze_purchase_context(
        history,
        amount_minor=21_000 * RUB,
        day=date(2026, 10, 19),
        timezone="Europe/Moscow",
        merchant="М.Видео",
        category="electronics",
    )
    assert result.basis == "amount_only"
    assert result.amount_position == "unknown"


def test_amount_well_above_personal_range_is_reported_without_judgement() -> None:
    history = [_tx(1, 5, 900, "Лента"), _tx(2, 12, 1_100, "Лента")]
    result = analyze_purchase_context(
        history,
        amount_minor=3_000 * RUB,
        day=date(2026, 10, 19),
        timezone="Europe/Moscow",
        merchant="Лента",
    )
    assert result.amount_position == "above"
