"""Эндпоинты, чей контракт зафиксирован на этапе 1, а реализация — позже (раздел 16.2).

Каждый обработчик проверяет авторизацию и отвечает ``501 not_implemented``
с указанием этапа, чтобы клиент мог показать честное состояние.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.core.errors import error_responses, not_implemented
from app.schemas.planned import (
    AlertsOut,
    BankMockSyncOut,
    BankMockSyncRequest,
    ScenarioOut,
    ScenarioRequest,
)

router = APIRouter()

STAGE_3 = "этап 3 (27 октября – 1 ноября)"
STAGE_4 = "этап 4 (2–15 ноября)"
STAGE_5 = "этап 5 (16–29 ноября)"


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
