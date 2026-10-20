"""Сборка ForecastInputSnapshot из реестра и сохранение расчёта (разделы 7.5, 13.3, 22.1).

Ядру передаётся нормализованный снимок: оно не знает, пришли данные из CSV,
демо или API. Снимок и результат сохраняются в ``forecast_runs`` вместе с
версией модели и отпечатком входа — расчёт воспроизводим.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    ForecastPoint,
    ForecastRun,
    IncomeEvent,
    Obligation,
    Transaction,
    User,
)
from app.domain.enums import ObligationStatus
from app.domain.ids import new_id
from app.modules.explain import explain, notes
from app.modules.quality import data_quality
from app.schemas.forecasts import (
    ForecastOut,
    ForecastPointOut,
    ForecastQuality,
    ForecastRequest,
    RiskDriverOut,
    RiskOut,
    ScenarioEvent,
    SpendingModelOut,
)
from forecast_core import (
    AccountSnapshot,
    ForecastInputSnapshot,
    HistoricalTransaction,
    IncomeExpectation,
    ObligationEvent,
    snapshot_fingerprint,
)
from forecast_core.baseline import HISTORY_WINDOW_DAYS, ForecastResult, run_baseline
from forecast_core.types import IncomeShift, ScenarioExpense

DEFAULT_RESERVE_MINOR = 500_000


class ForecastInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PreparedSnapshot:
    snapshot: ForecastInputSnapshot
    data_as_of: datetime
    stale: bool


def _as_of(db: Session, user: User) -> tuple[datetime, datetime, bool]:
    quality = data_quality(db, user)
    data_as_of = quality.data_as_of or datetime.now(UTC)
    # Демо-профиль заморожен на дате выгрузки, реальный пользователь считает «от сейчас».
    as_of = data_as_of if user.is_demo else datetime.now(UTC)
    return as_of, data_as_of, quality.stale


def prepare_snapshot(db: Session, user: User, request: ForecastRequest) -> PreparedSnapshot:
    as_of, data_as_of, stale = _as_of(db, user)
    query = select(Account).where(Account.user_id == user.id, Account.archived.is_(False))
    accounts = list(db.scalars(query))
    if request.account_ids is not None:
        wanted = set(request.account_ids)
        accounts = [a for a in accounts if a.id in wanted]
        if len(accounts) != len(wanted):
            raise ForecastInputError("account_not_found", "Счёт не найден")
    account_ids = {a.id for a in accounts}

    obligations = [
        o
        for o in db.scalars(
            select(Obligation).where(
                Obligation.user_id == user.id, Obligation.status != ObligationStatus.CANCELED
            )
        )
        if o.account_id is None or o.account_id in account_ids
    ]
    incomes = [
        i
        for i in db.scalars(
            select(IncomeEvent).where(
                IncomeEvent.user_id == user.id, IncomeEvent.canceled.is_(False)
            )
        )
        if i.account_id is None or i.account_id in account_ids
    ]
    since = as_of - timedelta(days=HISTORY_WINDOW_DAYS + 2)
    history = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.account_id.in_(account_ids),
            Transaction.occurred_at >= since,
            Transaction.occurred_at <= as_of,
        )
    ).all()

    reserve = request.reserve_minor
    if reserve is None:
        reserve = int(user.risk_preferences.get("reserve_minor", DEFAULT_RESERVE_MINOR))

    extra: tuple[ScenarioExpense, ...] = ()
    shifts: tuple[IncomeShift, ...] = ()
    scenario = request.scenario
    if scenario is not None and scenario.type == "expense" and scenario.amount_minor:
        today = as_of.astimezone(ZoneInfo(user.timezone)).date()
        extra = (
            ScenarioExpense(
                scenario.date or today, scenario.amount_minor, scenario.label or "Покупка"
            ),
        )
    elif scenario is not None and scenario.type == "income_shift":
        if scenario.target_id not in {i.id for i in incomes}:
            raise ForecastInputError("income_not_found", "Доход для сдвига не найден")
        shifts = (IncomeShift(scenario.target_id or "", scenario.shift_days or 0),)

    snapshot = ForecastInputSnapshot(
        as_of=as_of,
        timezone=user.timezone,
        horizon_days=request.horizon_days,
        reserve_minor=reserve,
        accounts=tuple(
            AccountSnapshot(
                id=a.id,
                type=a.type,
                currency=a.currency,
                balance_minor=a.available_balance_minor,
                data_as_of=a.updated_at,
                is_liquid=a.is_liquid,
                credit_limit_minor=a.credit_limit_minor,
                blocked_minor=a.blocked_minor,
            )
            for a in accounts
        ),
        obligations=tuple(
            ObligationEvent(
                id=o.id,
                account_id=o.account_id,
                due_date=o.due_date,
                amount_minor=o.amount_minor,
                status=o.status,
                kind=o.kind.value,
                critical=o.priority.value == "critical",
                movable=o.movable,
                amount_min_minor=o.amount_min_minor,
                amount_max_minor=o.amount_max_minor,
                recurrence=o.recurrence.value,
                recurrence_day=o.recurrence_day,
                title=o.title,
            )
            for o in obligations
        ),
        incomes=tuple(
            IncomeExpectation(
                id=i.id,
                account_id=i.account_id,
                date_from=i.date_from,
                date_to=i.date_to,
                amount_min_minor=i.amount_min_minor,
                amount_max_minor=i.amount_max_minor,
                probability=i.probability,
                confirmed=i.confirmed,
                recurrence=i.recurrence.value,
                title=i.title,
                kind=i.kind.value,
            )
            for i in incomes
        ),
        history=tuple(
            HistoricalTransaction(
                id=t.id,
                account_id=t.account_id,
                occurred_at=t.occurred_at,
                amount_minor=t.amount_minor,
                type=t.type,
                status=t.status,
                category=t.category,
            )
            for t in history
        ),
        coverage=data_quality(db, user).coverage,
        extra_expenses=extra,
        income_shifts=shifts,
    )
    return PreparedSnapshot(snapshot, data_as_of, stale)


def _compact_input(snapshot: ForecastInputSnapshot) -> dict[str, Any]:
    """Снимок входа без полной выписки (логи и хранилище — без истории операций, раздел 7.9)."""
    return {
        "as_of": snapshot.as_of.isoformat(),
        "timezone": snapshot.timezone,
        "horizon_days": snapshot.horizon_days,
        "reserve_minor": snapshot.reserve_minor,
        "accounts": [
            {"id": a.id, "type": a.type.value, "balance_minor": a.balance_minor,
             "is_liquid": a.is_liquid, "blocked_minor": a.blocked_minor}
            for a in snapshot.accounts
        ],
        "obligations": [
            {"id": o.id, "due_date": o.due_date.isoformat(), "amount_minor": o.amount_minor,
             "status": o.status.value, "recurrence": o.recurrence}
            for o in snapshot.obligations
        ],
        "incomes": [
            {"id": i.id, "date_from": i.date_from.isoformat(), "date_to": i.date_to.isoformat(),
             "amount_min_minor": i.amount_min_minor, "amount_max_minor": i.amount_max_minor,
             "probability": i.probability}
            for i in snapshot.incomes
        ],
        "history": {"transactions": len(snapshot.history)},
    }  # fmt: skip


def build_output(
    run_id: str,
    created_at: datetime,
    prepared: PreparedSnapshot,
    result: ForecastResult,
    scenario: ScenarioEvent | None,
) -> ForecastOut:
    snapshot = prepared.snapshot
    flags = list(result.flags)
    if prepared.stale:
        flags.append("stale_data")
    confidence = "insufficient" if prepared.stale else result.confidence
    risk_codes = [d.code for d in result.drivers if d.kind != "income_after_risk"]
    delayable = any(i.date_to > i.date_from for i in snapshot.incomes)
    if result.risk_level != "low" and result.next_income_day and delayable:
        risk_codes.append("salary_delay")
    return ForecastOut(
        forecast_id=run_id,
        created_at=created_at,
        data_as_of=prepared.data_as_of,
        today=result.today,
        horizon_days=snapshot.horizon_days,
        reserve_minor=result.reserve_minor,
        model_version=result.model_version,
        start_balance_minor=result.start_balance_minor,
        quality=ForecastQuality(
            coverage=snapshot.coverage,
            confidence=confidence,
            history_days=result.spending.history_days,
            flags=flags,
            notes=notes(flags),
        ),
        baseline_risk=None,
        scenario_risk=None,
        risk_level=result.risk_level,
        risk_date=result.risk_date,
        risk_drivers=risk_codes,
        risk=RiskOut(
            level=result.risk_level,
            date=result.risk_date,
            shortfall_minor=result.shortfall_minor,
            min_balance_minor=result.min_p50_minor,
            min_balance_date=result.min_p50_day,
            pessimistic_min_minor=result.min_p10_minor,
            pessimistic_min_date=result.min_p10_day,
            next_income_date=result.next_income_day,
            explanation=explain(result, prepared.data_as_of),
            drivers=[
                RiskDriverOut(
                    kind=d.kind,
                    code=d.code,
                    label=d.label,
                    amount_minor=d.amount_minor,
                    date=d.day,
                )
                for d in result.drivers
            ],
        ),
        spending=SpendingModelOut(
            estimator=result.spending.estimator,
            daily_by_weekday_minor=list(result.spending.weekday_daily_minor),
            history_days=result.spending.history_days,
            excluded_large=result.spending.excluded_large,
        ),
        scenario=scenario,
        points=[
            ForecastPointOut(
                day=p.day,
                p10_minor=p.p10_minor,
                p50_minor=p.p50_minor,
                p90_minor=p.p90_minor,
                risk_probability=None,
                below_reserve=p.p50_minor < result.reserve_minor,
                inflow_minor=p.inflow_minor,
                outflow_minor=p.outflow_minor,
                spending_minor=p.spending_minor,
            )
            for p in result.points
        ],
    )


def create_forecast(
    db: Session, user: User, request: ForecastRequest, idempotency_key: str | None
) -> tuple[ForecastOut, bool]:
    """Возвращает ``(прогноз, создан_ли_новый)``. Повтор ключа отдаёт сохранённый расчёт."""
    if idempotency_key:
        existing = db.scalar(
            select(ForecastRun).where(
                ForecastRun.user_id == user.id, ForecastRun.idempotency_key == idempotency_key
            )
        )
        if existing is not None and existing.result is not None:
            return ForecastOut.model_validate(existing.result), False
    prepared = prepare_snapshot(db, user, request)
    result = run_baseline(prepared.snapshot)
    run_id = new_id("fc")
    created_at = datetime.now(UTC)
    output = build_output(run_id, created_at, prepared, result, request.scenario)
    run = ForecastRun(
        id=run_id,
        user_id=user.id,
        as_of=prepared.snapshot.as_of,
        horizon_days=prepared.snapshot.horizon_days,
        reserve_minor=prepared.snapshot.reserve_minor,
        model_version=result.model_version,
        seed=None,
        input_snapshot=_compact_input(prepared.snapshot),
        input_fingerprint=snapshot_fingerprint(prepared.snapshot),
        quality_flags={"flags": output.quality.flags, "confidence": output.quality.confidence},
        scenario=request.scenario.model_dump(mode="json") if request.scenario else None,
        result=output.model_dump(mode="json"),
        idempotency_key=idempotency_key,
        created_at=created_at,
    )
    db.add(run)
    db.flush()
    db.add_all(
        ForecastPoint(
            run_id=run.id,
            day=p.day,
            p10_minor=p.p10_minor,
            p50_minor=p.p50_minor,
            p90_minor=p.p90_minor,
            risk_probability=None,
        )
        for p in result.points
    )
    db.commit()
    return output, True


def load_forecast(db: Session, user: User, forecast_id: str) -> ForecastOut | None:
    run = db.scalar(
        select(ForecastRun).where(ForecastRun.id == forecast_id, ForecastRun.user_id == user.id)
    )
    if run is None or run.result is None:
        return None
    return ForecastOut.model_validate(run.result)
