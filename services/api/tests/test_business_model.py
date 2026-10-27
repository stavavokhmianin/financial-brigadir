import runpy
from decimal import Decimal
from pathlib import Path

import pytest

calculate = runpy.run_path(str(Path(__file__).resolve().parents[3] / "scripts/business_model.py"))[
    "calculate"
]


def test_tz_revenue_example_and_all_costs() -> None:
    result = calculate(family_share=Decimal("0.3"))
    assert result["expected_payers"] == "600.00"
    assert result["arppu"] == "244.00" and result["mrr"] == "146400.00"
    assert result["operating_result"] == "-34776.00"
    assert result["cac"] is None and result["ltv_stationary"] is None


def test_break_even_is_minimum_integer_population() -> None:
    count = calculate()["break_even_mau"]
    assert Decimal(calculate(mau=count)["operating_result"]) >= 0
    assert Decimal(calculate(mau=count - 1)["operating_result"]) < 0
    zero = calculate(conversion=Decimal("0"))
    assert zero["break_even_mau"] is None and zero["mrr"] == "0.00"


@pytest.mark.parametrize(
    "patch",
    [
        {"conversion": Decimal("1.1")},
        {"cost_per_active": Decimal("-1")},
        {"conversion": Decimal("NaN")},
        {"churn": Decimal("0")},
        {"mau": -1},
    ],
)
def test_invalid_assumptions_are_rejected(patch: dict) -> None:
    with pytest.raises(ValueError):
        calculate(**patch)
