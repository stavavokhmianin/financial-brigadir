from typing import Any

import pytest
from fastapi.testclient import TestClient

STATEMENT = "Дата;Сумма;Описание\n2026-10-01;-1450,00;Супермаркет\n2026-10-02;-300;Метро\n"


@pytest.fixture
def ctx(client: TestClient) -> dict[str, Any]:
    session = client.post("/api/v1/demo/sessions", json={"profile_id": "young_specialist"}).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    account = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Карта другого банка", "type": "debit", "available_balance_minor": 1_000_000},
    ).json()
    return {"headers": headers, "account_id": account["id"]}


def _post(client: TestClient, ctx: dict[str, Any], content: str, mode: str = "import",
          key: str | None = None) -> Any:  # fmt: skip
    headers = dict(ctx["headers"])
    if key:
        headers["Idempotency-Key"] = key
    return client.post(
        "/api/v1/imports/csv",
        headers=headers,
        data={"account_id": ctx["account_id"], "mode": mode, "content": content},
    )


def _count(client: TestClient, ctx: dict[str, Any]) -> int:
    page = client.get(
        "/api/v1/transactions",
        headers=ctx["headers"],
        params={"account_id": ctx["account_id"], "limit": 200},
    ).json()
    return len(page["items"])


def test_preview_does_not_write(client: TestClient, ctx: dict[str, Any]) -> None:
    response = _post(client, ctx, STATEMENT, mode="preview")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "preview" and body["import_id"] is None
    assert body["rows_total"] == 2 and len(body["preview"]) == 2
    assert body["column_mapping"] == {"date": "Дата", "amount": "Сумма", "description": "Описание"}
    assert _count(client, ctx) == 0


def test_import_is_idempotent_by_file(client: TestClient, ctx: dict[str, Any]) -> None:
    first = _post(client, ctx, STATEMENT)
    assert first.status_code == 201
    assert first.json()["rows_imported"] == 2
    again = _post(client, ctx, STATEMENT)
    assert again.status_code == 200
    assert again.json()["already_imported"] is True
    assert again.json()["import_id"] == first.json()["import_id"]
    assert _count(client, ctx) == 2


def test_overlapping_statement_skips_known_rows(client: TestClient, ctx: dict[str, Any]) -> None:
    _post(client, ctx, STATEMENT)
    overlap = STATEMENT + "2026-10-03;-700;Аптека\n"
    body = _post(client, ctx, overlap).json()
    assert (body["rows_imported"], body["rows_duplicate"]) == (1, 2)
    assert _count(client, ctx) == 3


def test_idempotency_key_conflict(client: TestClient, ctx: dict[str, Any]) -> None:
    assert _post(client, ctx, STATEMENT, key="k-1").status_code == 201
    other = _post(client, ctx, STATEMENT + "2026-10-03;-1;x\n", key="k-1")
    assert other.status_code == 409
    assert other.json()["error"]["code"] == "idempotency_conflict"


def test_partial_file_imports_valid_rows(client: TestClient, ctx: dict[str, Any]) -> None:
    body = _post(client, ctx, STATEMENT + "не дата;-1;x\n").json()
    assert (body["rows_imported"], body["rows_rejected"]) == (2, 1)
    assert body["issues"][0]["code"] == "bad_date"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("описание\nx\n", "missing_columns"),
        ("date;amount\nплохо;плохо\n", "no_valid_rows"),
    ],
)
def test_invalid_files(client: TestClient, ctx: dict[str, Any], content: str, code: str) -> None:
    response = _post(client, ctx, content)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_multipart_file_upload(client: TestClient, ctx: dict[str, Any]) -> None:
    response = client.post(
        "/api/v1/imports/csv",
        headers=ctx["headers"],
        data={"account_id": ctx["account_id"], "mode": "import"},
        files={"file": ("statement.csv", STATEMENT.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201
    assert response.json()["rows_imported"] == 2


def test_file_and_content_are_mutually_exclusive(client: TestClient, ctx: dict[str, Any]) -> None:
    response = client.post(
        "/api/v1/imports/csv",
        headers=ctx["headers"],
        data={"account_id": ctx["account_id"]},
    )
    assert response.status_code == 400


def test_too_large_file(client: TestClient, ctx: dict[str, Any]) -> None:
    big = b"date;amount\n" + b"2026-10-01;-1\n" * 160_000
    response = client.post(
        "/api/v1/imports/csv",
        headers=ctx["headers"],
        data={"account_id": ctx["account_id"]},
        files={"file": ("big.csv", big, "text/csv")},
    )
    assert response.status_code == 413


def test_foreign_account_is_not_found(client: TestClient, ctx: dict[str, Any]) -> None:
    other = client.post("/api/v1/demo/sessions", json={"profile_id": "credit_card"}).json()
    response = client.post(
        "/api/v1/imports/csv",
        headers={"Authorization": f"Bearer {other['access_token']}"},
        data={"account_id": ctx["account_id"], "content": STATEMENT},
    )
    assert response.status_code == 404


def test_imported_source_freshness_is_visible(client: TestClient, ctx: dict[str, Any]) -> None:
    _post(client, ctx, STATEMENT)
    accounts = client.get("/api/v1/accounts", headers=ctx["headers"]).json()
    kinds = {a["source"]["kind"] for a in accounts["items"]}
    assert "synthetic" in kinds
    assert accounts["data_quality"]["coverage"] == "unknown"
