"""Метки пользователя и уже пришедший доход (ADR-0007)."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from forecast_core import (
    AccountSnapshot,
    AccountType,
    ForecastInputSnapshot,
    HistoricalTransaction,
    IncomeExpectation,
    TxStatus,
    TxType,
    snapshot_fingerprint,
)
from forecast_core.baseline import prepare_plan, run_baseline

AS_OF = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)  # 10:00 по Москве
RUB = 100


def _history(days: int = 28) -> tuple[HistoricalTransaction, ...]:
    daily = tuple(
        HistoricalTransaction(
            f"h{i}",
            "card",
            AS_OF - timedelta(days=i),
            -1_000 * RUB,
            TxType.EXPENSE,
            TxStatus.POSTED,
            "groceries",
        )
        for i in range(1, days + 1)
    )
    # Крупная трата: 20 000 ₽ выше порога автоотсечения (10 000 ₽, 15 медиан).
    big = HistoricalTransaction(
        "big", "card", AS_OF - timedelta(days=3), -20_000 * RUB, TxType.EXPENSE, TxStatus.POSTED
    )
    return (*daily, big)


def _snapshot(**overrides: object) -> ForecastInputSnapshot:
    values: dict[str, object] = {
        "as_of": AS_OF,
        "timezone": "Europe/Moscow",
        "horizon_days": 30,
        "reserve_minor": 5_000 * RUB,
        "accounts": (AccountSnapshot("card", AccountType.DEBIT, "RUB", 35_000 * RUB, AS_OF),),
        "history": _history(),
    }
    values.update(overrides)
    return ForecastInputSnapshot(**values)  # type: ignore[arg-type]


def _labeled(label: str) -> ForecastInputSnapshot:
    snapshot = _snapshot()
    history = tuple(replace(t, label=label) if t.id == "big" else t for t in snapshot.history)
    return replace(snapshot, history=history)


def test_unlabeled_large_expense_is_cut_automatically() -> None:
    spending = run_baseline(_snapshot()).spending
    assert spending.excluded_large == 1
    assert spending.excluded_one_off == 0
    assert spending.large_amounts_minor == (20_000 * RUB,)


def test_one_off_label_drops_expense_from_learning_entirely() -> None:
    spending = run_baseline(_labeled("one_off")).spending
    assert spending.excluded_one_off == 1
    assert spending.excluded_large == 0
    # «Разовая» не возвращается и как случайный крупный шок симуляции.
    assert spending.large_amounts_minor == ()


def test_regular_label_overrides_automatic_cut() -> None:
    base = run_baseline(_snapshot())
    regular = run_baseline(_labeled("regular"))
    assert regular.spending.excluded_large == 0
    # Трата вошла в обычный ритм: повседневный расход выше, прогноз ниже.
    assert sum(regular.spending.weekday_daily_minor) > sum(base.spending.weekday_daily_minor)
    assert regular.min_p50_minor < base.min_p50_minor


def test_labels_never_touch_start_balance() -> None:
    for label in ("one_off", "regular", "reducible", "mandatory"):
        assert run_baseline(_labeled(label)).start_balance_minor == 35_000 * RUB


def test_fingerprint_ignores_absent_labels_but_sees_set_ones() -> None:
    plain = _snapshot()
    assert snapshot_fingerprint(plain) == snapshot_fingerprint(replace(plain))
    assert snapshot_fingerprint(_labeled("one_off")) != snapshot_fingerprint(plain)
    assert snapshot_fingerprint(_labeled("one_off")) != snapshot_fingerprint(_labeled("regular"))


SALARY = IncomeExpectation(
    "salary",
    "card",
    date(2026, 10, 18),
    date(2026, 10, 21),
    60_000 * RUB,
    60_000 * RUB,
    1.0,
    True,
)


def test_income_already_received_in_open_window_is_not_counted_twice() -> None:
    received = HistoricalTransaction(
        "pay", "card", AS_OF - timedelta(days=1), 60_000 * RUB, TxType.INCOME, TxStatus.POSTED
    )
    waiting = prepare_plan(_snapshot(incomes=(SALARY,)))
    assert [hit.source_id for hit in waiting.incomes] == ["salary"]
    arrived = prepare_plan(_snapshot(incomes=(SALARY,), history=(*_history(), received)))
    assert arrived.incomes == []


def test_small_inflow_does_not_count_as_salary() -> None:
    refund_like = HistoricalTransaction(
        "small", "card", AS_OF - timedelta(days=1), 500 * RUB, TxType.INCOME, TxStatus.POSTED
    )
    plan = prepare_plan(_snapshot(incomes=(SALARY,), history=(*_history(), refund_like)))
    assert [hit.source_id for hit in plan.incomes] == ["salary"]
