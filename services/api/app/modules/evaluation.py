"""Проверка прогноза на реальных данных пилота (16.2 «после финала», 15.2, roadmap.md).

На синтетике будущее известно генератору. У участника пилота его узнаём позже:
каждый новый расчёт сохраняет остатки на момент расчёта (``input_snapshot``),
и это наблюдение факта для прежних прогнозов.

Правила сопоставления:
- наблюдение — самый ранний расчёт дня X на актуальных данных (без ``stale_data``);
  его ликвидный остаток считается фактом на конец дня X−1;
- прогноз — базовый (не сценарный) расчёт, сделанный до дня X−1, с точкой на этот день;
- рядом считается календарная модель A на том же входе (``reference.calendar``).

Отчёт только агрегированный: без идентификаторов, сумм отдельных людей и операций.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ForecastPoint, ForecastRun, User

LIQUID_TYPES = {"debit", "cash", "savings"}
BUCKETS = ((1, 7), (8, 14), (15, 30), (31, 90))
# Меньше участников — отчёт не детализируется, чтобы не раскрывать отдельного человека.
MIN_USERS = 3


@dataclass(frozen=True)
class Pair:
    user_id: str
    lead_days: int
    p10: int
    p50: int
    p90: int
    calendar: int | None
    actual: int
    reserve: int


@dataclass
class Report:
    users: int = 0
    runs: int = 0
    pairs: list[Pair] = field(default_factory=list)


def _local_day(moment: datetime, timezone: str) -> date:
    return moment.astimezone(ZoneInfo(timezone)).date()


def _liquid_balance(snapshot: dict[str, Any]) -> int:
    return sum(
        int(a["balance_minor"]) - int(a.get("blocked_minor") or 0)
        for a in snapshot.get("accounts", [])
        if a["type"] in LIQUID_TYPES and a.get("is_liquid", True)
    )


def _observations(runs: list[ForecastRun]) -> dict[date, int]:
    """Факт на конец дня: остаток из самого раннего свежего расчёта следующего дня."""
    earliest: dict[date, ForecastRun] = {}
    for run in runs:
        if "stale_data" in (run.quality_flags or {}).get("flags", []):
            continue
        day = _local_day(run.as_of, run.input_snapshot.get("timezone", "Europe/Moscow"))
        if day not in earliest or run.as_of < earliest[day].as_of:
            earliest[day] = run
    return {
        day - timedelta(days=1): _liquid_balance(run.input_snapshot)
        for day, run in earliest.items()
    }


def collect(db: Session, include_demo: bool = False) -> Report:
    report = Report()
    users = select(User.id) if include_demo else select(User.id).where(User.is_demo.is_(False))
    runs_by_user: dict[str, list[ForecastRun]] = defaultdict(list)
    for run in db.scalars(select(ForecastRun).where(ForecastRun.user_id.in_(users))):
        runs_by_user[run.user_id].append(run)

    for user_id, runs in runs_by_user.items():
        actual = _observations(runs)
        user_pairs = 0
        for run in runs:
            if run.scenario:
                continue
            made = _local_day(run.as_of, run.input_snapshot.get("timezone", "Europe/Moscow"))
            calendar = (run.reference or {}).get("calendar", {})
            points = db.scalars(select(ForecastPoint).where(ForecastPoint.run_id == run.id))
            run_pairs = 0
            for point in points:
                if point.day not in actual or point.day <= made:
                    continue
                reference = calendar.get(point.day.isoformat())
                report.pairs.append(
                    Pair(
                        user_id=user_id,
                        lead_days=(point.day - made).days,
                        p10=point.p10_minor,
                        p50=point.p50_minor,
                        p90=point.p90_minor,
                        calendar=int(reference) if reference is not None else None,
                        actual=actual[point.day],
                        reserve=run.reserve_minor,
                    )
                )
                run_pairs += 1
            report.runs += run_pairs > 0
            user_pairs += run_pairs
        report.users += user_pairs > 0
    return report


@dataclass(frozen=True)
class Summary:
    pairs: int
    mae: float
    mae_calendar: float | None
    bias: float
    coverage: float
    gaps_observed: int
    gaps_seen_in_range: int
    gaps_seen_by_median: int
    false_alarm_days: int


def summarize(pairs: list[Pair]) -> Summary | None:
    if not pairs:
        return None
    with_calendar = [p for p in pairs if p.calendar is not None]
    gaps = [p for p in pairs if p.actual < p.reserve]
    return Summary(
        pairs=len(pairs),
        mae=mean(abs(p.p50 - p.actual) for p in pairs),
        mae_calendar=(
            mean(abs(p.calendar - p.actual) for p in with_calendar if p.calendar is not None)
            if with_calendar
            else None
        ),
        bias=mean(p.p50 - p.actual for p in pairs),
        coverage=mean(p.p10 <= p.actual <= p.p90 for p in pairs),
        gaps_observed=len(gaps),
        gaps_seen_in_range=sum(p.p10 < p.reserve for p in gaps),
        gaps_seen_by_median=sum(p.p50 < p.reserve for p in gaps),
        false_alarm_days=sum(p.p50 < p.reserve <= p.actual for p in pairs),
    )


def _rub(minor: float | None) -> str:
    return "—" if minor is None else f"{minor / 100:,.0f} ₽".replace(",", " ")


def render(report: Report) -> str:
    lines = [
        "# Проверка прогноза на данных пилота",
        "",
        "Сгенерировано `python -m app.cli pilot-report`. Факт — остаток, который участник",
        "увидел при следующем заходе; прогноз — расчёт, показанный ему раньше.",
        "Модель A — календарь подтверждённых платежей и доходов на том же входе.",
        "",
        f"Участников с проверяемыми прогнозами: **{report.users}**, расчётов: {report.runs}, "
        f"пар «прогноз — факт»: {len(report.pairs)}.",
        "",
    ]
    if report.users < MIN_USERS:
        lines.append(
            f"Участников меньше {MIN_USERS}: детализация не выводится, чтобы не раскрывать "
            "данные отдельного человека."
        )
        return "\n".join(lines) + "\n"

    lines += [
        "| Горизонт, дней | Пар | MAE модели | MAE календаря (A) | Смещение | Факт в p10–p90 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    rows = [("все", report.pairs)] + [
        (f"{low}–{high}", [p for p in report.pairs if low <= p.lead_days <= high])
        for low, high in BUCKETS
    ]
    for label, pairs in rows:
        summary = summarize(pairs)
        if summary is None or len({p.user_id for p in pairs}) < MIN_USERS:
            continue
        lines.append(
            f"| {label} | {summary.pairs} | {_rub(summary.mae)} | {_rub(summary.mae_calendar)} "
            f"| {_rub(summary.bias)} | {summary.coverage:.0%} |"
        )
    total = summarize(report.pairs)
    if total is None:  # недостижимо: участники с парами есть
        return "\n".join(lines) + "\n"
    lines += [
        "",
        "Смещение > 0 — прогноз выше факта (модель оптимистична).",
        "",
        "## Дни ниже резерва",
        "",
        f"- наблюдено дней ниже резерва: {total.gaps_observed}",
        f"- из них риск был виден в коридоре (p10 ниже резерва): {total.gaps_seen_in_range}",
        f"- из них ниже резерва был и базовый прогноз (p50): {total.gaps_seen_by_median}",
        f"- дней, когда базовый прогноз был ниже резерва, а факт — нет: {total.false_alarm_days}",
        "",
        "Наблюдения редкие (только дни заходов в приложение), поэтому это нижняя граница",
        "качества обнаружения, а не полная оценка. Критерий перехода — `docs/roadmap.md`.",
    ]
    return "\n".join(lines) + "\n"
