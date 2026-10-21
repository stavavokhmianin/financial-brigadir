from fastapi import APIRouter

from app.api.deps import AppSettings
from app.schemas.pilot import MetaOut

router = APIRouter(tags=["health"])


@router.get("/meta", operation_id="getMeta", summary="Режим стенда: демо или пилот")
def meta(settings: AppSettings) -> MetaOut:
    pilot = settings.app_mode == "pilot"
    return MetaOut(
        mode=settings.app_mode,
        pilot_terms_version=settings.pilot_terms_version if pilot else None,
        demo_available=not pilot,
        bank_mock_available=not pilot,
    )
