"""Регистрация создаёт постоянный изолированный профиль, вход возвращает в него же."""

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.core.limits import IngressLimits

REGISTER = {
    "display_name": "Алексей",
    "email": "alex@example.com",
    "password": "correct-horse-42",
}


def test_register_and_sign_in_return_to_the_same_profile(client: TestClient) -> None:
    created = client.post("/api/v1/auth/register", json=REGISTER)
    assert created.status_code == 201, created.text
    first = created.json()
    assert first["user"]["display_name"] == "Алексей"
    assert first["user"]["email"] == "alex@example.com"
    assert first["live"]["pending"] > 0
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    first_accounts = client.get("/api/v1/accounts", headers=first_headers).json()
    assert first_accounts["items"]

    signed_in = client.post(
        "/api/v1/auth/sessions",
        json={"email": "  ALEX@example.com ", "password": REGISTER["password"]},
    )
    assert signed_in.status_code == 201, signed_in.text
    second = signed_in.json()
    assert second["user"]["id"] == first["user"]["id"]
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    second_accounts = client.get("/api/v1/accounts", headers=second_headers).json()
    assert [item["id"] for item in second_accounts["items"]] == [
        item["id"] for item in first_accounts["items"]
    ]


def test_each_registration_has_its_own_profile(client: TestClient) -> None:
    first = client.post("/api/v1/auth/register", json=REGISTER).json()
    second = client.post(
        "/api/v1/auth/register",
        json={**REGISTER, "display_name": "Мария", "email": "maria@example.com"},
    ).json()
    assert first["user"]["id"] != second["user"]["id"]
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    first_items = client.get("/api/v1/accounts", headers=first_headers).json()["items"]
    second_items = client.get("/api/v1/accounts", headers=second_headers).json()["items"]
    first_ids = {item["id"] for item in first_items}
    second_ids = {item["id"] for item in second_items}
    assert first_ids.isdisjoint(second_ids)


def test_duplicate_email_and_bad_credentials_do_not_create_another_profile(
    client: TestClient,
) -> None:
    client.post("/api/v1/auth/register", json=REGISTER)
    duplicate = client.post("/api/v1/auth/register", json={**REGISTER, "email": "ALEX@example.com"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_exists"

    for email, password in (
        (REGISTER["email"], "wrong-password"),
        ("nobody@example.com", "wrong-password"),
    ):
        denied = client.post("/api/v1/auth/sessions", json={"email": email, "password": password})
        assert denied.status_code == 401
        assert denied.json()["error"]["code"] == "invalid_credentials"


def test_password_hash_is_not_exported(client: TestClient) -> None:
    session = client.post("/api/v1/auth/register", json=REGISTER).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    exported = client.get("/api/v1/privacy/export", headers=headers).json()
    assert "password_hash" not in exported["user"]


def test_sign_in_has_stricter_rate_limit() -> None:
    app = FastAPI()

    @app.post("/api/v1/auth/sessions")
    def denied() -> Response:
        return Response(status_code=401)

    app.add_middleware(
        IngressLimits,
        requests_per_minute=100,
        auth_requests_per_minute=2,
    )
    with TestClient(app) as limited:
        body = {"email": "nobody@example.com", "password": "wrong-password"}
        assert limited.post("/api/v1/auth/sessions", json=body).status_code == 401
        assert limited.post("/api/v1/auth/sessions", json=body).status_code == 401
        blocked = limited.post("/api/v1/auth/sessions", json=body)
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "auth_rate_limited"
