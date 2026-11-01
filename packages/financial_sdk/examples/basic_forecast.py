from financial_sdk import FinancialEngine, ForecastOptions, InMemoryAdapter

payload = {
    "as_of": "2026-10-31T12:00:00+03:00",
    "timezone": "Europe/Moscow",
    "accounts": [
        {
            "id": "main",
            "type": "debit",
            "currency": "RUB",
            "balance_minor": 15_000_000,
            "data_as_of": "2026-10-31T12:00:00+03:00",
        }
    ],
    "transactions": [],
    "obligations": [
        {
            "id": "rent",
            "due_date": "2026-11-05",
            "amount_minor": 5_000_000,
            "status": "confirmed",
            "kind": "rent",
            "title": "Аренда",
        }
    ],
}

data = InMemoryAdapter(payload).load()
report = FinancialEngine().forecast(
    data,
    ForecastOptions(horizon_days=30, reserve_minor=1_000_000, seed=42),
)
print(report.to_dict())
