"""Server-side feature policy. Billing and real plan activation are outside this MVP."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models import Account, User
from app.domain.enums import Plan
from app.schemas.forecasts import ScenarioEvent


def lock_profile(db: Session, user: User) -> User:
    # Account creation, bank sync and plan changes use the same PostgreSQL lock.
    return db.scalars(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def account_count(db: Session, user: User) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Account)
            .where(
                Account.user_id == user.id,
                Account.archived.is_(False),
            )
        )
        or 0
    )


def _require_plus(user: User, feature: str) -> None:
    if user.plan != Plan.PLUS:
        message = {
            "multiple_accounts": "В Free доступен один счёт. Несколько счетов — в Plus.",
            "extended_horizon": "В Free прогноз до 30 дней. Более длинный горизонт — в Plus.",
            "advanced_scenarios": "В Free проверяется одна покупка. Другие сценарии — в Plus.",
        }[feature]
        raise APIError(
            403,
            "plan_limit",
            message,
            details={"feature": feature, "required_plan": "plus"},
        )


def ensure_account_capacity(db: Session, user: User, adding: int = 1) -> None:
    if adding > 0 and account_count(db, user) + adding > 1:
        _require_plus(user, "multiple_accounts")


def ensure_forecast_access(user: User, horizon_days: int, events: list[ScenarioEvent]) -> None:
    if horizon_days > 30:
        _require_plus(user, "extended_horizon")
    if len(events) > 1 or any(event.type != "expense" for event in events):
        _require_plus(user, "advanced_scenarios")
