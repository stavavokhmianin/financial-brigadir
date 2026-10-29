import ast
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from forecast_core import (
    AccountSnapshot,
    AccountType,
    ForecastInputSnapshot,
    ObligationEvent,
    ObligationStatus,
    format_rub,
    liquid_balance_minor,
    parse_rub_to_minor,
    snapshot_fingerprint,
)
from forecast_core.types import IncomeShift, ScenarioExpense

SRC = Path(__file__).resolve().parents[1] / "src" / "forecast_core"
FORBIDDEN_ROOTS = {"fastapi", "sqlalchemy", "alembic", "pydantic", "starlette", "app", "openai"}
AS_OF = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)


def test_core_does_not_import_framework_or_orm() -> None:
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in FORBIDDEN_ROOTS, f"{path.name}: import {name}"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1 450,00", 145000),
        ("-1450.00", -145000),
        ("12000", 1200000),
        ("0,005", 1),
        ("−5,5", -550),
        (12, 1200),
        (Decimal("0.01"), 1),
    ],
)
def test_parse_rub_to_minor(raw: str | int | Decimal, expected: int) -> None:
    assert parse_rub_to_minor(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "1,2,3", "NaN", "Infinity"])
def test_parse_rub_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_rub_to_minor(raw)


def test_parse_rub_rejects_float_and_bool() -> None:
    with pytest.raises(TypeError):
        parse_rub_to_minor(1.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_rub_to_minor(True)


@given(st.integers(min_value=-(10**12), max_value=10**12))
def test_format_parse_roundtrip(minor: int) -> None:
    text = format_rub(minor).replace(" ₽", "")
    assert parse_rub_to_minor(text) == minor


def _account(id_: str, type_: AccountType, balance: int, **kw: object) -> AccountSnapshot:
    return AccountSnapshot(
        id=id_,
        type=type_,
        currency="RUB",
        balance_minor=balance,
        data_as_of=AS_OF,
        **kw,  # type: ignore[arg-type]
    )


def test_liquid_balance_excludes_credit_and_deposit() -> None:
    accounts = [
        _account("debit", AccountType.DEBIT, 3_500_000),
        _account("card", AccountType.CREDIT_CARD, -1_200_000, credit_limit_minor=10_000_000),
        _account("deposit", AccountType.DEPOSIT, 50_000_000, is_liquid=False),
        _account("cash", AccountType.CASH, 200_000),
    ]
    assert liquid_balance_minor(accounts) == 3_700_000


def test_liquid_balance_keeps_overdraft_and_blocked() -> None:
    accounts = [
        _account("a", AccountType.DEBIT, -50_000),
        _account("b", AccountType.DEBIT, 1_000_000, blocked_minor=300_000),
    ]
    assert liquid_balance_minor(accounts) == 650_000


def test_liquid_balance_rejects_other_currency() -> None:
    usd = replace(_account("usd", AccountType.DEBIT, 100), currency="USD")
    with pytest.raises(ValueError):
        liquid_balance_minor([usd])


def test_fingerprint_is_order_independent_and_sensitive() -> None:
    a = _account("a", AccountType.DEBIT, 100)
    b = _account("b", AccountType.DEBIT, 200)
    rent = ObligationEvent(
        id="rent",
        account_id="a",
        due_date=date(2026, 10, 25),
        amount_minor=1_800_000,
        status=ObligationStatus.CONFIRMED,
        kind="rent",
    )
    s1 = ForecastInputSnapshot(AS_OF, "Europe/Moscow", 30, 500_000, (a, b), (rent,))
    s2 = ForecastInputSnapshot(AS_OF, "Europe/Moscow", 30, 500_000, (b, a), (rent,))
    assert snapshot_fingerprint(s1) == snapshot_fingerprint(s2)
    assert snapshot_fingerprint(s1) != snapshot_fingerprint(replace(s1, reserve_minor=0))

    first = ScenarioExpense(date(2026, 10, 20), 100, "A")
    second = ScenarioExpense(date(2026, 10, 21), 200, "B")
    shift_a = IncomeShift("salary", 2)
    shift_b = IncomeShift("bonus", -1)
    scenario_a = replace(s1, extra_expenses=(first, second), income_shifts=(shift_a, shift_b))
    scenario_b = replace(s1, extra_expenses=(second, first), income_shifts=(shift_b, shift_a))
    assert snapshot_fingerprint(scenario_a) == snapshot_fingerprint(scenario_b)
