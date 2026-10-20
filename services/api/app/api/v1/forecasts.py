from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses, not_found
from app.modules.forecasting import ForecastInputError, create_forecast, load_forecast
from app.schemas.forecasts import ForecastOut, ForecastRequest

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        max_length=80,
        description="Повтор запроса с тем же ключом вернёт тот же расчёт",
    ),
]


@router.post(
    "",
    operation_id="createForecast",
    summary="Прогноз остатка по дням из зафиксированного снимка (уровни 0–1, раздел 23.1)",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": ForecastOut, "description": "Повтор по Idempotency-Key"},
        **error_responses(400, 401, 404),
    },
)
def post_forecast(
    body: ForecastRequest,
    response: Response,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: IdempotencyKey = None,
) -> ForecastOut:
    try:
        output, created = create_forecast(db, user, body, idempotency_key)
    except ForecastInputError as exc:
        raise APIError(status.HTTP_404_NOT_FOUND, exc.code, exc.message) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return output


@router.get(
    "/{forecast_id}",
    operation_id="getForecast",
    summary="Сохранённый расчёт: траектория, риск, качество данных, версия модели",
    responses=error_responses(401, 404),
)
def get_forecast(forecast_id: str, user: CurrentUser, db: DbSession) -> ForecastOut:
    output = load_forecast(db, user, forecast_id)
    if output is None:
        raise not_found("Прогноз")
    return output
