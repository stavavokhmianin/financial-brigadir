from datetime import date

from basic_forecast import payload

from financial_sdk import (
    FinancialEngine,
    ForecastOptions,
    InMemoryAdapter,
    Scenario,
    ScenarioExpense,
)

data = InMemoryAdapter(payload).load()
result = FinancialEngine().simulate(
    data,
    Scenario(expenses=(ScenarioExpense(date(2026, 11, 3), 3_000_000, "Телефон"),)),
    ForecastOptions(horizon_days=30, reserve_minor=1_000_000, seed=42),
)
print(result.to_dict())
