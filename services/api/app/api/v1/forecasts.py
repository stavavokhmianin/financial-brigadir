from typing import Annotated

from fastapi import APIRouter, Header, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses, not_found
from app.db.models import AuditEvent, ForecastRun
from app.modules.forecasting import (
    DEFAULT_RESERVE_MINOR,
    ForecastInputError,
    create_forecast,
    create_scenario,
    load_forecast,
)
from app.modules.plans import ensure_forecast_access, lock_profile
from app.schemas.forecasts import (
    ForecastOut,
    ForecastRequest,
    RiskPreferencesOut,
    RiskPreferencesPatch,
    ScenarioOut,
    ScenarioRequest,
)

router = APIRouter(tags=["forecasts"])

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        max_length=80,
        description="Повтор запроса с тем же ключом вернёт тот же расчёт",
    ),
]


@router.get(
    "/risk-preferences",
    operation_id="getRiskPreferences",
    summary="Неснижаемый остаток пользователя для прогнозов",
    responses=error_responses(401),
)
def get_risk_preferences(user: CurrentUser) -> RiskPreferencesOut:
    return RiskPreferencesOut(
        reserve_minor=int(user.risk_preferences.get("reserve_minor", DEFAULT_RESERVE_MINOR))
    )


@router.patch(
    "/risk-preferences",
    operation_id="updateRiskPreferences",
    summary="Изменить неснижаемый остаток и применять его к новым прогнозам",
    responses=error_responses(401),
)
def update_risk_preferences(
    body: RiskPreferencesPatch, user: CurrentUser, db: DbSession
) -> RiskPreferencesOut:
    user.risk_preferences = {
        **(user.risk_preferences or {}),
        "reserve_minor": body.reserve_minor,
    }
    db.add(
        AuditEvent(
            user_id=user.id,
            action="risk_preferences_updated",
            object_type="user",
            object_id=user.id,
            meta={"fields": ["reserve_minor"]},
        )
    )
    db.commit()
    return RiskPreferencesOut(reserve_minor=body.reserve_minor)


@router.post(
    "/forecasts",
    operation_id="createForecast",
    summary="Прогноз остатка по дням из зафиксированного снимка (уровни 0–1, раздел 23.1)",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": ForecastOut, "description": "Повтор по Idempotency-Key"},
        **error_responses(400, 401, 403, 404),
    },
)
def post_forecast(
    body: ForecastRequest,
    response: Response,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: IdempotencyKey = None,
) -> ForecastOut:
    user = lock_profile(db, user)
    ensure_forecast_access(user, body.horizon_days, [body.scenario] if body.scenario else [])
    try:
        output, created = create_forecast(db, user, body, idempotency_key)
    except ForecastInputError as exc:
        raise APIError(exc.status_code, exc.code, exc.message) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return output


@router.get(
    "/forecasts/{forecast_id}",
    operation_id="getForecast",
    summary="Сохранённый расчёт: траектория, риск, качество данных, версия модели",
    responses=error_responses(401, 404),
)
def get_forecast(forecast_id: str, user: CurrentUser, db: DbSession) -> ForecastOut:
    output = load_forecast(db, user, forecast_id)
    if output is None:
        raise not_found("Прогноз")
    return output


@router.post(
    "/scenarios",
    operation_id="createScenario",
    summary="What-if: сравнение «до/после» без изменения истории (покупка, сдвиг дохода)",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 403, 404),
)
def post_scenario(body: ScenarioRequest, user: CurrentUser, db: DbSession) -> ScenarioOut:
    user = lock_profile(db, user)
    base = db.scalar(
        select(ForecastRun).where(
            ForecastRun.id == body.base_forecast_id,
            ForecastRun.user_id == user.id,
        )
    )
    if base is None:
        raise not_found("Прогноз")
    ensure_forecast_access(user, base.horizon_days, body.events)
    try:
        return create_scenario(db, user, body)
    except ForecastInputError as exc:
        raise APIError(exc.status_code, exc.code, exc.message) from exc
