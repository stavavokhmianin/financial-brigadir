"""Вероятные дубли (FR-08): находим, показываем, решает пользователь."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from synthetic_generator import generate


def _headers(client: TestClient, profile: str, seed: int = 42) -> dict[str, str]:
    session = client.post("/api/v1/demo/sessions", json={"profile_id": profile, "seed": seed})
    return {"Authorization": f"Bearer {session.json()['access_token']}"}


def _duplicates(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get(
        "/api/v1/transactions/duplicates", headers=headers
    ).json()["items"]
    return items


@pytest.mark.parametrize("seed", [42, 7])
def test_detects_exactly_the_generator_duplicates(client: TestClient, seed: int) -> None:
    headers = _headers(client, "two_banks", seed)
    found = _duplicates(client, headers)
    truth = generate("two_banks", seed=seed)["truth"]["duplicate_external_ids"]
    assert len(found) == len(truth) > 0
    for pair in found:
        tx, original = pair["transaction"], pair["original"]
        assert pair["reason"] == "same_moment"
        assert tx["amount_minor"] == original["amount_minor"]
        assert tx["occurred_at"] == original["occurred_at"]
        assert tx["booked_at"] != original["booked_at"]
        assert tx["needs_review"] is True


@pytest.mark.parametrize("profile", ["young_specialist", "credit_card", "freelancer"])
def test_no_false_duplicates_on_clean_profiles(client: TestClient, profile: str) -> None:
    assert _duplicates(client, _headers(client, profile)) == []


def test_quality_note_and_resolution(client: TestClient) -> None:
    headers = _headers(client, "two_banks")
    accounts = client.get("/api/v1/accounts", headers=headers).json()
    assert any("вероятные дубли" in note for note in accounts["data_quality"]["notes"])
    first, second = _duplicates(client, headers)
    url = "/api/v1/transactions/{}/duplicate-resolution"
    confirmed = client.post(
        url.format(first["transaction"]["id"]), headers=headers, json={"decision": "duplicate"}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["duplicate_of_id"] == first["original"]["id"]
    rejected = client.post(
        url.format(second["transaction"]["id"]),
        headers=headers,
        json={"decision": "not_duplicate"},
    )
    assert rejected.json()["review_reason"] == "not_duplicate"
    assert _duplicates(client, headers) == []
    notes = client.get("/api/v1/accounts", headers=headers).json()["data_quality"]["notes"]
    assert not any("вероятные дубли" in note for note in notes)


def test_confirmed_duplicate_leaves_spending_model(client: TestClient) -> None:
    headers = _headers(client, "two_banks")
    before = client.post("/api/v1/forecasts", headers=headers, json={}).json()
    for pair in _duplicates(client, headers):
        client.post(
            f"/api/v1/transactions/{pair['transaction']['id']}/duplicate-resolution",
            headers=headers,
            json={"decision": "duplicate"},
        )
    after = client.post("/api/v1/forecasts", headers=headers, json={}).json()
    spent_before = sum(before["spending"]["daily_by_weekday_minor"])
    spent_after = sum(after["spending"]["daily_by_weekday_minor"])
    assert spent_after < spent_before


def test_cross_source_duplicate_between_demo_and_csv(client: TestClient) -> None:
    headers = _headers(client, "young_specialist")
    account = client.get("/api/v1/accounts", headers=headers).json()["items"][0]
    page = client.get(
        "/api/v1/transactions",
        headers=headers,
        params={"account_id": account["id"], "type": "expense", "limit": 5},
    ).json()["items"]
    tx = next(t for t in page if t["status"] == "posted")
    amount = f"{tx['amount_minor'] / 100:.2f}".replace(".", ",")
    csv = f"Дата;Сумма;Описание\n{tx['occurred_at'][:10]};{amount};{tx['description']}\n"
    response = client.post(
        "/api/v1/imports/csv",
        headers=headers,
        data={"account_id": account["id"], "mode": "import", "content": csv},
    )
    assert response.status_code == 201
    pairs = _duplicates(client, headers)
    assert [p["reason"] for p in pairs] == ["cross_source"]
    assert pairs[0]["original"]["id"] == tx["id"] or pairs[0]["transaction"]["id"] == tx["id"]


def test_resolution_errors(client: TestClient) -> None:
    headers = _headers(client, "young_specialist")
    tx = client.get("/api/v1/transactions", headers=headers, params={"limit": 1}).json()
    url = f"/api/v1/transactions/{tx['items'][0]['id']}/duplicate-resolution"
    assert client.post(url, headers=headers, json={"decision": "duplicate"}).status_code == 400
    assert client.post(url, headers=headers, json={"decision": "maybe"}).status_code == 422
    other = _headers(client, "two_banks")
    pair = _duplicates(client, other)[0]
    foreign = f"/api/v1/transactions/{pair['transaction']['id']}/duplicate-resolution"
    assert client.post(foreign, headers=headers, json={"decision": "duplicate"}).status_code == 404
