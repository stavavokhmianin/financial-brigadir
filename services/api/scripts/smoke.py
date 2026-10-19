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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
