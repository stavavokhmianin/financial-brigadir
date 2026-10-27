from fastapi import APIRouter, Depends, status

from app.api.deps import AppSettings, DbSession, pilot_only
from app.core.errors import APIError, error_responses
from app.modules.pilot import PilotAccessError, sign_in
from app.modules.quality import data_quality
from app.schemas.demo import UserOut
from app.schemas.pilot import PilotSessionOut, PilotSignIn

router = APIRouter(prefix="/pilot", tags=["pilot"], dependencies=[Depends(pilot_only)])


@router.post(
    "/sessions",
    operation_id="createPilotSession",
    summary="Вход участника пилота по персональному коду",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 404),
)
def create_session(body: PilotSignIn, db: DbSession, settings: AppSettings) -> PilotSessionOut:
    if body.accepted_terms_version != settings.pilot_terms_version:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "terms_not_accepted",
            "Примите текущую версию условий пилота.",
            details={"pilot_terms_version": settings.pilot_terms_version},
        )
    try:
        result = sign_in(
            db, body.access_code, settings.pilot_terms_version, settings.pilot_session_ttl_hours
        )
    except PilotAccessError as exc:
        raise APIError(
            status.HTTP_401_UNAUTHORIZED,
            "invalid_access_code",
            "Код не подходит: проверьте его или обратитесь к оператору пилота.",
        ) from exc
    return PilotSessionOut(
        access_token=result.token,
        expires_at=result.expires_at,
        user=UserOut.model_validate(result.user),
        first_sign_in=result.created,
        data_quality=data_quality(db, result.user),
    )
