"""What-if (разделы 11.3, 16.4): сравнение «до/после» и безопасная сумма."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    session = client.post("/api/v1/demo/sessions", json={"profile_id": "young_specialist"}).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


def _base(client: TestClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    response = client.post("/api/v1/forecasts", headers=headers, json=body)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


def _scenario(
    client: TestClient, headers: dict[str, str], base_id: str, *events: dict[str, Any]
) -> Any:
    return client.post(
        "/api/v1/scenarios",
        headers=headers,
        json={"base_forecast_id": base_id, "events": list(events)},
    )


PURCHASE = {"type": "expense", "amount_minor": 1_200_000, "date": "2026-10-20", "label": "Телефон"}


def test_forecast_has_safe_to_spend_range(client: TestClient, headers: dict[str, str]) -> None:
    base = _base(client, headers)
    safe = base["safe_to_spend"]
    assert safe["available"] is True
    assert safe["date"] == "2026-10-20"
    assert safe["base_minor"] == base["risk"]["min_balance_minor"] - base["reserve_minor"]
    assert 0 <= safe["conservative_minor"] <= safe["base_minor"]


def test_purchase_scenario_compares_before_and_after(
    client: TestClient, headers: dict[str, str]
) -> None:
    base = _base(client, headers)
    response = _scenario(client, headers, base["forecast_id"], PURCHASE)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["base"]["forecast_id"] == base["forecast_id"]
    assert data["base_recomputed"] is False
    assert data["min_balance_delta_minor"] == -1_200_000
    assert (data["risk_level_before"], data["risk_level_after"]) == ("medium", "high")
    assert data["risk_date_after"] == "2026-10-23"
    assert data["worsened"] is True
    assert data["days_below_reserve_after"] > data["days_below_reserve_before"]
    assert data["delta_risk"] is None
    text = data["explanation"]
    assert text.startswith("Если 20 октября купить «Телефон» за 12 000 ₽")
    assert "можно потратить до" in text
    stored = client.get(f"/api/v1/forecasts/{data['result']['forecast_id']}", headers=headers)
    assert stored.json()["scenario"]["amount_minor"] == 1_200_000


def test_small_purchase_within_safe_amount_keeps_level(
    client: TestClient, headers: dict[str, str]
) -> None:
    base = _base(client, headers)
    amount = base["safe_to_spend"]["base_minor"]
    data = _scenario(
        client,
        headers,
        base["forecast_id"],
        {"type": "expense", "amount_minor": amount, "date": "2026-10-20"},
    ).json()
    assert data["risk_level_after"] != "high"
    assert data["worsened"] is False


def test_salary_delay_and_combined_events(client: TestClient, headers: dict[str, str]) -> None:
    salary = next(
        i
        for i in client.get("/api/v1/incomes", headers=headers).json()["items"]
        if i["kind"] == "salary"
    )
    base = _base(client, headers)
    shift = {"type": "income_shift", "target_id": salary["id"], "shift_days": 2}
    delayed = _scenario(client, headers, base["forecast_id"], shift).json()
    assert delayed["min_balance_delta_minor"] < 0
    assert "доход придёт на 2 дн. позже" in delayed["explanation"]
    both = _scenario(client, headers, base["forecast_id"], PURCHASE, shift).json()
    assert both["min_balance_delta_minor"] < delayed["min_balance_delta_minor"]


def test_base_is_recomputed_when_data_changed(client: TestClient, headers: dict[str, str]) -> None:
    base = _base(client, headers)
    client.post(
        "/api/v1/obligations",
        headers=headers,
        json={"title": "Стоматолог", "amount_minor": 800_000, "due_date": "2026-10-22"},
    )
    data = _scenario(client, headers, base["forecast_id"], PURCHASE).json()
    assert data["base_recomputed"] is True
    assert data["base"]["forecast_id"] != base["forecast_id"]
    assert data["base"]["risk"]["min_balance_minor"] < base["risk"]["min_balance_minor"]


def test_scenario_errors(client: TestClient, headers: dict[str, str]) -> None:
    assert _scenario(client, headers, "fc_missing", PURCHASE).status_code == 404
    base = _base(client, headers)
    assert _scenario(client, headers, base["forecast_id"]).status_code == 422
    other = client.post("/api/v1/demo/sessions", json={"profile_id": "two_banks"}).json()
    foreign = {"Authorization": f"Bearer {other['access_token']}"}
    assert _scenario(client, foreign, base["forecast_id"], PURCHASE).status_code == 404
