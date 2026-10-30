"""Живой учебный аккаунт и метки трат (ADR-0007)."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import LiveClock, LivePendingTransaction, Transaction
from app.modules.live import virtual_now

START = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)


def _live(client: TestClient, seed: int = 7) -> tuple[dict[str, Any], dict[str, str]]:
    response = client.post("/api/v1/demo/live-sessions", json={"seed": seed})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


def _forecast(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.post("/api/v1/forecasts", json={}, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


def test_virtual_clock_runs_pauses_skips_and_stops_at_the_end() -> None:
    real = datetime(2030, 1, 1, tzinfo=UTC)
    clock = LiveClock(
        virtual_start=START,
        virtual_end=START + timedelta(days=10),
        real_start=real,
        seconds_per_day=60,
        paused_at=None,
        paused_seconds=0.0,
        skipped_days=0,
    )
    assert virtual_now(clock, real + timedelta(seconds=90)) == START + timedelta(days=1.5)
    clock.paused_at = real + timedelta(seconds=60)
    assert virtual_now(clock, real + timedelta(hours=5)) == START + timedelta(days=1)
    clock.skipped_days = 2
    assert virtual_now(clock, real + timedelta(hours=5)) == START + timedelta(days=3)
    clock.paused_at, clock.paused_seconds = None, 600.0
    assert virtual_now(clock, real + timedelta(seconds=660)) == START + timedelta(days=3)
    assert virtual_now(clock, real + timedelta(days=1)) == START + timedelta(days=10)


def test_live_session_hides_persona_and_holds_the_future_back(
    client: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    body, headers = _live(client)
    live = body["live"]
    assert live["pending"] > 100 and live["revealed_total"] == 0
    assert live["virtual_now"].startswith("2026-10-19")
    # Учебный аккаунт помечен бейджем, плашек о синтетике и «смешанных данных» нет.
    notes = " ".join(body["data_quality"]["notes"])
    assert "синтетич" not in notes and "CSV" not in notes

    # Утечки нет: прогноз не меняется, если будущее стереть из базы целиком.
    before = _forecast(client, headers)
    with db_session_factory() as db:
        db.execute(delete(LivePendingTransaction))
        db.commit()
    after = _forecast(client, headers)
    for key in ("risk_level", "start_balance_minor", "points"):
        assert before[key] == after[key]


def test_next_day_reveals_operations_and_moves_balance_and_date(
    client: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    body, headers = _live(client)
    start_balance = client.get("/api/v1/accounts", headers=headers).json()["liquid_balance_minor"]
    with db_session_factory() as db:
        user_id = body["user"]["id"]
        first_day = list(
            db.scalars(
                select(LivePendingTransaction)
                .where(LivePendingTransaction.user_id == user_id)
                .order_by(LivePendingTransaction.occurred_at)
            )
        )

    state: dict[str, Any] = {}
    for _ in range(3):
        state = client.post("/api/v1/live/next-day", headers=headers).json()
    moment = datetime.fromisoformat(state["virtual_now"])
    revealed = [p for p in first_day if p.occurred_at <= moment]
    assert state["revealed_total"] == len(revealed) > 0
    assert state["pending"] == len(first_day) - len(revealed)

    accounts = client.get("/api/v1/accounts", headers=headers).json()
    liquid_ids = {a["id"] for a in accounts["items"] if a["is_liquid"] and a["type"] == "debit"}
    with db_session_factory() as db:
        delta = sum(
            t.amount_minor
            for t in db.scalars(
                select(Transaction).where(
                    Transaction.user_id == user_id,
                    Transaction.account_id.in_(liquid_ids),
                    Transaction.occurred_at > START,
                )
            )
        )
    assert accounts["liquid_balance_minor"] == start_balance + delta
    assert accounts["data_quality"]["data_as_of"][:10] == state["virtual_now"][:10]
    assert _forecast(client, headers)["today"] == state["virtual_now"][:10]


def test_pause_and_resume(client: TestClient) -> None:
    _, headers = _live(client)
    assert client.post("/api/v1/live/pause", headers=headers).json()["paused"] is True
    assert client.post("/api/v1/live/resume", headers=headers).json()["paused"] is False


def test_fixed_scenarios_have_no_live_clock(client: TestClient) -> None:
    fixed = client.post("/api/v1/demo/sessions", json={}).json()
    assert fixed["live"] is None
    headers = {"Authorization": f"Bearer {fixed['access_token']}"}
    response = client.get("/api/v1/live", headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_live"


def test_feedback_queue_label_effect_and_reducible_sum(client: TestClient) -> None:
    fixed = client.post("/api/v1/demo/sessions", json={}).json()
    headers = {"Authorization": f"Bearer {fixed['access_token']}"}
    queue = client.get("/api/v1/feedback", headers=headers).json()
    assert 3 <= len(queue["items"]) <= 5
    assert queue["labeled"] == 0 and queue["reducible_30d_minor"] == 0
    reasons = [item["reason"] for item in queue["items"]]
    assert reasons == sorted(reasons, key=["large", "new", "recent"].index)

    item = queue["items"][0]["transaction"]
    url = f"/api/v1/transactions/{item['id']}/label"
    one_off = client.put(
        url,
        json={"label": "one_off", "user_note": "Вернут деньги после командировки"},
        headers=headers,
    ).json()
    assert one_off["transaction"]["label"] == "one_off"
    assert one_off["transaction"]["user_note"] == "Вернут деньги после командировки"
    assert one_off["effect"]["after"]["excluded_one_off"] == 1
    assert one_off["effect"]["before"]["excluded_one_off"] == 0
    # Баланс от метки не зависит.
    forecast = _forecast(client, headers)
    assert forecast["start_balance_minor"] == fixed_start(client, headers)

    reducible = client.put(url, json={"label": "reducible"}, headers=headers).json()
    assert reducible["effect"]["before"]["excluded_one_off"] == 1
    after = client.get("/api/v1/feedback", headers=headers).json()
    assert after["labeled"] == 1
    assert after["reducible_30d_minor"] == -item["amount_minor"]
    assert item["id"] not in {i["transaction"]["id"] for i in after["items"]}

    cleared = client.put(url, json={"label": None}, headers=headers).json()
    assert cleared["transaction"]["label"] is None
    assert cleared["transaction"]["user_note"] == "Вернут деньги после командировки"


def fixed_start(client: TestClient, headers: dict[str, str]) -> int:
    accounts = client.get("/api/v1/accounts", headers=headers).json()
    return int(accounts["liquid_balance_minor"])


def test_label_only_on_own_spending(client: TestClient) -> None:
    _, headers = _live(client)
    income = client.get("/api/v1/transactions", params={"type": "income"}, headers=headers).json()[
        "items"
    ][0]
    response = client.put(
        f"/api/v1/transactions/{income['id']}/label", json={"label": "one_off"}, headers=headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "label_not_applicable"

    _, other = _live(client, seed=8)
    spend = client.get("/api/v1/feedback", headers=headers).json()["items"][0]["transaction"]
    stranger = client.put(
        f"/api/v1/transactions/{spend['id']}/label", json={"label": "regular"}, headers=other
    )
    assert stranger.status_code == 404


def test_erasure_removes_clock_and_future(
    client: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    _, headers = _live(client)
    response = client.request(
        "DELETE", "/api/v1/privacy/profile", headers=headers, json={"confirmation": "DELETE"}
    )
    assert response.status_code in (200, 204)
    with db_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(LiveClock)) == 0
        assert db.scalar(select(func.count()).select_from(LivePendingTransaction)) == 0
