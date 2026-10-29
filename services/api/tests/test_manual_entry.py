"""Ручной ввод (FR-03, US-01, US-05): счета, обязательства, доходы."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    session = client.post("/api/v1/demo/sessions", json={"profile_id": "young_specialist"}).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


@pytest.fixture
def stranger(client: TestClient) -> dict[str, str]:
    session = client.post("/api/v1/demo/sessions", json={"profile_id": "freelancer"}).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


def _obligations(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get(
        "/api/v1/obligations",
        headers=headers,
        params={"date_from": "2026-10-19", "date_to": "2026-11-30"},
    ).json()["items"]
    return items


# --- счета ---------------------------------------------------------------------


def test_update_account_balance_refreshes_freshness(
    client: TestClient, headers: dict[str, str]
) -> None:
    account = client.get("/api/v1/accounts", headers=headers).json()["items"][0]
    response = client.patch(
        f"/api/v1/accounts/{account['id']}",
        headers=headers,
        json={"available_balance_minor": 4_000_000},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["available_balance_minor"] == 4_000_000
    assert updated["updated_at"] > account["updated_at"]
    total = client.get("/api/v1/accounts", headers=headers).json()["liquid_balance_minor"]
    assert total == 4_000_000


def test_account_patch_rules(
    client: TestClient, headers: dict[str, str], stranger: dict[str, str]
) -> None:
    account = client.get("/api/v1/accounts", headers=headers).json()["items"][0]
    url = f"/api/v1/accounts/{account['id']}"
    assert client.patch(url, headers=headers, json={"credit_limit_minor": 1}).status_code == 400
    assert client.patch(url, headers=stranger, json={"name": "x"}).status_code == 404


# --- обязательства ---------------------------------------------------------------


def test_confirm_inferred_obligation(client: TestClient, headers: dict[str, str]) -> None:
    inferred = next(o for o in _obligations(client, headers) if o["status"] == "inferred")
    response = client.patch(
        f"/api/v1/obligations/{inferred['id']}", headers=headers, json={"status": "confirmed"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["confidence"] == 1.0


def test_cancel_obligation_removes_it_from_calendar(
    client: TestClient, headers: dict[str, str]
) -> None:
    rent = next(o for o in _obligations(client, headers) if o["kind"] == "rent")
    client.patch(f"/api/v1/obligations/{rent['id']}", headers=headers, json={"status": "canceled"})
    data = client.get(
        "/api/v1/obligations",
        headers=headers,
        params={"date_from": "2026-10-19", "date_to": "2026-11-30"},
    ).json()
    assert all(c["obligation_id"] != rent["id"] for c in data["calendar"])
    assert all(o["id"] != rent["id"] for o in data["items"])


def test_obligation_patch_validation(
    client: TestClient, headers: dict[str, str], stranger: dict[str, str]
) -> None:
    utilities = next(o for o in _obligations(client, headers) if o["kind"] == "utilities")
    url = f"/api/v1/obligations/{utilities['id']}"
    too_big = client.patch(url, headers=headers, json={"amount_minor": 10_000_000})
    assert too_big.status_code == 400
    assert client.patch(url, headers=headers, json={"status": "inferred"}).status_code == 422
    assert client.patch(url, headers=stranger, json={"status": "canceled"}).status_code == 404


def test_create_obligation_is_idempotent(client: TestClient, headers: dict[str, str]) -> None:
    body = {
        "title": "План: ноутбук",
        "amount_minor": 12_000_00,
        "due_date": "2026-10-25",
        "priority": "normal",
        "movable": True,
    }
    keyed = {**headers, "Idempotency-Key": "scenario-plan-1"}
    first = client.post("/api/v1/obligations", headers=keyed, json=body)
    replay = client.post("/api/v1/obligations", headers=keyed, json=body)
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]

    conflict = client.post(
        "/api/v1/obligations",
        headers=keyed,
        json={**body, "amount_minor": 13_000_00},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


# --- доходы -----------------------------------------------------------------------


def test_demo_incomes_have_salary_window(client: TestClient, headers: dict[str, str]) -> None:
    data = client.get(
        "/api/v1/incomes",
        headers=headers,
        params={"date_from": "2026-10-19", "date_to": "2026-11-30"},
    ).json()
    salary = [c for c in data["calendar"] if c["title"] == "Зарплата"]
    assert [(c["date_from"], c["date_to"]) for c in salary] == [
        ("2026-10-25", "2026-10-28"),
        ("2026-11-25", "2026-11-28"),
    ]
    assert {i["source_kind"] for i in data["items"]} == {"synthetic"}


def test_create_income_with_uncertain_date(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/incomes",
        headers=headers,
        json={
            "title": "Подработка",
            "kind": "freelance",
            "amount_minor": 1_500_000,
            "amount_min_minor": 1_000_000,
            "amount_max_minor": 2_000_000,
            "date_from": "2026-10-27",
            "date_to": "2026-11-05",
            "recurrence": "none",
            "confirmed": False,
        },
    )
    assert response.status_code == 201, response.text
    income = response.json()
    assert income["probability"] == 0.7
    assert income["source_kind"] == "manual"
    shifted = client.patch(
        f"/api/v1/incomes/{income['id']}",
        headers=headers,
        json={"date_from": "2026-10-29", "confirmed": True},
    )
    assert shifted.status_code == 200
    assert shifted.json()["probability"] >= 0.95
    canceled = client.patch(
        f"/api/v1/incomes/{income['id']}", headers=headers, json={"canceled": True}
    )
    assert canceled.json()["canceled"] is True
    listing = client.get(
        "/api/v1/incomes",
        headers=headers,
        params={"date_from": "2026-10-19", "date_to": "2026-11-30"},
    ).json()
    assert all(c["income_id"] != income["id"] for c in listing["calendar"])


@pytest.mark.parametrize(
    "patch",
    [
        {"date_to": "2026-10-01"},
        {"date_to": "2026-12-31"},
        {"amount_min_minor": 100},
        {"amount_minor": 0},
    ],
)
def test_income_validation(
    client: TestClient, headers: dict[str, str], patch: dict[str, Any]
) -> None:
    body = {"title": "Доход", "amount_minor": 100_000, "date_from": "2026-10-25", **patch}
    assert client.post("/api/v1/incomes", headers=headers, json=body).status_code == 422


def test_income_ownership(
    client: TestClient, headers: dict[str, str], stranger: dict[str, str]
) -> None:
    income = client.get("/api/v1/incomes", headers=headers).json()["items"][0]
    response = client.patch(
        f"/api/v1/incomes/{income['id']}", headers=stranger, json={"canceled": True}
    )
    assert response.status_code == 404
