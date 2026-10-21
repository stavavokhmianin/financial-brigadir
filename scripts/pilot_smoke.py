"""Smoke-тест пилотного контура через TLS-прокси (только стандартная библиотека).

    python scripts/pilot_smoke.py check  https://localhost:8443 --ca certs/tls.crt --code XXXX-…
    python scripts/pilot_smoke.py join   … --code …   # создать профиль со счётом
    python scripts/pilot_smoke.py erase  … --code …   # удалить профиль
    python scripts/pilot_smoke.py denied … --code …   # код больше не пускает

Сертификат проверяется по переданному --ca, а не отключением проверки.
"""

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

TERMS = "pilot-2026-12"


class Client:
    def __init__(self, base: str, ca: str | None) -> None:
        self.base = base.rstrip("/")
        # Без --ca — только локальная отладка API по http, без прокси.
        self.context = ssl.create_default_context(cafile=ca) if ca else None

    def call(
        self, method: str, path: str, body: Any = None, token: str | None = None
    ) -> tuple[int, Any, dict[str, str]]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method)  # noqa: S310
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=15, context=self.context) as response:  # noqa: S310
                raw = response.read()
                status, headers = response.status, dict(response.headers)
        except urllib.error.HTTPError as error:
            raw, status, headers = error.read(), error.code, dict(error.headers)
        try:
            payload = json.loads(raw or b"null")
        except ValueError:
            payload = raw.decode("utf-8", "replace")
        return status, payload, headers

    def sign_in(self, code: str) -> tuple[int, Any]:
        status, payload, _ = self.call(
            "POST",
            "/api/v1/pilot/sessions",
            {"access_code": code, "accepted_terms_version": TERMS},
        )
        return status, payload


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL {message}")
    print(f"ok   {message}")


def run_proxy_checks(client: Client) -> None:
    status, page, headers = client.call("GET", "/")
    check(status == 200 and "<html" in str(page).lower(), "web-клиент отдаётся по HTTPS")
    check("max-age" in headers.get("Strict-Transport-Security", ""), "HSTS")
    check("frame-ancestors 'none'" in headers.get("Content-Security-Policy", ""), "CSP")

    status, meta, _ = client.call("GET", "/api/v1/meta")
    check(status == 200 and meta["mode"] == "pilot", "режим стенда: pilot")

    # Общий limiter прокси: подбор кода упирается в 429.
    statuses = [client.sign_in("ZZZZ-ZZZZ-ZZZZ-ZZZZ")[0] for _ in range(10)]
    check(401 in statuses and 429 in statuses, f"подбор кода ограничен: {sorted(set(statuses))}")


def run_api_checks(client: Client, code: str) -> None:
    check(client.call("GET", "/api/v1/demo/profiles")[0] == 404, "демо-профили выключены")
    check(client.call("GET", "/api/v1/docs")[0] == 404, "Swagger в пилоте выключен")

    status, session = client.sign_in(code)
    check(status == 201 and session["first_sign_in"], "первый вход по коду участника")
    check(session["user"]["is_demo"] is False, "профиль не демо")
    token = session["access_token"]
    bank = client.call("POST", "/api/v1/connectors/bank-mock/sync", {}, token)[0]
    check(bank == 404, "учебный банк выключен")

    status, _, _ = client.call(
        "POST",
        "/api/v1/accounts",
        {"name": "Зарплатная", "type": "debit", "available_balance_minor": 4_000_000},
        token,
    )
    check(status == 201, "счёт добавлен вручную")
    status, _, _ = client.call(
        "POST",
        "/api/v1/obligations",
        {
            "title": "Аренда",
            "kind": "rent",
            "amount_minor": 3_000_000,
            "due_date": (datetime.now(UTC).date() + timedelta(days=10)).isoformat(),
            "recurrence": "monthly",
        },
        token,
    )
    check(status == 201, "обязательство добавлено")
    status, forecast, _ = client.call("POST", "/api/v1/forecasts", {}, token)
    check(status == 201 and forecast["risk_level"] in {"low", "medium", "high"}, "прогноз")
    status, export, _ = client.call("GET", "/api/v1/privacy/export", None, token)
    check(status == 200 and export["accounts"], "экспорт своих данных")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check", "join", "erase", "denied"])
    parser.add_argument("base")
    parser.add_argument("--ca")
    parser.add_argument("--code", required=True)
    args = parser.parse_args()
    client = Client(args.base, args.ca)

    if args.command == "check":
        # Сначала API (код ещё не потрачен лимитом), затем заголовки и limiter прокси.
        run_api_checks(client, args.code)
        if args.ca:
            run_proxy_checks(client)
    elif args.command == "join":
        status, session = client.sign_in(args.code)
        check(status == 201, "вход участника")
        status, _, _ = client.call(
            "POST",
            "/api/v1/accounts",
            {"name": "Карта", "type": "debit", "available_balance_minor": 1_000_000},
            session["access_token"],
        )
        check(status == 201, f"профиль {session['user']['id']} со счётом")
    elif args.command == "erase":
        status, session = client.sign_in(args.code)
        check(status == 201, "вход участника")
        status, _, _ = client.call(
            "DELETE",
            "/api/v1/privacy/profile",
            {"confirmation": "DELETE"},
            session["access_token"],
        )
        check(status == 204, "профиль удалён")
    else:
        check(client.sign_in(args.code)[0] == 401, "удалённый профиль не восстановился")
    return 0


if __name__ == "__main__":
    sys.exit(main())
