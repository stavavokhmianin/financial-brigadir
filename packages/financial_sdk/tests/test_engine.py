from datetime import UTC, date, datetime, timedelta

from financial_sdk import (
    AccountSnapshot,
    AccountType,
    FinancialData,
    FinancialEngine,
    ForecastModel,
    ForecastOptions,
    HistoricalTransaction,
    Scenario,
    ScenarioExpense,
    TxStatus,
    TxType,
)

RUB = 100
AS_OF = datetime(2026, 10, 31, 12, tzinfo=UTC)


def data(days: int = 42) -> FinancialData:
    account = AccountSnapshot(
        id="main",
        type=AccountType.DEBIT,
        currency="RUB",
        balance_minor=120_000 * RUB,
        data_as_of=AS_OF,
    )
    history = tuple(
        HistoricalTransaction(
            id=f"tx-{offset}",
            account_id=account.id,
            occurred_at=AS_OF - timedelta(days=offset),
            amount_minor=-(700 + offset % 5 * 100) * RUB,
            type=TxType.EXPENSE,
            status=TxStatus.POSTED,
            category="groceries",
        )
        for offset in range(1, days + 1)
    )
    return FinancialData(
        as_of=AS_OF,
        timezone="Europe/Moscow",
        accounts=(account,),
        transactions=history,
    )


def test_public_facade_keeps_both_model_versions() -> None:
    engine = FinancialEngine()
    baseline = engine.forecast(
        data(), ForecastOptions(model=ForecastModel.BASELINE, reserve_minor=5_000 * RUB)
    )
    monte_carlo = engine.forecast(
        data(),
        ForecastOptions(
            model=ForecastModel.MONTE_CARLO,
            reserve_minor=5_000 * RUB,
            simulations=50,
            seed=7,
        ),
    )
    assert baseline.model_version == "baseline-0.2"
    assert monte_carlo.model_version == "mc-0.3"
    assert baseline.safe_to_spend.base_minor >= baseline.safe_to_spend.conservative_minor
    assert monte_carlo.safe_to_spend.base_minor >= monte_carlo.safe_to_spend.conservative_minor


def test_short_history_falls_back_without_faking_probabilities() -> None:
    report = FinancialEngine().forecast(
        data(7), ForecastOptions(model=ForecastModel.MONTE_CARLO, simulations=20)
    )
    assert report.model_version == "baseline-0.2"
    assert "simulation_skipped" in report.result.flags
    assert report.result.gap_probability is None


def test_scenario_is_counterfactual_and_serializable() -> None:
    source = data()
    report = FinancialEngine().simulate(
        source,
        Scenario(
            expenses=(
                ScenarioExpense(
                    day=date(2026, 11, 3),
                    amount_minor=20_000 * RUB,
                    label="Ноутбук",
                ),
            )
        ),
        ForecastOptions(
            model=ForecastModel.MONTE_CARLO,
            reserve_minor=5_000 * RUB,
            simulations=50,
            seed=11,
        ),
    )
    assert report.comparison.min_balance_delta_minor == -20_000 * RUB
    assert source.transactions == data().transactions
    payload = report.to_dict()
    assert payload["base"]["result"]["model_version"] == "mc-0.3"
    assert "trajectories" not in payload["scenario"]["result"]
