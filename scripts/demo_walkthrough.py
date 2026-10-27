"""Сквозное демо из раздела 16.4: «профиль → прогноз → покупка → изменение риска».

    python scripts/demo_walkthrough.py --api http://localhost:8000   # против запущенного API
    python scripts/demo_walkthrough.py --offline                     # План Б: без сети и Docker

В офлайн-режиме API поднимается внутри процесса на SQLite в памяти из того же seed —
результаты те же, что и на стенде. Скрипт печатает реплики для показа и проверяет
ключевые числа; код возврата 1 — демо разошлось с эталоном.
"""

import argparse
import json
import sys
import urllib.request
from collections.abc import Callable
from typing import Any

Call = Callable[[str, str, Any, str | None], Any]
RUB = 100


def http_caller(base: str) -> Call:
    def call(method: str, path: str, body: Any = None, token: str | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(base + path, data=data, method=method)  # noqa: S310
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return json.loads(response.read() or b"null")

    return call


def offline_caller() -> Call:
    """API в процессе: SQLite в памяти, без сети (раздел 16.4, План Б)."""
    from collections.abc import Iterator

    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session, sessionmaker

    import app.db.models  # noqa: F401
    from app.db.base import Base
    from app.db.session import get_db, make_engine
    from app.main import create_app

    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    application = create_app()

    def _db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = _db
    client = TestClient(application)

    def call(method: str, path: str, body: Any = None, token: str | None = None) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.request(method, path, json=body, headers=headers)
        response.raise_for_status()
        return response.json()

    return call


def rub(minor: int) -> str:
    sign = "−" if minor < 0 else ""
    return f"{sign}{round(abs(minor) / RUB):,}".replace(",", " ") + " ₽"


class Demo:
    def __init__(self, call: Call) -> None:
        self.call = call
        self.failures: list[str] = []

    def say(self, step: str, text: str) -> None:
        print(f"\n[{step}] {text}")

    def expect(self, condition: bool, what: str) -> None:
        mark = "ok  " if condition else "FAIL"
        print(f"      {mark} {what}")
        if not condition:
            self.failures.append(what)

    def run(self) -> int:
        call = self.call

        self.say("1", "Выбираем демо-профиль с зарплатой, арендой и кредитом.")
        session = call("POST", "/api/v1/demo/sessions", {"profile_id": "young_specialist"}, None)
        token = session["access_token"]
        quality = session["data_quality"]
        accounts = call("GET", "/api/v1/accounts", None, token)
        print(
            f"      Свободные средства: {rub(accounts['liquid_balance_minor'])}, "
            f"данные на {quality['data_as_of'][:10]}, охват: {quality['coverage']}, "
            f"история {quality['history_days']} дн."
        )
        self.expect(accounts["liquid_balance_minor"] == 55_000 * RUB, "остаток 55 000 ₽")

        self.say("2", "Ежедневный прогноз, коридор неопределённости, день максимального риска.")
        forecast = call("POST", "/api/v1/forecasts", {}, token)
        risk = forecast["risk"]
        print(f"      {risk['explanation']}")
        print(
            f"      Минимум {rub(risk['min_balance_minor'])} ({risk['min_balance_date']}), "
            f"в плохом сценарии {rub(risk['pessimistic_min_minor'])}."
        )
        self.expect(forecast["risk_level"] == "medium", "риск «возможен»")
        self.expect(forecast["risk_date"] == "2026-10-23", "дата риска 23 октября")
        self.expect(
            forecast["quality"]["confidence"] == "illustrative",
            "вероятность помечена как модельная оценка (9.3)",
        )

        self.say("3", "Покупка 12 000 ₽: график и риск меняются без записи фиктивной операции.")
        before = call("GET", "/api/v1/transactions?limit=200", None, token)
        purchase = {
            "type": "expense",
            "amount_minor": 12_000 * RUB,
            "date": "2026-10-20",
            "label": "Телефон",
        }
        scenario = call(
            "POST",
            "/api/v1/scenarios",
            {"base_forecast_id": forecast["forecast_id"], "events": [purchase]},
            token,
        )
        print(f"      {scenario['explanation']}")
        after = call("GET", "/api/v1/transactions?limit=200", None, token)
        self.expect(scenario["risk_level_after"] == "high", "после покупки — «риск нехватки»")
        self.expect(
            scenario["min_balance_delta_minor"] == -12_000 * RUB, "минимум ниже на 12 000 ₽"
        )
        self.expect(
            [t["id"] for t in before["items"]] == [t["id"] for t in after["items"]],
            "история операций не изменилась",
        )

        self.say("4", "Сдвигаем зарплату на два дня — новый прогноз и уточнение риска.")
        incomes = call("GET", "/api/v1/incomes", None, token)
        salary = next(i for i in incomes["items"] if i["kind"] == "salary")
        shift = {"type": "income_shift", "target_id": salary["id"], "shift_days": 2}
        delayed = call(
            "POST",
            "/api/v1/scenarios",
            {"base_forecast_id": forecast["forecast_id"], "events": [shift]},
            token,
        )
        print(f"      {delayed['explanation']}")
        self.expect(delayed["min_balance_delta_minor"] < 0, "задержка зарплаты снижает минимум")
        self.expect(delayed["risk_level_after"] == "high", "задержка на 2 дня — «риск нехватки»")

        self.say("5", "Полезное предупреждение и подавление повторного сообщения.")
        alerts = call("GET", "/api/v1/alerts", None, token)["items"]
        sent = [a for a in alerts if a["action"] == "send"]
        if sent:
            print(f"      Предупреждение: {sent[0]['message']}")
        call("POST", "/api/v1/forecasts", {}, token)
        latest = call("GET", "/api/v1/alerts", None, token)["items"][0]
        print(f"      Повторный расчёт: {latest['reason_text']}.")
        print("      Демо-режим банковского API — этап 5 (контракт в OpenAPI).")
        self.expect(len(sent) == 1, "показано одно предупреждение")
        self.expect(latest["reason"] == "repeat_without_change", "повтор без изменений подавлен")

        self.say("6", "Код, тесты, отчёт сравнения с baseline, бизнес-модель с допущениями.")
        safe = forecast["safe_to_spend"]
        print(
            f"      Безопасная покупка {safe['date']}: до {rub(safe['base_minor'])} "
            f"(с запасом — до {rub(safe['conservative_minor'])})."
        )
        print("      Репозиторий: ветка step4ik; отчёт baseline: docs/backtest/baseline.md;")
        print("      бизнес-модель: docs/pitch/deck.md.")
        self.expect(safe["available"], "безопасная сумма рассчитана")

        print()
        if self.failures:
            print(f"Демо разошлось с эталоном: {', '.join(self.failures)}")
            return 1
        print("Демо 16.4 прошло: все ключевые числа совпали с эталоном.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--api", help="адрес запущенного API, например http://localhost:8000")
    mode.add_argument("--offline", action="store_true", help="План Б: API внутри процесса")
    args = parser.parse_args()
    call = offline_caller() if args.offline else http_caller(args.api.rstrip("/"))
    return Demo(call).run()


if __name__ == "__main__":
    sys.exit(main())
