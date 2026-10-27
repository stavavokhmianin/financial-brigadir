"""IDOR по всему контракту (раздел 25): чужой объект — всегда 404 и без изменений.

Список проверяемых операций берётся из OpenAPI. Новый путь с идентификатором без
записи в CASES роняет тест: ownership-проверку нельзя забыть.
"""

from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app

# operation -> (как получить id объекта Алисы, корректное тело запроса)
CASES: dict[tuple[str, str], tuple[str, dict[str, Any] | None]] = {
    ("PATCH", "/api/v1/accounts/{account_id}"): ("accounts", {"name": "чужое"}),
    ("POST", "/api/v1/transactions/{transaction_id}/duplicate-resolution"): (
        "transactions",
        {"decision": "duplicate"},
    ),
    ("PATCH", "/api/v1/obligations/{obligation_id}"): ("obligations", {"title": "чужое"}),
    ("PATCH", "/api/v1/incomes/{income_id}"): ("incomes", {"title": "чужое"}),
    ("GET", "/api/v1/forecasts/{forecast_id}"): ("forecasts", None),
    ("PATCH", "/api/v1/alerts/{alert_id}"): ("alerts", {"feedback": "useful"}),
}


def _session(client: TestClient, profile: str) -> dict[str, str]:
    token = client.post("/api/v1/demo/sessions", json={"profile_id": profile}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def _alice_objects(client: TestClient, alice: dict[str, str]) -> dict[str, str]:
    forecast = client.post("/api/v1/forecasts", headers=alice, json={}).json()
    first = {
        kind: client.get(f"/api/v1/{kind}", headers=alice).json()["items"][0]["id"]
        for kind in ("accounts", "transactions", "obligations", "incomes", "alerts")
    }
    return {**first, "forecasts": forecast["forecast_id"]}


def test_every_id_path_is_covered() -> None:
    schema = create_app().openapi()
    operations = {
        (method.upper(), path)
        for path, ops in schema["paths"].items()
        if "{" in path
        for method in ops
    }
    assert operations == set(CASES)


def test_foreign_objects_are_not_found_and_unchanged(client: TestClient) -> None:
    alice = _session(client, "young_specialist")
    bob = _session(client, "two_banks")
    objects = _alice_objects(client, alice)
    before = {
        kind: client.get(f"/api/v1/{kind}", headers=alice).json()["items"]
        for kind in ("accounts", "obligations", "incomes", "alerts")
    }

    for (method, path), (kind, body) in CASES.items():
        url = path.split("{")[0] + objects[kind] + path.split("}")[1]
        response = client.request(method, url, headers=bob, json=body)
        assert response.status_code == 404, f"{method} {path}: {response.status_code}"
        assert response.json()["error"]["code"] == "not_found"
        # Ответ не подтверждает существование объекта и не содержит его данных.
        assert objects[kind] not in response.text

    after = {kind: client.get(f"/api/v1/{kind}", headers=alice).json()["items"] for kind in before}
    assert after == before
    assert client.get(f"/api/v1/forecasts/{objects['forecasts']}", headers=alice).status_code == 200
