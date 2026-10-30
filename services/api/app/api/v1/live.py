"""Живой учебный аккаунт (ADR-0007): вход без выбора персонажа и виртуальное время."""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status

from app.adapters.synthetic import SyntheticDataAdapter
from app.api.deps import AppSettings, CurrentUser, DbSession, demo_only
from app.core.errors import APIError, error_responses
from app.db.models import LiveClock, User
from app.modules import live
from app.modules.demo import create_demo_session
from app.modules.quality import data_quality
from app.schemas.demo import (
    DemoProfileOut,
    DemoSessionOut,
    DemoSummary,
    LiveSessionCreate,
    LiveStateOut,
    UserOut,
)

router = APIRouter(tags=["live"], dependencies=[Depends(demo_only)])
adapter = SyntheticDataAdapter()


def _state(db: DbSession, clock: LiveClock) -> LiveStateOut:
    return LiveStateOut.model_validate(live.state(db, clock, datetime.now(UTC)))


def _clock(db: DbSession, user: User) -> LiveClock:
    clock = db.get(LiveClock, user.id)
    if clock is None:
        raise APIError(status.HTTP_404_NOT_FOUND, "not_live", "Это не учебный аккаунт")
    return clock


@router.post(
    "/demo/live-sessions",
    operation_id="createLiveSession",
    summary="Начать без регистрации: живой учебный аккаунт со своей синтетикой",
    status_code=status.HTTP_201_CREATED,
)
def create_live_session(
    body: LiveSessionCreate, db: DbSession, settings: AppSettings
) -> DemoSessionOut:
    seed = body.seed if body.seed is not None else secrets.randbelow(2**31)
    available = [p["id"] for p in adapter.profiles() if adapter.is_available(p["id"])]
    profile_id = live.pick_profile(available, seed)
    result = create_demo_session(
        db,
        adapter,
        profile_id,
        seed,
        settings.demo_session_ttl_hours,
        live=live.LiveOptions(
            seconds_per_day=settings.live_seconds_per_day,
            horizon_days=settings.live_horizon_days,
        ),
    )
    profile = next(p for p in adapter.profiles() if p["id"] == profile_id)
    return DemoSessionOut(
        access_token=result.token,
        expires_at=result.expires_at,
        user=UserOut.model_validate(result.user),
        profile=DemoProfileOut.model_validate(profile),
        summary=DemoSummary(
            accounts=result.accounts,
            transactions=result.transactions,
            obligations=result.obligations,
            incomes=result.incomes,
            duplicates_skipped=result.duplicates_skipped,
        ),
        data_quality=data_quality(db, result.user),
        live=_state(db, _clock(db, result.user)),
    )


@router.get(
    "/live",
    operation_id="getLiveState",
    summary="Виртуальное время учебного аккаунта",
    responses=error_responses(401, 404),
)
def get_state(user: CurrentUser, db: DbSession) -> LiveStateOut:
    return _state(db, _clock(db, user))


@router.post(
    "/live/next-day",
    operation_id="liveNextDay",
    summary="Перемотать на виртуальные сутки вперёд",
    responses=error_responses(401, 404),
)
def next_day(user: CurrentUser, db: DbSession) -> LiveStateOut:
    clock = _clock(db, user)
    live.next_day(db, user, clock, datetime.now(UTC))
    return _state(db, clock)


@router.post(
    "/live/pause",
    operation_id="livePause",
    summary="Остановить виртуальное время",
    responses=error_responses(401, 404),
)
def pause(user: CurrentUser, db: DbSession) -> LiveStateOut:
    clock = _clock(db, user)
    live.pause(db, clock, datetime.now(UTC))
    return _state(db, clock)


@router.post(
    "/live/resume",
    operation_id="liveResume",
    summary="Продолжить виртуальное время",
    responses=error_responses(401, 404),
)
def resume(user: CurrentUser, db: DbSession) -> LiveStateOut:
    clock = _clock(db, user)
    live.resume(db, clock, datetime.now(UTC))
    return _state(db, clock)
