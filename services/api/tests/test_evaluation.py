from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import cli
from app.db.models import ForecastPoint, ForecastRun, User
from app.domain.ids import new_id
from app.modules.evaluation import collect, render, summarize

RESERVE = 500_000
START = date(2026, 12, 1)


def _run(
    db: Session,
    user_id: str,
    moment: datetime,
    balance: int,
    *,
    points: dict[date, tuple[int, int, int]] | None = None,
    calendar: dict[date, int] | None = None,
    scenario: bool = False,
    stale: bool = False,
) -> None:
    run = ForecastRun(
        id=new_id("fc"),
        user_id=user_id,
        as_of=moment,
        horizon_days=30,
        reserve_minor=RESERVE,
        model_version="mc-0.2",
        input_snapshot={
            "timezone": "Europe/Moscow",
            "accounts": [
                {"type": "debit", "balance_minor": balance, "is_liquid": True, "blocked_minor": 0},
                {"type": "credit_card", "balance_minor": 9_999_999, "is_liquid": False},
            ],
        },
        input_fingerprint="x",
        quality_flags={"flags": ["stale_data"] if stale else []},
        scenario={"events": [{"type": "expense"}]} if scenario else None,
        reference={"calendar": {d.isoformat(): v for d, v in (calendar or {}).items()}},
    )
    db.add(run)
    db.flush()
    for day, (p10, p50, p90) in (points or {}).items():
        db.add(ForecastPoint(run_id=run.id, day=day, p10_minor=p10, p50_minor=p50, p90_minor=p90))
    db.commit()


def _at(day: date, hour: int) -> datetime:
    # 10:00 по Москве = 07:00 UTC: день наблюдения считается в часовом поясе пользователя.
    return datetime(day.year, day.month, day.day, hour - 3, tzinfo=UTC)


def _participant(db: Session, *, demo: bool = False) -> str:
    user = User(id=new_id("usr"), is_demo=demo)
    db.add(user)
    db.commit()
    d2, d5 = START + timedelta(days=1), START + timedelta(days=4)
    _run(
        db,
        user.id,
        _at(START, 10),
        2_000_000,
        points={d2: (900_000, 1_000_000, 1_100_000), d5: (450_000, 600_000, 700_000)},
        calendar={d2: 1_500_000, d5: 1_200_000},
    )
    # Сценарий не прогноз: его точки не оцениваются.
    _run(db, user.id, _at(START, 11), 2_000_000, points={d2: (0, 0, 0)}, scenario=True)
    _run(db, user.id, _at(START + timedelta(days=2), 9), 1_050_000)  # факт на 2 декабря
    _run(db, user.id, _at(START + timedelta(days=2), 18), 7_777_777)  # не самый ранний
    _run(db, user.id, _at(START + timedelta(days=4), 9), 9_999_999, stale=True)  # устарело
    _run(db, user.id, _at(START + timedelta(days=5), 9), 400_000)  # факт на 5 декабря
    return user.id


@pytest.fixture
def three(db_session_factory: sessionmaker[Session]) -> list[str]:
    with db_session_factory() as db:
        return [_participant(db) for _ in range(3)]


def test_pairs_follow_matching_rules(
    db_session_factory: sessionmaker[Session], three: list[str]
) -> None:
    with db_session_factory() as db:
        report = collect(db)
    assert report.users == 3 and report.runs == 3
    assert len(report.pairs) == 6
    by_lead = {p.lead_days: p for p in report.pairs if p.user_id == three[0]}
    assert by_lead[1].actual == 1_050_000 and by_lead[1].calendar == 1_500_000
    assert by_lead[4].actual == 400_000

    summary = summarize(report.pairs)
    assert summary is not None
    assert summary.mae == pytest.approx((50_000 + 200_000) / 2)
    assert summary.mae_calendar == pytest.approx((450_000 + 800_000) / 2)
    assert summary.coverage == pytest.approx(0.5)
    # 5 декабря факт 400 000 ниже резерва и вне коридора; p10 450 000 риск видел, p50 — нет.
    assert summary.gaps_observed == 3
    assert summary.gaps_seen_in_range == 3 and summary.gaps_seen_by_median == 0
    assert summary.false_alarm_days == 0


def test_report_is_aggregated_and_excludes_demo(
    db_session_factory: sessionmaker[Session], three: list[str]
) -> None:
    with db_session_factory() as db:
        _participant(db, demo=True)
        report = collect(db)
        with_demo = collect(db, include_demo=True)
    assert report.users == 3 and with_demo.users == 4
    text = render(report)
    assert "| все | 6 | 1 250 ₽ | 6 250 ₽ |" in text
    assert all(user_id not in text for user_id in three)


def test_small_pilot_hides_details(db_session_factory: sessionmaker[Session]) -> None:
    with db_session_factory() as db:
        _participant(db)
        text = render(collect(db))
    assert "Участников меньше 3" in text
    assert "MAE" not in text and "₽" not in text


def test_cli_writes_report(
    db_session_factory: sessionmaker[Session],
    three: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    monkeypatch.setattr(cli, "SessionLocal", db_session_factory)
    out = tmp_path / "pilot.md"
    assert cli.main(["pilot-report", "--out", str(out)]) == 0
    assert "Проверка прогноза на данных пилота" in out.read_text(encoding="utf-8")


def test_base_forecast_stores_calendar_reference(
    client: TestClient, db_session_factory: sessionmaker[Session]
) -> None:
    session = client.post("/api/v1/demo/sessions", json={}).json()
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    base = client.post("/api/v1/forecasts", headers=headers, json={}).json()
    event = {"type": "expense", "amount_minor": 1_200_000, "date": "2026-10-20", "label": "x"}
    client.post(
        "/api/v1/scenarios",
        headers=headers,
        json={"base_forecast_id": base["forecast_id"], "events": [event]},
    )
    with db_session_factory() as db:
        runs = {run.scenario is None: run for run in db.scalars(select(ForecastRun))}
    calendar = runs[True].reference["calendar"]  # type: ignore[index]
    assert len(calendar) == 30
    # Календарь без повседневных трат оптимистичнее модели в день минимума.
    assert calendar["2026-10-24"] > base["risk"]["min_balance_minor"]
    assert runs[False].reference is None
