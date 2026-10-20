from typing import Any

import pytest
from fastapi.testclient import TestClient


def _session(client: TestClient, profile_id: str = "young_specialist") -> dict[str, Any]:
    response = client.post("/api/v1/demo/sessions", json={"profile_id": profile_id})
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


def _auth(session: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['access_token']}"}


# --- демо ---------------------------------------------------------------


def test_demo_profiles_list_marks_post_mvp(client: TestClient) -> None:
    profiles = client.get("/api/v1/demo/profiles").json()
    assert len(profiles) >= 5
    by_id = {p["id"]: p for p in profiles}
    assert by_id["young_specialist"]["mvp"] is True
    assert by_id["family"]["mvp"] is False


def test_demo_session_creates_isolated_profile(client: TestClient) -> None:
    session = _session(client)
    assert session["token_type"] == "bearer"
    assert session["user"]["is_demo"] is True
    summary = session["summary"]
    assert summary["accounts"] == 1
    assert summary["transactions"] > 300
    assert summary["obligations"] >= 4
    quality = session["data_quality"]
    assert quality["is_demo"] is True
    assert quality["data_as_of"].startswith("2026-10-19")
    assert quality["history_days"] >= 180


def test_reupload_inside_demo_is_idempotent(client: TestClient) -> None:
    session = _session(client, "two_banks")
    assert session["summary"]["duplicates_skipped"] > 0


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"profile_id": "nobody"}, 404, "profile_not_found"),
        ({"profile_id": "family"}, 400, "profile_not_available"),
    ],
)
def test_demo_session_errors(
    client: TestClient, body: dict[str, Any], status: int, code: str
) -> None:
    response = client.post("/api/v1/demo/sessions", json=body)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_same_seed_gives_same_numbers(client: TestClient) -> None:
    first = client.get("/api/v1/accounts", headers=_auth(_session(client))).json()
    second = client.get("/api/v1/accounts", headers=_auth(_session(client))).json()
    assert first["liquid_balance_minor"] == second["liquid_balance_minor"] == 5_500_000
    assert first["items"][0]["id"] != second["items"][0]["id"]


# --- авторизация и IDOR -------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/accounts"),
        ("get", "/api/v1/transactions"),
        ("get", "/api/v1/obligations"),
        ("post", "/api/v1/forecasts"),
        ("get", "/api/v1/alerts"),
    ],
)
def test_private_endpoints_require_token(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    bad = client.request(method, path, json={}, headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


def test_cannot_read_foreign_account(client: TestClient) -> None:
    alice = _session(client)
    bob = _session(client, "credit_card")
    alice_account = client.get("/api/v1/accounts", headers=_auth(alice)).json()["items"][0]["id"]
    response = client.get(
        "/api/v1/transactions", params={"account_id": alice_account}, headers=_auth(bob)
    )
    assert response.status_code == 404
    response = client.post(
        "/api/v1/obligations",
        headers=_auth(bob),
        json={"title": "x", "amount_minor": 100, "due_date": "2026-11-01",
              "account_id": alice_account},
    )  # fmt: skip
    assert response.status_code == 404
    bob_tx = client.get("/api/v1/transactions", headers=_auth(bob), params={"limit": 200}).json()
    assert all(t["account_id"] != alice_account for t in bob_tx["items"])


# --- счета ------------------------------------------------------------------


def test_credit_limit_is_not_liquid(client: TestClient) -> None:
    session = _session(client, "credit_card")
    data = client.get("/api/v1/accounts", headers=_auth(session)).json()
    debit = next(a for a in data["items"] if a["type"] == "debit")
    card = next(a for a in data["items"] if a["type"] == "credit_card")
    assert card["is_liquid"] is False and card["credit_limit_minor"] == 15_000_000
    assert data["liquid_balance_minor"] == debit["available_balance_minor"] - debit["blocked_minor"]
    assert "Кредитный лимит не считается свободными деньгами." in data["data_quality"]["notes"]


def test_manual_account_creation(client: TestClient) -> None:
    headers = _auth(_session(client))
    before = client.get("/api/v1/accounts", headers=headers).json()["liquid_balance_minor"]
    created = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Вклад", "type": "deposit", "available_balance_minor": 10_000_000},
    )
    assert created.status_code == 201
    assert created.json()["is_liquid"] is False
    cash = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Наличные", "type": "cash", "available_balance_minor": 300_000},
    )
    assert cash.json()["source"]["kind"] == "manual"
    data = client.get("/api/v1/accounts", headers=headers).json()
    assert data["liquid_balance_minor"] == before + 300_000
    assert data["data_quality"]["coverage"] == "unknown"


@pytest.mark.parametrize(
    "body",
    [
        {"name": "Карта", "type": "credit_card", "available_balance_minor": 0},
        {"name": "Карта", "type": "debit", "available_balance_minor": 0, "credit_limit_minor": 1},
        {"name": "Карта", "type": "debit", "available_balance_minor": 1.5},
        {"name": "Карта", "type": "debit", "available_balance_minor": 0, "currency": "USD"},
        {"name": "", "type": "debit", "available_balance_minor": 0},
    ],
)
def test_manual_account_validation(client: TestClient, body: dict[str, Any]) -> None:
    headers = _auth(_session(client))
    assert client.post("/api/v1/accounts", headers=headers, json=body).status_code == 422


# --- операции ---------------------------------------------------------------


def test_transactions_cursor_pagination_is_complete_and_stable(client: TestClient) -> None:
    headers = _auth(_session(client))
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 97}
        if cursor:
            params["cursor"] = cursor
        page = client.get("/api/v1/transactions", headers=headers, params=params).json()
        seen += [t["id"] for t in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen))
    total = client.get("/api/v1/demo/profiles").json()  # профиль не меняется
    assert total
    everything = client.get("/api/v1/transactions", headers=headers, params={"limit": 200}).json()
    assert everything["items"][0]["occurred_at"] >= everything["items"][-1]["occurred_at"]


def test_transactions_filters(client: TestClient) -> None:
    headers = _auth(_session(client, "two_banks"))
    refunds = client.get(
        "/api/v1/transactions", headers=headers, params={"type": "refund", "limit": 200}
    ).json()["items"]
    assert refunds and all(r["type"] == "refund" for r in refunds)
    assert all(r["related_transaction_id"] for r in refunds)
    window = client.get(
        "/api/v1/transactions",
        headers=headers,
        params={"date_from": "2026-10-01", "date_to": "2026-10-10", "limit": 200},
    ).json()["items"]
    assert window
    assert all("2026-09-30" <= t["occurred_at"][:10] <= "2026-10-10" for t in window)
    bad = client.get("/api/v1/transactions", headers=headers, params={"cursor": "%%%"})
    assert bad.status_code == 400


# --- обязательства -----------------------------------------------------------


def test_obligations_calendar(client: TestClient) -> None:
    headers = _auth(_session(client))
    data = client.get(
        "/api/v1/obligations",
        headers=headers,
        params={"date_from": "2026-10-19", "date_to": "2026-11-30"},
    ).json()
    dates = [(c["date"], c["title"]) for c in data["calendar"]]
    assert ("2026-10-21", "Потребкредит") in dates
    assert ("2026-10-23", "Аренда квартиры") in dates
    assert ("2026-11-21", "Потребкредит") in dates
    assert {o["source_kind"] for o in data["items"]} == {"synthetic"}
    bad = client.get(
        "/api/v1/obligations", headers=headers,
        params={"date_from": "2026-11-01", "date_to": "2026-10-01"},
    )  # fmt: skip
    assert bad.status_code == 400


def test_create_obligation_on_31st(client: TestClient) -> None:
    headers = _auth(_session(client))
    created = client.post(
        "/api/v1/obligations",
        headers=headers,
        json={
            "title": "Рассрочка",
            "kind": "installment",
            "amount_minor": 650_000,
            "due_date": "2027-01-31",
            "recurrence": "monthly",
            "recurrence_day": 31,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "confirmed"
    assert created.json()["source_kind"] == "manual"
    data = client.get(
        "/api/v1/obligations",
        headers=headers,
        params={"date_from": "2027-01-01", "date_to": "2027-03-31"},
    ).json()
    days = [c["date"] for c in data["calendar"] if c["title"] == "Рассрочка"]
    assert days == ["2027-01-31", "2027-02-28", "2027-03-31"]


@pytest.mark.parametrize(
    "patch",
    [
        {"amount_minor": 0},
        {"amount_min_minor": 100},
        {"amount_min_minor": 700_000, "amount_max_minor": 900_000},
        {"recurrence_day": 5},
    ],
)
def test_obligation_validation(client: TestClient, patch: dict[str, Any]) -> None:
    headers = _auth(_session(client))
    body = {"title": "Платёж", "amount_minor": 650_000, "due_date": "2026-11-01", **patch}
    assert client.post("/api/v1/obligations", headers=headers, json=body).status_code == 422


# --- настройки уведомлений -----------------------------------------------------


def test_notification_settings_patch(client: TestClient) -> None:
    headers = _auth(_session(client))
    response = client.patch(
        "/api/v1/notification-settings",
        headers=headers,
        json={"mode": "quiet", "quiet_hours_start": "22:00:00", "quiet_hours_end": "08:00:00"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "quiet"
    assert data["max_noncritical_per_week"] == 2
    half = client.patch(
        "/api/v1/notification-settings", headers=headers, json={"quiet_hours_start": None}
    )
    assert half.status_code == 400
    too_many = client.patch(
        "/api/v1/notification-settings", headers=headers, json={"max_noncritical_per_week": 99}
    )
    assert too_many.status_code == 422


# --- контракты следующих этапов --------------------------------------------------


def test_planned_endpoints_answer_501_with_stage(client: TestClient) -> None:
    headers = _auth(_session(client))
    response = client.post("/api/v1/forecasts", headers=headers, json={"horizon_days": 30})
    assert response.status_code == 501
    error = response.json()["error"]
    assert error["code"] == "not_implemented"
    assert "этап 2" in error["details"]["planned_stage"]
    assert client.get("/api/v1/alerts", headers=headers).status_code == 501
    invalid = client.post("/api/v1/forecasts", headers=headers, json={"horizon_days": 365})
    assert invalid.status_code == 422
