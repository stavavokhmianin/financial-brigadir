"""Единая точка входа в расчётные сценарии SDK."""

from dataclasses import replace

from financial_sdk.models import (
    FinancialData,
    ForecastModel,
    ForecastOptions,
    ForecastReport,
    Scenario,
    ScenarioReport,
    with_options,
)
from forecast_core.baseline import ForecastResult, run_baseline
from forecast_core.probabilistic import run_monte_carlo
from forecast_core.scenarios import compare, safe_to_spend
from forecast_core.types import ForecastInputSnapshot


class FinancialEngine:
    """Stateless-фасад над ``baseline-0.2`` и ``mc-0.3``.

    Экземпляр не хранит пользовательские данные, поэтому его можно безопасно
    переиспользовать в CLI, сервере, worker'е или мобильном bridge-процессе.
    """

    def _run(self, snapshot: ForecastInputSnapshot, options: ForecastOptions) -> ForecastResult:
        if options.model == ForecastModel.BASELINE:
            return run_baseline(snapshot)
        return run_monte_carlo(
            snapshot,
            simulations=options.simulations,
            seed=options.seed,
        )

    def forecast(
        self,
        source: FinancialData | ForecastInputSnapshot,
        options: ForecastOptions | None = None,
    ) -> ForecastReport:
        config = options or ForecastOptions()
        snapshot = with_options(source, config)
        result = self._run(snapshot, config)
        return ForecastReport(
            result=result,
            safe_to_spend=safe_to_spend(result, config.safe_spend_day),
            requested_model=config.model,
        )

    def simulate(
        self,
        source: FinancialData | ForecastInputSnapshot,
        scenario: Scenario,
        options: ForecastOptions | None = None,
    ) -> ScenarioReport:
        config = options or ForecastOptions()
        base_snapshot = with_options(source, config)
        changed_snapshot = replace(
            base_snapshot,
            extra_expenses=(*base_snapshot.extra_expenses, *scenario.expenses),
            income_shifts=(*base_snapshot.income_shifts, *scenario.income_shifts),
        )
        base_result = self._run(base_snapshot, config)
        scenario_result = self._run(changed_snapshot, config)
        return ScenarioReport(
            base=ForecastReport(
                base_result,
                safe_to_spend(base_result, config.safe_spend_day),
                config.model,
            ),
            scenario=ForecastReport(
                scenario_result,
                safe_to_spend(scenario_result, config.safe_spend_day),
                config.model,
            ),
            comparison=compare(base_result, scenario_result),
        )


# Короткое имя для документации и интеграций; FinancialEngine остаётся явным названием класса.
FinancialSDK = FinancialEngine
