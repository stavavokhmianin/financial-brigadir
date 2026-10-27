"""Smoke-тест запущенного API: ``python scripts/smoke.py http://localhost:8000``.

Только стандартная библиотека, чтобы работать в любом контейнере.
"""

import json
import sys
import urllib.request
from typing import Any


def call(base: str, method: str, path: str, body: Any = None, token: str | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)  # noqa: S310
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read() or b"null")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"ok   {message}")


def main(base: str) -> int:
    health = call(base, "GET", "/api/v1/health/ready")
    check(health["status"] == "ok", "readiness")

    profiles = call(base, "GET", "/api/v1/demo/profiles")
    check(len(profiles) >= 5, f"демо-профилей: {len(profiles)}")

    session = call(base, "POST", "/api/v1/demo/sessions", {"profile_id": "young_specialist"})
    token = session["access_token"]
    check(session["summary"]["transactions"] > 0, "демо-профиль создан из seed")

    accounts = call(base, "GET", "/api/v1/accounts", token=token)
    check(accounts["liquid_balance_minor"] == 5_500_000, "остаток эталонного профиля 55 000 ₽")

    window = "date_from=2026-10-19&date_to=2026-10-31"
    obligations = call(base, "GET", f"/api/v1/obligations?{window}", token=token)
    check(len(obligations["calendar"]) >= 2, "календарь обязательств до зарплаты")

    forecast = call(base, "POST", "/api/v1/forecasts", {}, token=token)
    check(
        forecast["risk_level"] == "medium" and forecast["risk_date"] == "2026-10-23",
        "прогноз: риск до зарплаты 23 октября",
    )
    purchase = {"scenario": {"type": "expense", "amount_minor": 1_200_000, "date": "2026-10-20"}}
    with_purchase = call(base, "POST", "/api/v1/forecasts", purchase, token=token)
    check(with_purchase["risk_level"] == "high", "покупка 12 000 ₽ повышает риск")

    scenario = call(
        base,
        "POST",
        "/api/v1/scenarios",
        {"base_forecast_id": forecast["forecast_id"], "events": [purchase["scenario"]]},
        token=token,
    )
    check(
        scenario["worsened"] and scenario["min_balance_delta_minor"] == -1_200_000,
        "сравнение до/после: минимум ниже на 12 000 ₽",
    )
    check(forecast["safe_to_spend"]["available"], "безопасная сумма покупки рассчитана")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
