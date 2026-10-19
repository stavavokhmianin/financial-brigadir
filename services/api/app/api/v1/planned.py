"""Эндпоинты, чей контракт зафиксирован на этапе 1, а реализация — позже (раздел 16.2).

Каждый обработчик проверяет авторизацию и отвечает ``501 not_implemented``
с указанием этапа, чтобы клиент мог показать честное состояние.
"""

from typing import Annotated

from fastapi import APIRouter, File, Form, Header, UploadFile

from app.api.deps import CurrentUser
from app.core.errors import error_responses, not_implemented
from app.schemas.planned import (
    AlertsOut,
    BankMockSyncOut,
    BankMockSyncRequest,
    ForecastOut,
    ForecastRequest,
    ImportResultOut,
    ScenarioOut,
    ScenarioRequest,
)

router = APIRouter()

STAGE_2 = "этап 2 (23–26 октября)"
STAGE_3 = "этап 3 (27 октября – 1 ноября)"
STAGE_4 = "этап 4 (2–15 ноября)"
STAGE_5 = "этап 5 (16–29 ноября)"

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        max_length=80,
        description="Повтор запроса с тем же ключом вернёт тот же результат",
    ),
]


@router.post(
    "/imports/csv",
    tags=["imports"],
    operation_id="importCsv",
    summary="Валидация, предпросмотр и импорт CSV; идемпотентно по fingerprint",
    status_code=201,
    responses=error_responses(400, 401, 413, 501),
)
def import_csv(
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="CSV по поддерживаемому шаблону")],
    account_id: Annotated[str, Form()],
    mode: Annotated[str, Form(pattern="^(preview|import)$")] = "preview",
    idempotency_key: IdempotencyKey = None,
) -> ImportResultOut:
    raise not_implemented(STAGE_2)


@router.post(
    "/forecasts",
    tags=["forecasts"],
    operation_id="createForecast",
    summary="Расчёт прогноза из зафиксированного снимка",
    status_code=201,
    responses=error_responses(400, 401, 501),
)
def create_forecast(
    body: ForecastRequest, user: CurrentUser, idempotency_key: IdempotencyKey = None
) -> ForecastOut:
    raise not_implemented(STAGE_2)


@router.get(
    "/forecasts/{forecast_id}",
    tags=["forecasts"],
    operation_id="getForecast",
    summary="Траектория прогноза и метаданные",
    responses=error_responses(401, 404, 501),
)
def get_forecast(forecast_id: str, user: CurrentUser) -> ForecastOut:
    raise not_implemented(STAGE_2)


@router.post(
    "/scenarios",
    tags=["forecasts"],
    operation_id="createScenario",
    summary="What-if без изменения истории",
    status_code=201,
    responses=error_responses(400, 401, 404, 501),
)
def create_scenario(body: ScenarioRequest, user: CurrentUser) -> ScenarioOut:
    raise not_implemented(STAGE_3)


@router.get(
    "/alerts",
    tags=["alerts"],
    operation_id="listAlerts",
    summary="Предупреждения и причины подавления",
    responses=error_responses(401, 501),
)
def list_alerts(user: CurrentUser) -> AlertsOut:
    raise not_implemented(STAGE_4)


@router.post(
    "/connectors/bank-mock/sync",
    tags=["connectors"],
    operation_id="syncBankMock",
    summary="Мок банковского подключения (без реальных банковских данных)",
    responses=error_responses(401, 501),
)
def sync_bank_mock(body: BankMockSyncRequest, user: CurrentUser) -> BankMockSyncOut:
    raise not_implemented(STAGE_5)
