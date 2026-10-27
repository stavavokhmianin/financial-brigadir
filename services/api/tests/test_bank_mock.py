import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.bank import BankConnector, ConsentToken
from app.adapters.bank_mock import SCOPES, BankAccessError, BankMockConnector
from app.db.models import BankConsent

PREFIX = "/api/v1/connectors/bank-mock"


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    result = client.post("/api/v1/demo/sessions", json={}).json()
    return {"Authorization": f"Bearer {result['access_token']}"}


def grant(client: TestClient, headers: dict[str, str], scopes: tuple[str, ...] = SCOPES) -> Any:
    return client.post(
        PREFIX + "/consent", headers=headers, json={"accepted": True, "scopes": list(scopes)}
    )


def sync(client: TestClient, headers: dict[str, str], scenario: str = "ok") -> Any:
    return client.post(PREFIX + "/sync", headers=headers, json={"scenario": scenario})


def snapshot(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    data: dict[str, Any] = client.get("/api/v1/privacy/export", headers=headers).json()
    for key in ("audit_events", "exported_at"):
        data.pop(key)
    return data


def test_connector_protocol_pagination_scopes_and_revoke() -> None:
    async def check() -> None:
        consent = ConsentToken("test", SCOPES, datetime.now(UTC) + timedelta(hours=1))
        connector: BankConnector = BankMockConnector(consent)
        account = (await connector.list_accounts(consent))[0]
        balance = await connector.get_balances(account.external_id)
        assert balance.available_minor > 0
        items = []
        cursor = None
        pages = 0
        while True:
            page = await connector.list_transactions(
                account.external_id,
                date(2026, 1, 1),
                date(2026, 10, 19),
                cursor,
            )
            items.extend(page.items)
            pages += 1
            cursor = page.next_cursor
            if cursor is None:
                break
        assert pages > 1 and len({i.external_id for i in items}) == len(items)
        await connector.revoke_access(consent)
        with pytest.raises(BankAccessError):
            await connector.get_balances(account.external_id)

    asyncio.run(check())


def test_sync_replay_and_user_isolation(client: TestClient, headers: dict[str, str]) -> None:
    other = client.post("/api/v1/demo/sessions", json={}).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert sync(client, headers).status_code == 403
    assert grant(client, headers).status_code == 200
    initial = sync(client, headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["transactions_new"] > 100
    before = snapshot(client, headers)
    replay = sync(client, headers, "duplicates").json()
    assert replay["transactions_new"] == 0 and replay["transactions_duplicate"] > 100
    after = snapshot(client, headers)
    assert after["accounts"] == before["accounts"]
    assert after["transactions"] == before["transactions"]
    assert client.get(PREFIX + "/consent", headers=other_headers).json() is None
    assert sync(client, other_headers).status_code == 403
    assert all(
        a["bank_name"] != "Учебный банк" for a in snapshot(client, other_headers)["accounts"]
    )
    # Consent and its source participate in export/erasure.
    assert after["bank_consents"]
    assert (
        client.request(
            "DELETE", "/api/v1/privacy/profile", headers=headers, json={"confirmation": "DELETE"}
        ).status_code
        == 204
    )


def test_network_failure_rolls_back_all_pages_and_retry_succeeds(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    grant(client, headers)
    before = snapshot(client, headers)
    response = sync(client, headers, "network_error")
    assert response.status_code == 503 and response.headers["retry-after"] == "1"
    assert snapshot(client, headers) == before
    assert sync(client, headers).status_code == 200


def test_partial_then_complete_and_delayed_update(
    client: TestClient, headers: dict[str, str]
) -> None:
    grant(client, headers)
    delayed = sync(client, headers, "delayed").json()
    assert delayed["data_as_of"].startswith("2026-10-17")
    partial = sync(client, headers, "partial").json()
    assert partial["status"] == "partial"
    quality = client.get("/api/v1/accounts", headers=headers).json()["data_quality"]
    assert quality["coverage"] == "partial"
    complete = sync(client, headers).json()
    assert complete["transactions_new"] > 0
    assert complete["data_as_of"].startswith("2026-10-19")
    assert sync(client, headers, "delayed").status_code == 409
    assert not any(s["is_partial"] for s in snapshot(client, headers)["data_sources"])


def test_expiry_revocation_and_scopes(
    client: TestClient,
    headers: dict[str, str],
    db_session_factory: sessionmaker[Session],
) -> None:
    assert (
        client.post(PREFIX + "/consent", headers=headers, json={"scopes": list(SCOPES)}).status_code
        == 422
    )
    grant(client, headers, ("accounts",))
    assert sync(client, headers).status_code == 403
    grant(client, headers)
    assert sync(client, headers, "consent_expired").status_code == 403
    uid = snapshot(client, headers)["user"]["id"]
    with db_session_factory() as db:
        consent = db.get(BankConsent, uid)
        assert consent is not None
        consent.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert sync(client, headers).status_code == 403
    grant(client, headers)
    assert sync(client, headers).status_code == 200
    before = snapshot(client, headers)["transactions"]
    assert client.delete(PREFIX + "/consent", headers=headers).status_code == 204
    assert sync(client, headers).status_code == 403
    assert snapshot(client, headers)["transactions"] == before
    grant(client, headers)
    assert sync(client, headers).json()["transactions_new"] == 0
