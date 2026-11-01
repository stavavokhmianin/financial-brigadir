# Financial SDK

Самостоятельная Python-библиотека прогнозирования личных денежных потоков. SDK принимает
нормализованные счета, операции, ожидаемые доходы и обязательства; возвращает прогноз по дням,
уровень риска, безопасную сумму и сравнение what-if сценариев.

SDK не импортирует FastAPI, SQLAlchemy, UI и банковские клиенты. Приложение выбирает, откуда
получить данные и где хранить результат.

```python
from financial_sdk import FinancialEngine, ForecastOptions, InMemoryAdapter

data = InMemoryAdapter(source=payload).load()
report = FinancialEngine().forecast(
    data,
    ForecastOptions(horizon_days=30, reserve_minor=500_000, seed=42),
)

print(report.result.risk_level)
print(report.safe_to_spend.base_minor)
print(report.to_dict())
```

Подробное руководство: [`docs/sdk.md`](../../docs/sdk.md).
