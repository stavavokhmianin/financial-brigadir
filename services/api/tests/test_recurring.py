"""Регулярные платежи: найти, подтвердить без двойного учёта, отклонить (FR-11, ADR-0007)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import RecurringDecision


def _live(client: TestClient, seed: int = 7) -> dict[str, str]:
    body = client.post("/api/v1/demo/live-sessions", json={"seed": seed}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _candidates(client: TestClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get("/api/v1/recurring", headers=headers).json()["items"]
    return items


def test_payments_already_in_calendar_are_not_proposed(client: TestClient) -> None:
    fixed = client.post("/api/v1/demo/sessions", json={}).json()
    headers = {"Authorization": f"Bearer {fixed['access_token']}"}
    # Аренда, кредит, связь, подписка и ЖКХ повторяются, но уже стоят в календаре.
    assert _candidates(client, headers) == []


def test_unregistered_monthly_payment_is_proposed(client: TestClient) -> None:
    headers = _live(client)
    items = _candidates(client, headers)
    first = items[0]
    assert (first["title"], first["period"], first["anchor"]) == ("Фитнес-клуб", "monthly", 10)
    assert first["amount_minor"] == 290_000 and first["occurrences"] >= 6
    assert first["next_date"] == "2026-11-10"
    assert 0.6 <= first["confidence"] <= 1


def test_confirm_moves_payment_from_daily_spending_to_calendar(client: TestClient) -> None:
    headers = _live(client)
    fitness = _candidates(client, headers)[0]
    before = client.post("/api/v1/forecasts", json={}, headers=headers).json()

    response = client.post(f"/api/v1/recurring/{fitness['id']}/confirm", headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    obligation = body["obligation"]
    assert obligation["title"] == "Фитнес-клуб"
    assert (obligation["recurrence"], obligation["recurrence_day"]) == ("monthly", 10)
    assert obligation["status"] == "confirmed" and obligation["due_date"] == "2026-11-10"
    assert body["effect"]["changed"] is True

    after = client.post("/api/v1/forecasts", json={}, headers=headers).json()
    # Один платёж не считается дважды: из повседневных трат он ушёл, в календаре он есть.
    assert sum(after["spending"]["daily_by_weekday_minor"]) < sum(
        before["spending"]["daily_by_weekday_minor"]
    )
    calendar = client.get(
        "/api/v1/obligations",
        params={"date_from": after["today"], "date_to": "2026-12-31"},
        headers=headers,
    ).json()["calendar"]
    assert [x["date"] for x in calendar if x["title"] == "Фитнес-клуб"] == [
        "2026-11-10",
        "2026-12-10",
    ]
    assert fitness["id"] not in {c["id"] for c in _candidates(client, headers)}
    # Платежи обязательства не спрашиваются и в «Помогите уточнить прогноз».
    queue = client.get("/api/v1/feedback", headers=headers).json()["items"]
    assert "Фитнес-клуб" not in {i["transaction"]["description"] for i in queue}


def test_rejected_candidate_is_not_proposed_again(client: TestClient) -> None:
    headers = _live(client)
    target = _candidates(client, headers)[-1]
    response = client.post(f"/api/v1/recurring/{target['id']}/reject", headers=headers)
    assert response.status_code == 204
    assert target["id"] not in {c["id"] for c in _candidates(client, headers)}
    again = client.post(f"/api/v1/recurring/{target['id']}/confirm", headers=headers)
    assert again.status_code == 404


def test_weekly_candidate_in_two_banks(client: TestClient) -> None:
    headers = _live(client, seed=2)
    weekly = [c for c in _candidates(client, headers) if c["period"] == "weekly"]
    assert [c["title"] for c in weekly] == ["Доставка воды"]
    assert weekly[0]["anchor"] == 0


def test_erasure_removes_decisions(
    client: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    headers = _live(client)
    client.post(
        f"/api/v1/recurring/{_candidates(client, headers)[0]['id']}/confirm", headers=headers
    )
    client.request(
        "DELETE", "/api/v1/privacy/profile", headers=headers, json={"confirmation": "DELETE"}
    )
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(RecurringDecision)) == 0
