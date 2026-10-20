from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.limits import IngressLimits
from app.db.base import Base
from app.db.models import AuthSession, User
from app.main import create_app
from app.modules.privacy import purge_expired_profiles


def session(client: TestClient) -> tuple[dict[str, str], str]:
    result = client.post("/api/v1/demo/sessions", json={"profile_id": "two_banks"}).json()
    return {"Authorization": f"Bearer {result['access_token']}"}, result["user"]["id"]


def test_export_and_delete_include_derived_data_and_isolate_users(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    alice, uid = session(client)
    bob, bob_id = session(client)
    assert client.post("/api/v1/forecasts", headers=alice, json={}).status_code == 201
    result = client.get("/api/v1/privacy/export", headers=alice)
    assert result.status_code == 200
    data = result.json()
    assert data["user"]["id"] == uid
    assert data["forecast_runs"] and data["forecast_points"]
    assert data["transactions"] and data["accounts"]
    assert bob_id not in result.text
    assert "token_hash" not in result.text and "access_token" not in result.text
    assert result.headers["cache-control"] == "no-store"
    assert (
        client.request(
            "DELETE", "/api/v1/privacy/profile", headers=alice, json={"confirmation": "no"}
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE", "/api/v1/privacy/profile", headers=alice, json={"confirmation": "DELETE"}
        ).status_code
        == 204
    )
    assert client.get("/api/v1/accounts", headers=alice).status_code == 401
    assert client.get("/api/v1/accounts", headers=bob).status_code == 200
    with db_session_factory() as db:
        assert db.get(User, uid) is None
        for table in Base.metadata.tables.values():
            if "user_id" in table.c:
                assert (
                    db.scalar(select(func.count()).select_from(table).where(table.c.user_id == uid))
                    == 0
                ), table.name
    # All rows, including self-linked transactions and forecast points, can be erased.
    assert (
        client.request(
            "DELETE", "/api/v1/privacy/profile", headers=bob, json={"confirmation": "DELETE"}
        ).status_code
        == 204
    )
    with db_session_factory() as db:
        for table in Base.metadata.tables.values():
            assert db.scalar(select(func.count()).select_from(table)) == 0, table.name


def test_logout_revokes_and_private_actions_require_auth(client: TestClient) -> None:
    headers, _ = session(client)
    assert client.post("/api/v1/privacy/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/privacy/export", headers=headers).status_code == 401
    assert (
        client.request(
            "DELETE", "/api/v1/privacy/profile", json={"confirmation": "DELETE"}
        ).status_code
        == 401
    )


def test_retention_keeps_active_sessions(
    client: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    _, expired_id = session(client)
    _, active_id = session(client)
    now = datetime.now(UTC)
    with db_session_factory() as db:
        for user in db.scalars(select(User)):
            user.created_at = now - timedelta(days=8)
        for auth in db.scalars(select(AuthSession).where(AuthSession.user_id == expired_id)):
            auth.expires_at = now - timedelta(days=1)
        db.commit()
        assert purge_expired_profiles(db, now) == 1
        assert db.get(User, expired_id) is None
        assert db.get(User, active_id) is not None


def test_validation_does_not_echo_sensitive_values(client: TestClient) -> None:
    headers, _ = session(client)
    secret = "private statement 123456789"
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": secret,
            "type": "credit_card",
            "available_balance_minor": 0,
        },
    )
    assert response.status_code == 422
    assert secret not in response.text


def test_ingress_limits_before_body_parsing() -> None:
    app = create_app()
    app.add_middleware(IngressLimits, max_bytes=100, requests_per_minute=2)
    with TestClient(app) as client:
        assert client.post("/api/v1/demo/sessions", content=b"x" * 101).status_code == 413
        assert client.post("/api/v1/demo/sessions", json={"seed": "invalid"}).status_code == 422
        result = client.post("/api/v1/demo/sessions", json={})
        assert result.status_code == 429 and result.headers["retry-after"] == "60"


def test_same_csv_on_different_accounts_and_key_conflict(client: TestClient) -> None:
    headers, _ = session(client)
    accounts = client.get("/api/v1/accounts", headers=headers).json()["items"]
    content = "date;amount;id\n2026-10-01;-100;unique\n"

    def upload(account: str, key: str) -> Any:
        return client.post(
            "/api/v1/imports/csv",
            headers={**headers, "Idempotency-Key": key},
            data={"account_id": account, "mode": "import", "content": content},
        )

    assert upload(accounts[0]["id"], "a").json()["rows_imported"] == 1
    assert upload(accounts[1]["id"], "a").status_code == 409
    second = upload(accounts[1]["id"], "b")
    assert second.status_code == 201 and second.json()["rows_imported"] == 1
    assert upload(accounts[0]["id"], "a").json()["already_imported"]
