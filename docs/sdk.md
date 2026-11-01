# Financial SDK

`financial-sdk` — самостоятельная Python-библиотека финансового анализа. Она принимает
нормализованные счета, операции, будущие обязательства и доходы, а возвращает прогноз
денежного потока, риск нарушения резерва, безопасную сумму и результат what-if сценария.

SDK не знает о FastAPI, SQLAlchemy, интерфейсе «Финансового бригадира», конкретном банке
или способе хранения. Приложение отвечает за получение и сохранение данных; SDK — только
за нормализацию и воспроизводимый расчёт.

## Установка и совместимость

```bash
pip install ./packages/forecast_core ./packages/financial_sdk
```

Требуется Python 3.12+. Публичный пакет следует Semantic Versioning. До версии `1.0.0`
обратная несовместимость допускается только в minor-релизе и описывается в
[`CHANGELOG.md`](../packages/financial_sdk/CHANGELOG.md). Версии математических моделей
отделены от версии библиотеки: SDK `0.1.0` содержит `baseline-0.2` и `mc-0.3`.

## Слои

```text
банк / Open Banking / CSV / приложение
                  │
             DataAdapter
                  │
       FinancialData (нормализация)
                  │
            FinancialEngine
         ┌────────┴────────┐
     baseline-0.2       mc-0.3
         └────────┬────────┘
       ForecastReport / ScenarioReport
                  │
       Python / JSON / HTTP bridge
```

- `adapters` получают данные, но ничего не рассчитывают;
- `normalization` проверяет нейтральный вход и переводит деньги в целые minor units;
- `FinancialEngine` выбирает модель и не хранит состояние пользователя;
- `serialization` делает результат JSON-safe без Pydantic;
- `forecast_core` — внутреннее математическое ядро; прикладной код импортирует
  `financial_sdk`.

## Минимальный прогноз

```python
from financial_sdk import FinancialEngine, ForecastOptions, InMemoryAdapter

payload = {
    "as_of": "2026-11-01T12:00:00+03:00",
    "timezone": "Europe/Moscow",
    "currency": "RUB",
    "accounts": [
        {
            "id": "main",
            "type": "debit",
            "balance_minor": 12_500_000,
            "data_as_of": "2026-11-01T12:00:00+03:00",
        }
    ],
    "transactions": [],
    "obligations": [
        {
            "id": "rent",
            "due_date": "2026-11-05",
            "amount_minor": 5_000_000,
            "title": "Аренда",
            "status": "confirmed",
        }
    ],
    "incomes": [],
}

data = InMemoryAdapter(payload).load()
report = FinancialEngine().forecast(
    data,
    ForecastOptions(horizon_days=30, reserve_minor=500_000, seed=42),
)

print(report.model_version)
print(report.result.risk_level)
print(report.safe_to_spend.conservative_minor)
print(report.to_dict())
```

Все суммы имеют суффикс `_minor`: для RUB это копейки. Временные метки обязаны содержать
часовой пояс. Идентификаторы принадлежат интегратору, SDK их не генерирует и не хранит.

## Сценарий «что если»

```python
from datetime import date
from financial_sdk import FinancialEngine, ForecastOptions, Scenario, ScenarioExpense

result = FinancialEngine().simulate(
    data,
    Scenario(expenses=(ScenarioExpense(date(2026, 11, 7), 3_500_000, "Телефон"),)),
    ForecastOptions(horizon_days=30, reserve_minor=500_000, seed=42),
)

print(result.comparison.delta_risk)
print(result.comparison.min_balance_delta_minor)
```

База и сценарий считаются с одинаковым seed, поэтому разница отражает событие, а не
разные случайные траектории. Входные данные при этом не изменяются.

## Выбор модели

- `ForecastModel.BASELINE` — детерминированная `baseline-0.2`;
- `ForecastModel.MONTE_CARLO` — `mc-0.3`;
- `ForecastModel.AUTO` — рекомендуемое значение, сейчас выбирает `mc-0.3`.

Если истории меньше 28 дней, `mc-0.3` честно возвращает результат `baseline-0.2` с флагом
`simulation_skipped`, а не выдумывает вероятности на недостаточных данных.

## Адаптеры

В комплекте есть:

- `InMemoryAdapter` для dict/JSON;
- `CSVTransactionsAdapter` с настраиваемыми названиями колонок и единицей денег;
- `OpenBankingAdapter` поверх асинхронного протокола `BankConnector`;
- `AdapterRegistry` для регистрации адаптеров интегратора.

Собственный синхронный адаптер реализует один метод:

```python
from financial_sdk import FinancialData


class MyAdapter:
    def load(self) -> FinancialData: ...
```

Для сетевого источника реализуется `async def load()`. SDK не запрашивает пароли банка:
`BankConnector` работает только с выданным интегратором consent token.

## Web, Android и iOS

SDK исполняется как Python-библиотека на backend или в совместимом Python runtime.
Web/Android/iOS передают нейтральный JSON через любой HTTP/RPC transport. Эталонный тонкий
FastAPI bridge находится в
[`examples/fastapi_bridge.py`](../packages/financial_sdk/examples/fastapi_bridge.py).
FastAPI не является зависимостью SDK. Текущий backend «Финансового бригадира» — один из
потребителей этой же публичной границы.

## Проверки и выпуск

```bash
ruff check packages/financial_sdk
ruff format --check packages/financial_sdk
mypy packages/forecast_core/src packages/financial_sdk/src
pytest packages/financial_sdk/tests
python -m build packages/financial_sdk
```

Публичными считаются имена из `financial_sdk.__all__`. Внутренние модули и поля
`trajectories`/`daily_history` не являются транспортным контрактом; сериализатор скрывает
их по умолчанию, чтобы ответ API не раздувался.
