"""Поиск повторяющихся трат и исключение платежей обязательства из модели (FR-11)."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from forecast_core import (
    AccountSnapshot,
    AccountType,
    ForecastInputSnapshot,
    HistoricalTransaction,
    TxStatus,
    TxType,
    snapshot_fingerprint,
)
from forecast_core.baseline import run_baseline
from forecast_core.recurring import detect_recurring, merchant_key

TZ = ZoneInfo("Europe/Moscow")
TODAY = date(2026, 10, 19)
AS_OF = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)
RUB = 100


def _tx(
    id_: str, day: date, amount: int, description: str, account: str = "card"
) -> HistoricalTransaction:
    return HistoricalTransaction(
        id_,
        account,
        datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC),
        -amount,
        TxType.EXPENSE,
        TxStatus.POSTED,
        "sport",
        description=description,
    )


def _monthly(
    description: str, amount: int, day: int, months: int = 6
) -> list[HistoricalTransaction]:
    items = []
    for i in range(months):
        month = TODAY.month - i - 1
        year = TODAY.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        items.append(_tx(f"{description}{i}", date(year, month, day), amount, description))
    return items


def _daily_noise(days: int = 120) -> list[HistoricalTransaction]:
    return [
        _tx(f"g{i}", TODAY - timedelta(days=i), (300 + (i * 37) % 900) * RUB, "Супермаркет")
        for i in range(1, days)
    ]


def test_merchant_key_ignores_case_digits_and_punctuation() -> None:
    assert merchant_key("ФИТНЕС-КЛУБ №12", None) == merchant_key("фитнес клуб", None)
    assert merchant_key(None, "sport") == "sport"


def test_monthly_payment_is_found_with_next_date() -> None:
    history = _monthly("Фитнес-клуб", 2_900 * RUB, 10) + _daily_noise()
    [found] = detect_recurring(history, TODAY, TZ)
    assert (found.title, found.period, found.anchor) == ("Фитнес-клуб", "monthly", 10)
    assert found.amount_minor == 2_900 * RUB and found.occurrences == 6
    assert found.next_day == date(2026, 11, 10)
    assert 0.6 <= found.confidence <= 1


def test_weekly_payment_is_found() -> None:
    mondays = [TODAY - timedelta(days=TODAY.weekday() + 7 * i) for i in range(10)]
    history = [_tx(f"w{i}", d, 450 * RUB, "Доставка воды") for i, d in enumerate(mondays)]
    [found] = detect_recurring(history, TODAY, TZ)
    assert (found.period, found.anchor) == ("weekly", 0)
    assert found.next_day > TODAY and found.next_day.weekday() == 0


def test_irregular_and_stopped_spending_is_not_proposed() -> None:
    # Ежедневные покупки, нестабильные суммы и подписка, которую перестали платить.
    unstable = [
        _tx(f"u{i}", d.occurred_at.date(), (500 + 4_000 * (i % 2)) * RUB, "Ресторан")
        for i, d in enumerate(_monthly("x", 1, 15))
    ]
    stopped = [
        replace(t, occurred_at=t.occurred_at - timedelta(days=120))
        for t in _monthly("Старый сервис", 499 * RUB, 3)
    ]
    assert detect_recurring(_daily_noise() + unstable + stopped, TODAY, TZ) == []


def test_payments_of_an_obligation_leave_daily_spending() -> None:
    history = tuple(_monthly("Фитнес-клуб", 2_900 * RUB, 10) + _daily_noise())
    snapshot = ForecastInputSnapshot(
        as_of=AS_OF,
        timezone="Europe/Moscow",
        horizon_days=30,
        reserve_minor=5_000 * RUB,
        accounts=(AccountSnapshot("card", AccountType.DEBIT, "RUB", 80_000 * RUB, AS_OF),),
        history=history,
    )
    linked = replace(
        snapshot,
        history=tuple(
            replace(t, obligation_id="obl_fit") if t.description == "Фитнес-клуб" else t
            for t in history
        ),
    )
    plain, covered = run_baseline(snapshot).spending, run_baseline(linked).spending
    # Модель трат смотрит на 91 день: в окне платежи 10 августа и 10 сентября.
    assert covered.excluded_obligation_like == plain.excluded_obligation_like + 2
    assert sum(covered.weekday_daily_minor) < sum(plain.weekday_daily_minor)
    # Связь с обязательством входит в отпечаток: другой вход — другой расчёт.
    assert snapshot_fingerprint(linked) != snapshot_fingerprint(snapshot)
