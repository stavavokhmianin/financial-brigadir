from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, DataSource, User
from app.domain.enums import DataSourceKind
from app.modules.quality import data_quality


def test_imported_csv_is_not_hidden_behind_demo_quality(client: TestClient) -> None:
    session = client.post("/api/v1/demo/sessions", json={}).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    account = client.get("/api/v1/accounts", headers=headers).json()["items"][0]
    response = client.post(
        "/api/v1/imports/csv",
        headers=headers,
        data={
            "account_id": account["id"],
            "mode": "import",
            "content": "date;amount\n2020-01-01;-100\ninvalid;bad\n",
        },
    )
    assert response.status_code == 201
    quality = client.get("/api/v1/accounts", headers=headers).json()["data_quality"]
    assert quality["is_demo"] is False and quality["stale"] is True
    assert quality["coverage"] == "partial"
    assert quality["history_days"] >= 0
    assert "смешаны" in " ".join(quality["notes"])
    forecast = client.post("/api/v1/forecasts", headers=headers, json={})
    assert forecast.status_code == 201
    assert "stale_data" in forecast.json()["quality"]["flags"]


def test_manual_balance_has_freshness(
    client: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    session = client.post("/api/v1/demo/sessions", json={}).json()
    now = datetime.now(UTC)
    with db_session_factory() as db:
        user = db.get(User, session["user"]["id"])
        assert user
        user.is_demo = False
        source = db.scalar(select(DataSource).where(DataSource.user_id == user.id))
        assert source
        source.kind = DataSourceKind.MANUAL
        source.data_as_of = None
        source.history_from = None
        account = db.scalar(select(Account).where(Account.user_id == user.id))
        assert account
        account.updated_at = now - timedelta(days=10)
        db.commit()
        quality = data_quality(db, user, now)
        assert quality.data_as_of == account.updated_at and quality.stale


def test_sql_like_identifiers_cannot_select_foreign_data(client: TestClient) -> None:
    session = client.post("/api/v1/demo/sessions", json={}).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    response = client.patch(
        "/api/v1/accounts/' OR 1=1 --", headers=headers, json={"name": "should not update anything"}
    )
    assert response.status_code == 404
    response = client.get(
        "/api/v1/transactions", headers=headers, params={"account_id": "' OR 1=1 --"}
    )
    assert response.status_code == 404 or response.json()["items"] == []
