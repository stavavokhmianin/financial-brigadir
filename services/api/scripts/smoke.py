"""Smoke-тест запущенного API: ``python scripts/smoke.py http://localhost:8000``.

Только стандартная библиотека, чтобы работать в любом контейнере.
"""

import json
import sys
import urllib.request
from typing import Any


def call(base: str, method: str, path: str, body: Any = None, token: str | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)  # noqa: S310
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return json.loads(response.read() or b"null")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"ok   {message}")


def main(base: str) -> int:
    health = call(base, "GET", "/api/v1/health/ready")
    check(health["status"] == "ok", "readiness")

    profiles = call(base, "GET", "/api/v1/demo/profiles")
    check(len(profiles) >= 5, f"демо-профилей: {len(profiles)}")

    session = call(base, "POST", "/api/v1/demo/sessions", {"profile_id": "young_specialist"})
    token = session["access_token"]
    check(session["summary"]["transactions"] > 0, "демо-профиль создан из seed")

    accounts = call(base, "GET", "/api/v1/accounts", token=token)
    check(accounts["liquid_balance_minor"] == 5_500_000, "остаток эталонного профиля 55 000 ₽")

    window = "date_from=2026-10-19&date_to=2026-10-31"
    obligations = call(base, "GET", f"/api/v1/obligations?{window}", token=token)
    check(len(obligations["calendar"]) >= 2, "календарь обязательств до зарплаты")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
