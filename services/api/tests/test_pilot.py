from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import cli
from app.core.config import Settings
from app.db.models import AuditEvent, ErasureRecord, PilotAccessCode, User
from app.db.session import get_db
from app.main import create_app
from app.modules.pilot import issue_codes, revoke_code
from app.modules.privacy import reapply_erasures

TERMS = "pilot-2026-12"


@pytest.fixture
def erasure_log(tmp_path: Path) -> Path:
    return tmp_path / "erasures.log"


@pytest.fixture
def pilot(db_session_factory: sessionmaker[Session], erasure_log: Path) -> Iterator[TestClient]:
    app = create_app(
        Settings(app_mode="pilot", pilot_terms_version=TERMS, erasure_log_path=str(erasure_log))
    )

    def _get_db() -> Iterator[Session]:
        with db_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as test_client:
        yield test_client


def code(db_session_factory: sessionmaker[Session], days: int = 30) -> str:
    with db_session_factory() as db:
        return issue_codes(db, 1, days)[0].code


def sign_in(client: TestClient, access_code: str, terms: str = TERMS) -> dict[str, Any]:
    response = client.post(
        "/api/v1/pilot/sessions",
        json={"access_code": access_code, "accepted_terms_version": terms},
    )
    return {"status": response.status_code, **response.json()}


def bearer(result: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {result['access_token']}"}


def test_meta_reports_mode(client: TestClient, pilot: TestClient) -> None:
    demo = client.get("/api/v1/meta").json()
    assert demo == {
        "mode": "demo",
        "pilot_terms_version": None,
        "demo_available": True,
        "bank_mock_available": True,
    }
    assert pilot.get("/api/v1/meta").json()["mode"] == "pilot"
    assert pilot.get("/api/v1/meta").json()["pilot_terms_version"] == TERMS


def test_demo_and_bank_mock_are_absent_in_pilot(
    pilot: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    assert pilot.get("/api/v1/demo/profiles").status_code == 404
    assert pilot.post("/api/v1/demo/sessions", json={}).status_code == 404
    headers = bearer(sign_in(pilot, code(db_session_factory)))
    for method, path in (
        ("GET", "/api/v1/connectors/bank-mock/consent"),
        ("POST", "/api/v1/connectors/bank-mock/sync"),
    ):
        response = pilot.request(method, path, headers=headers, json={})
        assert response.status_code == 404, path
        assert response.json()["error"]["code"] == "not_available"


def test_pilot_sign_in_is_absent_in_demo(client: TestClient) -> None:
    response = client.post(
        "/api/v1/pilot/sessions",
        json={"access_code": "ABCD-EFGH-JKMN-PQRS", "accepted_terms_version": TERMS},
    )
    assert response.status_code == 404


def test_first_sign_in_creates_empty_profile_and_records_terms(
    pilot: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    access_code = code(db_session_factory)
    first = sign_in(pilot, access_code)
    assert first["status"] == 201 and first["first_sign_in"] is True
    assert first["user"]["is_demo"] is False and first["user"]["plan"] == "plus"
    headers = bearer(first)
    accounts = pilot.get("/api/v1/accounts", headers=headers).json()
    assert accounts["items"] == []
    created = pilot.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Зарплатная", "type": "debit", "available_balance_minor": 4_000_000},
    )
    assert created.status_code == 201, created.text

    # Тот же код — тот же профиль; регистр и разделители не важны.
    again = sign_in(pilot, access_code.replace("-", " ").lower())
    assert again["status"] == 201 and again["first_sign_in"] is False
    assert again["user"]["id"] == first["user"]["id"]
    assert len(pilot.get("/api/v1/accounts", headers=bearer(again)).json()["items"]) == 1

    with db_session_factory() as db:
        user = db.get(User, first["user"]["id"])
        assert user is not None and user.consent_versions["pilot_terms"] == TERMS
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.user_id == user.id)))
        joined = [e for e in events if e.action == "pilot_joined"]
        assert joined and joined[0].meta == {"terms_version": TERMS}
        # Сам код нигде не хранится и не попадает в журнал.
        normalized = access_code.replace("-", "")
        assert all(normalized not in str(e.meta) for e in events)
        assert all(normalized not in row.code_hash for row in db.scalars(select(PilotAccessCode)))


def test_terms_and_code_are_checked(
    pilot: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    access_code = code(db_session_factory)
    stale = sign_in(pilot, access_code, terms="pilot-2026-11")
    assert stale["status"] == 400 and stale["error"]["code"] == "terms_not_accepted"
    assert stale["error"]["details"]["pilot_terms_version"] == TERMS
    wrong = sign_in(pilot, "ABCD-EFGH-JKMN-PQRS")
    assert wrong["status"] == 401 and wrong["error"]["code"] == "invalid_access_code"
    # Неудачные попытки не создают профилей.
    with db_session_factory() as db:
        assert db.scalars(select(User)).first() is None


def test_revoked_and_expired_codes_close_access(
    pilot: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    access_code = code(db_session_factory, days=1)
    result = sign_in(pilot, access_code)
    expires = datetime.fromisoformat(result["expires_at"])
    assert expires <= datetime.now(UTC) + timedelta(days=1, minutes=1)
    with db_session_factory() as db:
        row = db.scalars(select(PilotAccessCode)).one()
        assert revoke_code(db, row.id) is True
        assert revoke_code(db, row.id) is False
    assert sign_in(pilot, access_code)["status"] == 401

    expiring = code(db_session_factory)
    with db_session_factory() as db:
        for row in db.scalars(select(PilotAccessCode).where(PilotAccessCode.revoked_at.is_(None))):
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert sign_in(pilot, expiring)["status"] == 401


def test_delete_logs_erasure_and_disables_code(
    pilot: TestClient, db_session_factory: sessionmaker[Session], erasure_log: Path
) -> None:
    access_code = code(db_session_factory)
    result = sign_in(pilot, access_code)
    uid = result["user"]["id"]
    deleted = pilot.request(
        "DELETE", "/api/v1/privacy/profile", headers=bearer(result), json={"confirmation": "DELETE"}
    )
    assert deleted.status_code == 204
    assert erasure_log.read_text(encoding="utf-8").split() == [uid]
    assert sign_in(pilot, access_code)["status"] == 401
    with db_session_factory() as db:
        assert db.get(ErasureRecord, uid) is not None
        assert db.scalars(select(PilotAccessCode)).first() is None


def test_reapply_erasures_after_restoring_an_old_backup(
    db_session_factory: sessionmaker[Session], erasure_log: Path
) -> None:
    erasure_log.write_text("usr_gone\n", encoding="utf-8")
    with db_session_factory() as db:
        # Состояние восстановленного бэкапа: профиль снова есть, журнала в БД ещё нет.
        db.add_all([User(id="usr_gone"), User(id="usr_kept")])
        db.commit()
        assert reapply_erasures(db, str(erasure_log)) == 1
        assert db.get(User, "usr_gone") is None
        assert db.get(User, "usr_kept") is not None
        assert db.get(ErasureRecord, "usr_gone") is not None
        assert reapply_erasures(db, str(erasure_log)) == 0


def test_cli_issues_lists_and_revokes_without_leaking_codes(
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "SessionLocal", db_session_factory)
    assert cli.main(["invite", "--count", "2", "--days", "14"]) == 0
    issued = [line.split("\t") for line in capsys.readouterr().out.splitlines()]
    assert len(issued) == 2 and all(len(row[1]) == 19 for row in issued)
    assert cli.main(["list-codes"]) == 0
    listing = capsys.readouterr().out
    assert issued[0][0] in listing and issued[0][1] not in listing
    assert cli.main(["revoke-code", issued[0][0]]) == 0
    assert cli.main(["revoke-code", "pac_missing"]) == 1
    with pytest.raises(ValueError):
        with db_session_factory() as db:
            issue_codes(db, 0, 30)
