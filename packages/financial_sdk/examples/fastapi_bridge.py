"""Тонкий HTTP-bridge: FastAPI — потребитель SDK, а не его зависимость."""

from typing import Any

from fastapi import FastAPI

from financial_sdk import FinancialEngine, ForecastOptions, InMemoryAdapter

app = FastAPI()
engine = FinancialEngine()


@app.post("/forecast")
def forecast(payload: dict[str, Any]) -> dict[str, object]:
    data = InMemoryAdapter(payload["data"]).load()
    report = engine.forecast(
        data,
        ForecastOptions(
            horizon_days=int(payload.get("horizon_days", 30)),
            reserve_minor=int(payload.get("reserve_minor", 0)),
            seed=int(payload.get("seed", 0)),
        ),
    )
    return report.to_dict()
