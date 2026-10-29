from typing import Any

import pytest
from fastapi.testclient import TestClient


def _headers(client: TestClient, profile: str = "young_specialist") -> dict[str, str]:
    session = client.post("/api/v1/demo/sessions", json={"profile_id": profile}).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    return _headers(client)


def _forecast(client: TestClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    response = client.post("/api/v1/forecasts", headers=headers, json=body)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


def test_demo_forecast_matches_golden_story(client: TestClient, headers: dict[str, str]) -> None:
    data = _forecast(client, headers)
    assert data["model_version"] == "mc-0.2"
    assert data["today"] == "2026-10-19"
    assert data["start_balance_minor"] == 5_500_000
    assert data["reserve_minor"] == 500_000
    assert len(data["points"]) == 30 and data["points"][0]["day"] == "2026-10-20"
    assert data["risk_level"] == "medium" and data["risk_date"] == "2026-10-23"
    # Вероятность — модельная оценка симуляции, не откалиброванная на реальных данных.
    assert 0.1 <= data["baseline_risk"] < 0.5 and data["scenario_risk"] is None
    assert all(0 <= p["risk_probability"] <= 1 for p in data["points"])
    assert data["quality"]["confidence"] == "illustrative"
    labels = [d["label"] for d in data["risk"]["drivers"] if d["kind"] == "obligation"]
    assert labels[:2] == ["Аренда квартиры", "Потребкредит"]
    assert "rent" in data["risk_drivers"] and "salary_delay" in data["risk_drivers"]
    explanation = data["risk"]["explanation"]
    assert "23 октября" in explanation and "Данные на 19 октября" in explanation
    rent_day = next(p for p in data["points"] if p["day"] == "2026-10-23")
    assert rent_day["outflow_minor"] == 3_000_000
    assert data["spending"]["estimator"] == "mean" and data["spending"]["history_days"] >= 90


def test_purchase_scenario_raises_risk_without_touching_history(
    client: TestClient, headers: dict[str, str]
) -> None:
    before = client.get("/api/v1/transactions", headers=headers, params={"limit": 200}).json()
    data = _forecast(
        client,
        headers,
        scenario={"type": "expense", "amount_minor": 1_200_000, "date": "2026-10-20"},
    )
    assert data["risk_level"] == "high"
    assert data["risk"]["min_balance_minor"] < 0
    assert data["risk"]["explanation"].startswith("На 23 октября")
    assert "покупка 12 000 ₽" in data["risk"]["explanation"]
    assert "scenario_applied" in data["quality"]["flags"]
    assert data["scenario"]["amount_minor"] == 1_200_000
    after = client.get("/api/v1/transactions", headers=headers, params={"limit": 200}).json()
    assert [t["id"] for t in after["items"]] == [t["id"] for t in before["items"]]


def test_salary_delay_scenario(client: TestClient, headers: dict[str, str]) -> None:
    salary = next(
        i
        for i in client.get("/api/v1/incomes", headers=headers).json()["items"]
        if i["kind"] == "salary"
    )
    base = _forecast(client, headers)
    delayed = _forecast(
        client,
        headers,
        scenario={"type": "income_shift", "target_id": salary["id"], "shift_days": 3},
    )
    assert delayed["risk"]["min_balance_minor"] < base["risk"]["min_balance_minor"]
    assert delayed["risk_level"] == "high"


def test_reserve_and_horizon_are_respected(client: TestClient, headers: dict[str, str]) -> None:
    data = _forecast(client, headers, reserve_minor=0, horizon_days=3)
    assert len(data["points"]) == 3 and data["reserve_minor"] == 0
    assert data["risk_level"] == "low"
    assert "не опускается ниже резерва" in data["risk"]["explanation"]


def test_idempotency_and_get(client: TestClient, headers: dict[str, str]) -> None:
    key = {"Idempotency-Key": "fc-1", **headers}
    first = client.post("/api/v1/forecasts", headers=key, json={})
    second = client.post("/api/v1/forecasts", headers=key, json={})
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["forecast_id"] == second.json()["forecast_id"]
    stored = client.get(f"/api/v1/forecasts/{first.json()['forecast_id']}", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["points"] == first.json()["points"]


def test_forecast_ownership(client: TestClient, headers: dict[str, str]) -> None:
    forecast = _forecast(client, headers)
    other = _headers(client, "two_banks")
    assert (
        client.get(f"/api/v1/forecasts/{forecast['forecast_id']}", headers=other).status_code == 404
    )
    foreign_account = client.get("/api/v1/accounts", headers=headers).json()["items"][0]["id"]
    response = client.post(
        "/api/v1/forecasts", headers=other, json={"account_ids": [foreign_account]}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "account_not_found"


@pytest.mark.parametrize(
    "scenario",
    [
        {"type": "expense"},
        {"type": "income_shift", "shift_days": 2},
        {"type": "income_change", "amount_minor": 1},
    ],
)
def test_scenario_validation(
    client: TestClient, headers: dict[str, str], scenario: dict[str, Any]
) -> None:
    response = client.post("/api/v1/forecasts", headers=headers, json={"scenario": scenario})
    assert response.status_code == 422


def test_unknown_income_for_shift(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/forecasts",
        headers=headers,
        json={"scenario": {"type": "income_shift", "target_id": "inc_x", "shift_days": 2}},
    )
    assert response.status_code == 404


def test_credit_card_profile_accrues_card_spending(client: TestClient) -> None:
    data = _forecast(client, _headers(client, "credit_card"))
    assert data["risk_level"] == "low"
    assert "card_spending_accrual" in data["quality"]["flags"]
    assert any("кредитке" in note for note in data["quality"]["notes"])
