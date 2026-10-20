"""Сравнение сценариев и безопасная сумма (разделы 9.4, 23.3)."""

from dataclasses import replace
from datetime import date

import pytest

from forecast_core.baseline import run_baseline
from forecast_core.scenarios import compare, safe_to_spend
from forecast_core.types import IncomeShift, ScenarioExpense

from .test_baseline import RUB, _snapshot


def test_safe_amount_is_exact_boundary_for_base_scenario() -> None:
    snapshot = _snapshot()
    base = run_baseline(snapshot)
    day = date(2026, 10, 20)
    safe = safe_to_spend(base, day)
    assert safe.available
    assert safe.base_minor == base.min_p50_minor - snapshot.reserve_minor
    assert 0 <= safe.conservative_minor <= safe.base_minor

    at_limit = run_baseline(
        replace(snapshot, extra_expenses=(ScenarioExpense(day, safe.base_minor),))
    )
    assert at_limit.risk_level != "high"
    over = run_baseline(
        replace(snapshot, extra_expenses=(ScenarioExpense(day, safe.base_minor + 1),))
    )
    assert over.risk_level == "high"


def test_safe_amount_later_in_month_ignores_earlier_days() -> None:
    base = run_baseline(_snapshot())
    after_salary = safe_to_spend(base, date(2026, 10, 27))
    before_rent = safe_to_spend(base, date(2026, 10, 20))
    assert after_salary.base_minor > before_rent.base_minor


def test_no_safe_amount_when_already_below_reserve_or_no_data() -> None:
    poor = run_baseline(_snapshot(reserve_minor=50_000 * RUB))
    assert safe_to_spend(poor).base_minor == 0
    nothing = run_baseline(_snapshot(accounts=(), obligations=(), incomes=(), history=()))
    assert safe_to_spend(nothing).available is False


def test_compare_purchase_and_salary_delay() -> None:
    snapshot = _snapshot()
    base = run_baseline(snapshot)
    purchase = run_baseline(
        replace(snapshot, extra_expenses=(ScenarioExpense(date(2026, 10, 20), 12_000 * RUB),))
    )
    result = compare(base, purchase)
    assert result.min_balance_delta_minor == -12_000 * RUB
    assert (result.risk_level_before, result.risk_level_after) == ("low", "high")
    assert result.risk_date_before is None and result.risk_date_after == date(2026, 10, 25)
    assert result.days_below_reserve_after > result.days_below_reserve_before == 0
    assert result.worsened

    delayed = run_baseline(replace(snapshot, income_shifts=(IncomeShift("salary", 2),)))
    shift = compare(base, delayed)
    assert shift.min_balance_delta_minor <= 0
    assert shift.days_below_reserve_after >= shift.days_below_reserve_before


def test_compare_requires_same_reserve_and_horizon() -> None:
    base = run_baseline(_snapshot())
    other = run_baseline(_snapshot(reserve_minor=0))
    with pytest.raises(ValueError):
        compare(base, other)
