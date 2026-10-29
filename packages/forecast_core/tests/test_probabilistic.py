"""Вероятностная симуляция (раздел 9.3, FR-18) и безопасная сумма по формуле 9.4."""

import time
from dataclasses import replace
from datetime import date, timedelta

import pytest

from forecast_core import IncomeExpectation
from forecast_core.probabilistic import MODEL_VERSION, run_monte_carlo
from forecast_core.scenarios import compare, safe_to_spend
from forecast_core.types import IncomeShift, ScenarioExpense, TxType

from .test_baseline import RUB, SALARY, _account, _snapshot, _tx


def _noisy(days: int = 60) -> tuple:  # type: ignore[type-arg]
    return tuple(
        _tx(f"n{i}", -(300 + (i * 397) % 2_500) * RUB, TxType.EXPENSE, days_ago=i)
        for i in range(1, days + 1)
    )


def _snap(**kw: object):  # type: ignore[no-untyped-def]
    values: dict[str, object] = {"history": _noisy(), "horizon_days": 21}
    values.update(kw)
    return _snapshot(**values)


def test_reproducible_with_seed_and_ordered_bands() -> None:
    snapshot = _snap()
    first, second = run_monte_carlo(snapshot), run_monte_carlo(snapshot)
    assert first == second
    assert first.model_version == MODEL_VERSION
    assert first.gap_probability is not None and 0 <= first.gap_probability <= 1
    for point in first.points:
        assert point.p10_minor <= point.p50_minor <= point.p90_minor
        assert point.risk_probability is not None and 0 <= point.risk_probability <= 1
    other = run_monte_carlo(snapshot, seed=1)
    assert abs((other.gap_probability or 0) - (first.gap_probability or 0)) < 0.1


def test_probability_responds_to_reserve_and_balance() -> None:
    rich = run_monte_carlo(_snap(accounts=(_account(balance=500_000 * RUB),)))
    assert rich.gap_probability == 0 and rich.risk_level == "low"
    hopeless = run_monte_carlo(_snap(reserve_minor=400_000 * RUB))
    assert hopeless.gap_probability == 1 and hopeless.risk_level == "high"


def test_purchase_and_salary_delay_raise_probability() -> None:
    snapshot = _snap(accounts=(_account(balance=30_000 * RUB),))
    base = run_monte_carlo(snapshot)
    purchase = run_monte_carlo(
        replace(snapshot, extra_expenses=(ScenarioExpense(date(2026, 10, 20), 8_000 * RUB),))
    )
    delayed = run_monte_carlo(replace(snapshot, income_shifts=(IncomeShift("salary", 3),)))
    assert (purchase.gap_probability or 0) > (base.gap_probability or 0)
    assert (delayed.gap_probability or 0) >= (base.gap_probability or 0)
    comparison = compare(base, purchase)
    assert comparison.delta_risk is not None and comparison.delta_risk > 0
    # Общие случайные числа: покупка сдвигает квантили ровно на свою сумму.
    assert comparison.min_balance_delta_minor == -8_000 * RUB


def test_zero_probability_income_does_not_change_other_random_paths() -> None:
    """Добавление или сдвиг невозможного дохода не должно менять траты и квантили."""
    impossible = IncomeExpectation(
        "never",
        "card",
        date(2026, 11, 9),
        date(2026, 11, 9),
        1_000 * RUB,
        1_000 * RUB,
        0.0,
        False,
        "none",
        "Невозможный доход",
    )
    snapshot = _snap(incomes=(impossible,))
    base = run_monte_carlo(snapshot)
    shifted = run_monte_carlo(replace(snapshot, income_shifts=(IncomeShift("never", 5),)))
    assert shifted.points == base.points
    assert shifted.gap_probability == base.gap_probability


def test_simulation_is_independent_of_input_order() -> None:
    bonus = IncomeExpectation(
        "bonus",
        "card",
        date(2026, 10, 23),
        date(2026, 10, 25),
        2_000 * RUB,
        5_000 * RUB,
        0.4,
        False,
        "none",
        "Премия",
    )
    snapshot = _snap(incomes=(SALARY, bonus))
    reordered = replace(snapshot, incomes=(bonus, SALARY))
    assert run_monte_carlo(snapshot) == run_monte_carlo(reordered)


def test_safe_amount_is_exact_boundary_of_formula_9_4() -> None:
    snapshot = _snap(accounts=(_account(balance=40_000 * RUB),))
    base = run_monte_carlo(snapshot)
    day = date(2026, 10, 20)
    safe = safe_to_spend(base, day)
    assert safe.available and 0 <= safe.conservative_minor <= safe.base_minor

    def level_after(amount: int) -> str:
        expense = (ScenarioExpense(day, amount),)
        return run_monte_carlo(replace(snapshot, extra_expenses=expense)).risk_level

    assert level_after(safe.base_minor) != "high"
    assert level_after(safe.base_minor + 1) == "high"
    assert level_after(safe.conservative_minor) == "low"


def test_short_history_falls_back_to_deterministic_model() -> None:
    result = run_monte_carlo(_snap(history=_noisy(days=10)))
    assert result.model_version == "baseline-0.1"
    assert "simulation_skipped" in result.flags
    assert result.gap_probability is None


def test_golden_demo_profile_with_simulation() -> None:
    synthetic = pytest.importorskip("synthetic_generator")
    from forecast_core.adapters import snapshot_from_dataset

    snapshot = snapshot_from_dataset(synthetic.generate("young_specialist"))
    result = run_monte_carlo(snapshot)
    assert result.risk_level == "medium"
    assert result.risk_date == date(2026, 10, 23)
    assert 0.1 <= (result.gap_probability or 0) < 0.5
    purchase = (ScenarioExpense(date(2026, 10, 20), 12_000 * RUB),)
    assert run_monte_carlo(replace(snapshot, extra_expenses=purchase)).risk_level == "high"


def test_performance_10k_transactions_and_90_days() -> None:
    history = tuple(
        _tx(f"p{i}", -(100 + i % 900) * RUB, TxType.EXPENSE, days_ago=1 + i % 90)
        for i in range(10_000)
    )
    started = time.perf_counter()
    result = run_monte_carlo(_snap(history=history, horizon_days=90))
    assert time.perf_counter() - started < 3.0
    assert len(result.points) == 90
    assert result.points[-1].day == result.today + timedelta(days=90)
