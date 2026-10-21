from fastapi import APIRouter, Depends, status

from app.adapters.synthetic import SyntheticDataAdapter
from app.api.deps import AppSettings, DbSession, demo_only
from app.core.errors import APIError, error_responses
from app.modules.demo import create_demo_session
from app.modules.quality import data_quality
from app.schemas.demo import (
    DemoProfileOut,
    DemoSessionCreate,
    DemoSessionOut,
    DemoSummary,
    UserOut,
)

router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(demo_only)])
adapter = SyntheticDataAdapter()


@router.get(
    "/profiles",
    operation_id="listDemoProfiles",
    summary="Демо-профили для экрана запуска",
)
def list_profiles() -> list[DemoProfileOut]:
    return [DemoProfileOut.model_validate(p) for p in adapter.profiles()]


@router.post(
    "/sessions",
    operation_id="createDemoSession",
    summary="Создать изолированный профиль из seed (FR-01)",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 404),
)
def create_session(body: DemoSessionCreate, db: DbSession, settings: AppSettings) -> DemoSessionOut:
    profiles = {p["id"]: p for p in adapter.profiles()}
    if body.profile_id not in profiles:
        raise APIError(status.HTTP_404_NOT_FOUND, "profile_not_found", "Демо-профиль не найден")
    if not adapter.is_available(body.profile_id):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "profile_not_available",
            "Профиль появится после MVP",
        )
    result = create_demo_session(
        db, adapter, body.profile_id, body.seed, settings.demo_session_ttl_hours
    )
    return DemoSessionOut(
        access_token=result.token,
        expires_at=result.expires_at,
        user=UserOut.model_validate(result.user),
        profile=DemoProfileOut.model_validate(profiles[body.profile_id]),
        summary=DemoSummary(
            accounts=result.accounts,
            transactions=result.transactions,
            obligations=result.obligations,
            incomes=result.incomes,
            duplicates_skipped=result.duplicates_skipped,
        ),
        data_quality=data_quality(db, result.user),
    )
