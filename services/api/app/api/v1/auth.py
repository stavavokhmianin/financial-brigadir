"""Обычная регистрация: один человек — один изолированный профиль."""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError

from app.adapters.synthetic import SyntheticDataAdapter
from app.api.deps import AppSettings, DbSession, demo_only
from app.core.errors import APIError, error_responses
from app.db.models import LiveClock, User
from app.modules import live
from app.modules.demo import create_demo_session
from app.modules.quality import data_quality
from app.modules.user_auth import SignInError, password_hash, sign_in
from app.schemas.auth import RegisterIn, SignInIn, UserSessionOut
from app.schemas.demo import LiveStateOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(demo_only)])
adapter = SyntheticDataAdapter()


def _out(db: DbSession, user: User, token: str, expires_at: datetime) -> UserSessionOut:
    clock = db.get(LiveClock, user.id)
    if clock is None:
        raise APIError(status.HTTP_409_CONFLICT, "profile_incomplete", "Профиль не готов")
    return UserSessionOut(
        access_token=token,
        expires_at=expires_at,
        user=UserOut.model_validate(user),
        data_quality=data_quality(db, user),
        live=LiveStateOut.model_validate(live.state(db, clock, datetime.now(UTC))),
    )


@router.post(
    "/register",
    operation_id="registerUser",
    summary="Создать личный профиль с отдельной историей и моделью",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409, 422),
)
def register(body: RegisterIn, db: DbSession, settings: AppSettings) -> UserSessionOut:
    # Argon2 и выбор синтетической основы не должны удерживать read-транзакцию SQLite:
    # две одновременные регистрации иначе обе читают, а затем одна не может стать писателем.
    hashed_password = password_hash(body.password)
    seed = secrets.randbelow(2**31)
    available = [item["id"] for item in adapter.profiles() if adapter.is_available(item["id"])]
    profile_id = live.pick_profile(available, seed)
    try:
        result = create_demo_session(
            db,
            adapter,
            profile_id,
            seed,
            settings.user_session_ttl_hours,
            live=live.LiveOptions(
                seconds_per_day=settings.live_seconds_per_day,
                horizon_days=settings.live_horizon_days,
            ),
            display_name=body.display_name,
            email=body.email,
            password_hash=hashed_password,
        )
    except IntegrityError as exc:
        db.rollback()
        raise APIError(
            status.HTTP_409_CONFLICT, "email_exists", "Этот email уже зарегистрирован"
        ) from exc
    return _out(db, result.user, result.token, result.expires_at)


@router.post(
    "/sessions",
    operation_id="createUserSession",
    summary="Войти в существующий личный профиль",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 422),
)
def create_session(body: SignInIn, db: DbSession, settings: AppSettings) -> UserSessionOut:
    try:
        result = sign_in(db, body.email, body.password, settings.user_session_ttl_hours)
    except SignInError as exc:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_credentials",
            "Неверный email или пароль",
        ) from exc
    return _out(db, result.user, result.token, result.expires_at)
