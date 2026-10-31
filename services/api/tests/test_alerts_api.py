"""Предупреждения через API: журнал решений, подавление повторов, отзыв, метрики."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    session = client.post("/api/v1/demo/sessions", json={"profile_id": "young_specialist"}).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


def _alerts(client: TestClient, headers: dict[str, str], **params: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get(
        "/api/v1/alerts", headers=headers, params=params
    ).json()["items"]
    return items


def test_forecast_with_risk_creates_one_alert_and_suppresses_repeat(
    client: TestClient, headers: dict[str, str]
) -> None:
    client.post("/api/v1/forecasts", headers=headers, json={})
    [first] = _alerts(client, headers)
    assert first["action"] == "send"
    assert first["reason"] == "new_risk"
    assert first["risk_date"] == "2026-10-23"
    text = first["message"]
    assert "23 октября" in text and "Аренда квартиры" in text and "оценка модели" in text
    client.post("/api/v1/forecasts", headers=headers, json={})
    latest = _alerts(client, headers)[0]
    assert (latest["action"], latest["reason"]) == ("suppress", "repeat_without_change")
    assert "без существенных изменений" in latest["reason_text"]
    assert [a["id"] for a in _alerts(client, headers, action="send")] == [first["id"]]


def test_opening_alerts_marks_only_sent_events_read(
    client: TestClient, headers: dict[str, str]
) -> None:
    client.post("/api/v1/forecasts", headers=headers, json={})
    client.post("/api/v1/forecasts", headers=headers, json={})
    before = _alerts(client, headers)
    assert len(before) == 2
    assert all(item["read_at"] is None for item in before)

    marked = client.post(
        "/api/v1/alerts/read", headers=headers, json={"alert_ids": [item["id"] for item in before]}
    )
    assert marked.status_code == 200
    assert marked.json()["read_count"] == 1

    after = _alerts(client, headers)
    sent = next(item for item in after if item["action"] == "send")
    suppressed = next(item for item in after if item["action"] == "suppress")
    assert sent["read_at"] is not None
    assert suppressed["read_at"] is None
    assert (
        client.post(
            "/api/v1/alerts/read", headers=headers, json={"alert_ids": [sent["id"]]}
        ).json()["read_count"]
        == 0
    )


def test_scenario_does_not_alert(client: TestClient, headers: dict[str, str]) -> None:
    purchase = {"type": "expense", "amount_minor": 1_200_000, "date": "2026-10-20"}
    client.post("/api/v1/forecasts", headers=headers, json={"scenario": purchase})
    assert _alerts(client, headers) == []


def test_quiet_mode_suppresses_noncritical(client: TestClient, headers: dict[str, str]) -> None:
    client.patch("/api/v1/notification-settings", headers=headers, json={"mode": "quiet"})
    client.post("/api/v1/forecasts", headers=headers, json={})
    [decision] = _alerts(client, headers)
    assert (decision["action"], decision["reason"]) == ("suppress", "mode_quiet")


def test_feedback_and_disable_type(client: TestClient, headers: dict[str, str]) -> None:
    client.post("/api/v1/forecasts", headers=headers, json={})
    [alert] = _alerts(client, headers)
    response = client.patch(
        f"/api/v1/alerts/{alert['id']}", headers=headers, json={"feedback": "disable_type"}
    )
    assert response.status_code == 200 and response.json()["feedback"] == "disable_type"
    settings = client.get("/api/v1/notification-settings", headers=headers).json()
    assert settings["disabled_types"] == ["reserve_risk"]
    client.post("/api/v1/forecasts", headers=headers, json={"reserve_minor": 2_000_000})
    assert _alerts(client, headers)[0]["reason"] == "type_disabled"


def test_analytics(client: TestClient, headers: dict[str, str]) -> None:
    client.post("/api/v1/forecasts", headers=headers, json={})
    client.post("/api/v1/forecasts", headers=headers, json={})
    [_, first] = _alerts(client, headers)
    client.patch(f"/api/v1/alerts/{first['id']}", headers=headers, json={"feedback": "useful"})
    data = client.get("/api/v1/alerts/analytics", headers=headers).json()
    assert data["total_decisions"] == 2
    assert data["by_action"] == {"send": 1, "suppress": 1}
    assert data["by_reason"]["repeat_without_change"] == 1
    assert data["useful_share"] == 1.0 and data["disable_rate"] == 0.0
    assert data["sent_last_7_days"] == 1


def test_alert_ownership_and_validation(client: TestClient, headers: dict[str, str]) -> None:
    client.post("/api/v1/forecasts", headers=headers, json={})
    [alert] = _alerts(client, headers)
    other = client.post("/api/v1/demo/sessions", json={"profile_id": "two_banks"}).json()
    foreign = {"Authorization": f"Bearer {other['access_token']}"}
    url = f"/api/v1/alerts/{alert['id']}"
    assert client.patch(url, headers=foreign, json={"feedback": "useful"}).status_code == 404
    assert client.patch(url, headers=headers, json={"feedback": "meh"}).status_code == 422
    assert _alerts(client, foreign) == []


def test_no_risk_no_alert(client: TestClient) -> None:
    session = client.post("/api/v1/demo/sessions", json={"profile_id": "two_banks"}).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    client.post("/api/v1/forecasts", headers=headers, json={})
    assert _alerts(client, headers) == []


def test_regular_payment_reminder_is_created_once_and_can_be_muted(
    client: TestClient, headers: dict[str, str]
) -> None:
    obligation = client.post(
        "/api/v1/obligations",
        headers=headers,
        json={
            "title": "VK Музыка",
            "kind": "subscription",
            "amount_minor": 49_900,
            "due_date": "2026-10-20",
            "recurrence": "monthly",
            "recurrence_day": 20,
            "priority": "normal",
        },
    ).json()

    first = [a for a in _alerts(client, headers) if a["reason"] == "expected_recurring"]
    assert len(first) == 1
    assert first[0]["risk_date"] == "2026-10-20"
    assert "Завтра обычно списывается 499\u00a0₽" in first[0]["message"]
    assert len([a for a in _alerts(client, headers) if a["reason"] == "expected_recurring"]) == 1

    response = client.patch(
        f"/api/v1/alerts/{first[0]['id']}",
        headers=headers,
        json={"feedback": "disable_event"},
    )
    assert response.status_code == 200
    settings = client.get("/api/v1/notification-settings", headers=headers).json()
    assert f"expected_recurring:{obligation['id']}" in settings["disabled_types"]


def test_point_mute_is_rejected_for_reserve_risk(
    client: TestClient, headers: dict[str, str]
) -> None:
    client.post("/api/v1/forecasts", headers=headers, json={})
    [alert] = _alerts(client, headers)
    response = client.patch(
        f"/api/v1/alerts/{alert['id']}", headers=headers, json={"feedback": "disable_event"}
    )
    assert response.status_code == 400
