from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import User


def start(client: TestClient) -> tuple[dict[str, str], str]:
    result = client.post("/api/v1/demo/sessions", json={}).json()
    assert result["user"]["plan"] == "plus"
    return {"Authorization": f"Bearer {result['access_token']}"}, result["user"]["id"]


def preview(client: TestClient, headers: dict[str, str], plan: str) -> Any:
    response = client.patch("/api/v1/plans/demo-preview", headers=headers, json={"plan": plan})
    assert response.status_code == 200, response.text
    return response.json()


def test_free_limits_both_forecast_paths_and_new_bank_accounts(client: TestClient) -> None:
    headers, _ = start(client)
    preview(client, headers, "free")
    assert client.get("/api/v1/plans", headers=headers).json()["billing_enabled"] is False
    second = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": "Second",
            "type": "cash",
            "available_balance_minor": 100,
        },
    )
    assert second.status_code == 403 and second.json()["error"]["code"] == "plan_limit"
    assert (
        client.post("/api/v1/forecasts", headers=headers, json={"horizon_days": 31}).status_code
        == 403
    )
    income = client.get("/api/v1/incomes", headers=headers).json()["items"][0]["id"]
    event = {"type": "income_shift", "target_id": income, "shift_days": 2}
    assert (
        client.post("/api/v1/forecasts", headers=headers, json={"scenario": event}).status_code
        == 403
    )
    base = client.post("/api/v1/forecasts", headers=headers, json={}).json()
    assert (
        client.post(
            "/api/v1/scenarios",
            headers=headers,
            json={"base_forecast_id": base["forecast_id"], "events": [event]},
        ).status_code
        == 403
    )
    expense = {"type": "expense", "amount_minor": 100}
    assert (
        client.post(
            "/api/v1/scenarios",
            headers=headers,
            json={"base_forecast_id": base["forecast_id"], "events": [expense, expense]},
        ).status_code
        == 403
    )
    client.post(
        "/api/v1/connectors/bank-mock/consent",
        headers=headers,
        json={"accepted": True, "scopes": ["accounts", "balances", "transactions"]},
    )
    assert (
        client.post("/api/v1/connectors/bank-mock/sync", headers=headers, json={}).status_code
        == 403
    )
    assert len(client.get("/api/v1/accounts", headers=headers).json()["items"]) == 1


def test_downgrade_preserves_data_basic_purchase_and_privacy(client: TestClient) -> None:
    headers, _ = start(client)
    client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": "Second",
            "type": "cash",
            "available_balance_minor": 100,
        },
    )
    long = client.post("/api/v1/forecasts", headers=headers, json={"horizon_days": 90}).json()
    before = client.get("/api/v1/accounts", headers=headers).json()["liquid_balance_minor"]
    assert preview(client, headers, "free")["existing_accounts_over_limit"]
    after = client.get("/api/v1/accounts", headers=headers).json()
    assert len(after["items"]) == 2 and after["liquid_balance_minor"] == before
    assert (
        client.get("/api/v1/forecasts/" + long["forecast_id"], headers=headers).status_code == 200
    )
    expense = {"type": "expense", "amount_minor": 100}
    assert (
        client.post(
            "/api/v1/scenarios",
            headers=headers,
            json={"base_forecast_id": long["forecast_id"], "events": [expense]},
        ).status_code
        == 403
    )
    base = client.post("/api/v1/forecasts", headers=headers, json={}).json()
    assert len(base["points"]) == 30
    assert (
        client.post(
            "/api/v1/scenarios",
            headers=headers,
            json={"base_forecast_id": base["forecast_id"], "events": [expense]},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/obligations",
            headers=headers,
            json={
                "title": "Manual",
                "amount_minor": 100,
                "due_date": "2026-10-25",
            },
        ).status_code
        == 201
    )
    assert client.get("/api/v1/privacy/export", headers=headers).status_code == 200
    preview(client, headers, "plus")
    assert (
        client.post("/api/v1/forecasts", headers=headers, json={"horizon_days": 90}).status_code
        == 201
    )
    client.request(
        "DELETE", "/api/v1/privacy/profile", headers=headers, json={"confirmation": "DELETE"}
    )
    assert client.get("/api/v1/accounts", headers=headers).status_code == 401


def test_plan_change_is_demo_only_and_isolated(
    client: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    headers, uid = start(client)
    other, _ = start(client)
    preview(client, headers, "free")
    assert client.get("/api/v1/plans", headers=other).json()["current_plan"] == "plus"
    with db_session_factory() as db:
        user = db.get(User, uid)
        assert user
        user.is_demo = False
        db.commit()
    assert (
        client.patch(
            "/api/v1/plans/demo-preview", headers=headers, json={"plan": "plus"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/plans/demo-preview", headers=other, json={"plan": "free", "user_id": uid}
        ).status_code
        == 422
    )
    assert client.get("/api/v1/plans").status_code == 401
