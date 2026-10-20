"""Эталонные расчётные тесты (раздел 12.4) и финансовые инварианты (23.2)."""

import time
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from forecast_core import (
    AccountSnapshot,
    AccountType,
    ForecastInputSnapshot,
    HistoricalTransaction,
    IncomeExpectation,
    ObligationEvent,
    ObligationStatus,
    TxStatus,
    TxType,
)
from forecast_core.adapters import snapshot_from_dataset
from forecast_core.baseline import MODEL_VERSION, run_baseline
from forecast_core.types import IncomeShift, ScenarioExpense

AS_OF = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)  # 10:00 по Москве
TODAY = date(2026, 10, 19)
RUB = 100


def _account(
    id_: str = "card",
    type_: AccountType = AccountType.DEBIT,
    balance: int = 35_000 * RUB,
    **kw: object,
) -> AccountSnapshot:
    return AccountSnapshot(id_, type_, "RUB", balance, AS_OF, **kw)  # type: ignore[arg-type]


def _daily_history(
    days: int = 28, amount: int = 1_000 * RUB, account: str = "card"
) -> tuple[HistoricalTransaction, ...]:
    """Ровно одна покупка в день — траты без разброса, коридор нулевой."""
    return tuple(
        HistoricalTransaction(
            f"h{i}",
            account,
            AS_OF - timedelta(days=i),
            -amount,
            TxType.EXPENSE,
            TxStatus.POSTED,
            "groceries",
        )
        for i in range(1, days + 1)
    )


def _tx(
    id_: str,
    amount: int,
    type_: TxType,
    days_ago: int = 3,
    account: str = "card",
    category: str | None = None,
    status: TxStatus = TxStatus.POSTED,
) -> HistoricalTransaction:
    return HistoricalTransaction(
        id_, account, AS_OF - timedelta(days=days_ago), amount, type_, status, category
    )


RENT = ObligationEvent(
    "rent",
    "card",
    date(2026, 10, 25),
    18_000 * RUB,
    ObligationStatus.CONFIRMED,
    "rent",
    recurrence="monthly",
    recurrence_day=25,
    title="Аренда",
)
SALARY = IncomeExpectation(
    "salary",
    "card",
    date(2026, 10, 26),
    date(2026, 10, 28),
    60_000 * RUB,
    60_000 * RUB,
    0.97,
    True,
    "monthly",
    "Зарплата",
    "salary",
)


def _snapshot(**kw: object) -> ForecastInputSnapshot:
    values: dict[str, object] = {
        "as_of": AS_OF,
        "timezone": "Europe/Moscow",
        "horizon_days": 14,
        "reserve_minor": 5_000 * RUB,
        "accounts": (_account(),),
        "obligations": (RENT,),
        "incomes": (SALARY,),
        "history": _daily_history(),
    }
    values.update(kw)
    return ForecastInputSnapshot(**values)  # type: ignore[arg-type]


def test_golden_scenario_from_section_2_1() -> None:
    """35 000 ₽, платёж 18 000 ₽ через 6 дней, траты 1 000 ₽/день, зарплата 26–28."""
    result = run_baseline(_snapshot())
    by_day = {p.day: p for p in result.points}
    assert result.model_version == MODEL_VERSION
    assert result.start_balance_minor == 35_000 * RUB
    assert by_day[date(2026, 10, 24)].p50_minor == (35_000 - 5 * 1_000) * RUB
    assert by_day[date(2026, 10, 25)].p50_minor == (35_000 - 6 * 1_000 - 18_000) * RUB
    assert by_day[date(2026, 10, 26)].p50_minor == (35_000 - 7 * 1_000 - 18_000 + 60_000) * RUB
    # Пессимистичный сценарий: зарплата в последний день окна (28-го).
    assert by_day[date(2026, 10, 27)].p10_minor == (35_000 - 8 * 1_000 - 18_000) * RUB
    assert by_day[date(2026, 10, 28)].p10_minor == (35_000 - 9 * 1_000 - 18_000 + 60_000) * RUB
    assert result.risk_level == "low"
    assert result.min_p50_minor == 11_000 * RUB and result.min_p50_day == date(2026, 10, 25)


def test_purchase_scenario_creates_risk_and_explains_it() -> None:
    base = run_baseline(_snapshot())
    purchase = ScenarioExpense(date(2026, 10, 20), 12_000 * RUB, "Телефон")
    result = run_baseline(_snapshot(extra_expenses=(purchase,)))
    assert result.risk_level == "high"
    assert result.risk_date == date(2026, 10, 25)
    assert result.min_p50_minor == base.min_p50_minor - 12_000 * RUB
    assert result.shortfall_minor == 5_000 * RUB - result.min_p50_minor
    kinds = [d.kind for d in result.drivers]
    assert kinds[0] == "obligation" and result.drivers[0].label == "Аренда"
    assert "scenario" in kinds and "daily_spending" in kinds
    after = next(d for d in result.drivers if d.kind == "income_after_risk")
    assert after.day == date(2026, 10, 26)
    assert "scenario_applied" in result.flags


def test_salary_delay_scenario_moves_risk() -> None:
    tight = _snapshot(accounts=(_account(balance=30_000 * RUB),))
    on_time = run_baseline(tight)
    delayed = run_baseline(replace(tight, income_shifts=(IncomeShift("salary", 2),)))
    assert on_time.risk_level == "medium"  # опасно только в пессимистичном сценарии
    assert delayed.risk_level == "high"
    assert delayed.min_p50_minor < on_time.min_p50_minor


def test_transfers_refunds_card_and_obligation_payments_are_not_spending() -> None:
    noise = (
        _tx("t-out", -30_000 * RUB, TxType.TRANSFER_OUT),
        _tx("t-in", 30_000 * RUB, TxType.TRANSFER_IN, account="savings"),
        _tx("refund", 5_000 * RUB, TxType.REFUND),
        _tx("card-pay", -20_000 * RUB, TxType.CREDIT_PAYMENT),
        _tx("rent-paid", -18_000 * RUB, TxType.EXPENSE, category="rent"),
        _tx("on-card", -7_000 * RUB, TxType.CREDIT_PURCHASE, account="credit"),
        _tx("pending", -9_000 * RUB, TxType.EXPENSE, days_ago=1, status=TxStatus.PENDING),
        _tx("canceled", -9_000 * RUB, TxType.EXPENSE, status=TxStatus.CANCELED),
    )
    accounts = (
        _account(),
        _account("savings", AccountType.SAVINGS, 0),
        _account(
            "credit",
            AccountType.CREDIT_CARD,
            -7_000 * RUB,
            is_liquid=False,
            credit_limit_minor=100_000 * RUB,
        ),
    )
    clean = run_baseline(_snapshot(accounts=accounts))
    noisy = run_baseline(_snapshot(accounts=accounts, history=_daily_history() + noise))
    assert noisy.spending.weekday_daily_minor == clean.spending.weekday_daily_minor
    assert noisy.spending.excluded_obligation_like == 1
    assert [p.p50_minor for p in noisy.points] == [p.p50_minor for p in clean.points]
    # Кредитный лимит и долг по карте не увеличивают свободные средства.
    assert noisy.start_balance_minor == 35_000 * RUB


def test_large_one_off_purchase_is_excluded_from_daily_model() -> None:
    spike = _tx("tv", -80_000 * RUB, TxType.EXPENSE, category="electronics")
    result = run_baseline(_snapshot(history=(*_daily_history(), spike)))
    assert result.spending.excluded_large == 1
    assert set(result.spending.weekday_daily_minor) == {1_000 * RUB}
    assert "large_expenses_excluded" in result.flags


def test_credit_card_payment_grows_with_card_spending() -> None:
    card_history = tuple(
        _tx(f"c{i}", -500 * RUB, TxType.CREDIT_PURCHASE, days_ago=i, account="credit")
        for i in range(1, 29)
    )
    payment = ObligationEvent(
        "pay",
        "card",
        date(2026, 10, 29),
        4_000 * RUB,
        ObligationStatus.UNCERTAIN,
        "credit_card",
        title="Погашение кредитки",
    )
    accounts = (
        _account(),
        _account(
            "credit",
            AccountType.CREDIT_CARD,
            -4_000 * RUB,
            is_liquid=False,
            credit_limit_minor=100_000 * RUB,
        ),
    )
    result = run_baseline(
        _snapshot(
            accounts=accounts,
            obligations=(payment,),
            incomes=(),
            history=_daily_history() + card_history,
        )
    )
    pay_day = next(p for p in result.points if p.day == date(2026, 10, 29))
    assert result.spending.card_daily_minor == 500 * RUB
    assert pay_day.outflow_minor == (4_000 + 10 * 500) * RUB
    assert "card_spending_accrual" in result.flags


def test_income_probability_thresholds() -> None:
    maybe = replace(SALARY, probability=0.7, confirmed=False)
    result = run_baseline(_snapshot(incomes=(maybe,)))
    day = {p.day: p for p in result.points}[date(2026, 10, 28)]
    assert day.p50_minor > 30_000 * RUB  # в базовом сценарии доход учтён
    assert day.p10_minor < 10_000 * RUB  # в пессимистичном — нет
    assert "unconfirmed_events" in result.flags


def test_canceled_obligation_is_ignored_and_31st_is_clamped() -> None:
    canceled = replace(RENT, status=ObligationStatus.CANCELED)
    installment = ObligationEvent(
        "inst",
        "card",
        date(2026, 10, 31),
        1_000 * RUB,
        ObligationStatus.CONFIRMED,
        "installment",
        recurrence="monthly",
        recurrence_day=31,
    )
    result = run_baseline(
        _snapshot(obligations=(canceled, installment), incomes=(), horizon_days=45)
    )
    outflow_days = [p.day for p in result.points if p.outflow_minor]
    assert outflow_days == [date(2026, 10, 31), date(2026, 11, 30)]


def test_history_quality_flags_and_confidence() -> None:
    no_history = run_baseline(_snapshot(history=()))
    assert "no_history" in no_history.flags
    assert no_history.confidence == "illustrative"  # календарь обязательств уже есть
    short = run_baseline(_snapshot(history=_daily_history(days=10)))
    assert "short_history" in short.flags
    nothing = run_baseline(_snapshot(accounts=(), obligations=(), incomes=(), history=()))
    assert nothing.confidence == "insufficient"


def test_bands_are_ordered_and_result_is_deterministic() -> None:
    noisy = tuple(
        _tx(f"n{i}", -(300 + (i * 397) % 2_500) * RUB, TxType.EXPENSE, days_ago=i)
        for i in range(1, 60)
    )
    snapshot = _snapshot(history=noisy, horizon_days=30)
    first, second = run_baseline(snapshot), run_baseline(snapshot)
    assert first == second
    assert all(p.p10_minor <= p.p50_minor <= p.p90_minor for p in first.points)
    widths = [p.p90_minor - p.p10_minor for p in first.points]
    assert widths[-1] > widths[0]  # неопределённость растёт с горизонтом


def test_golden_demo_profile() -> None:
    """Демо 16.4 на эталонном профиле: риск до зарплаты и эффект покупки 12 000 ₽."""
    synthetic = pytest.importorskip("synthetic_generator")
    snapshot = snapshot_from_dataset(synthetic.generate("young_specialist"))
    result = run_baseline(snapshot)
    assert result.start_balance_minor == 55_000 * RUB
    assert result.risk_level == "medium"
    assert result.risk_date == date(2026, 10, 23)
    labels = [d.label for d in result.drivers if d.kind == "obligation"]
    assert labels[:2] == ["Аренда квартиры", "Потребкредит"]
    purchase = ScenarioExpense(date(2026, 10, 20), 12_000 * RUB)
    with_purchase = run_baseline(replace(snapshot, extra_expenses=(purchase,)))
    assert with_purchase.risk_level == "high"
    assert with_purchase.min_p50_minor < 0


def test_performance_10k_transactions() -> None:
    """Раздел 13.4: 30-дневный прогноз на 10 000 операций — до 3 секунд (цель 26.1 — 2 с)."""
    history = tuple(
        _tx(f"p{i}", -(100 + i % 900) * RUB, TxType.EXPENSE, days_ago=1 + i % 90)
        for i in range(10_000)
    )
    started = time.perf_counter()
    run_baseline(_snapshot(history=history, horizon_days=30))
    assert time.perf_counter() - started < 2.0
