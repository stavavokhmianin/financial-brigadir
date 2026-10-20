from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Response
from sqlalchemy import update

from app.api.deps import CurrentUser, DbSession
from app.core.errors import error_responses
from app.db.models import AuditEvent, AuthSession
from app.modules.privacy import erase_profile, export_profile
from app.schemas.common import APIModel

router = APIRouter(prefix="/privacy", tags=["privacy"])


class DeleteProfileRequest(APIModel):
    confirmation: Literal["DELETE"]


@router.get("/export", operation_id="exportProfile", responses=error_responses(401))
def export(user: CurrentUser, db: DbSession, response: Response) -> dict[str, Any]:
    response.headers["Content-Disposition"] = 'attachment; filename="brigadir-profile.json"'
    return export_profile(db, user)


@router.post(
    "/logout", operation_id="logoutProfile", status_code=204, responses=error_responses(401)
)
def logout(user: CurrentUser, db: DbSession) -> Response:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    db.add(AuditEvent(user_id=user.id, action="sessions_revoked"))
    db.commit()
    return Response(status_code=204)


@router.delete(
    "/profile", operation_id="deleteProfile", status_code=204, responses=error_responses(401)
)
def remove(body: DeleteProfileRequest, user: CurrentUser, db: DbSession) -> Response:
    erase_profile(db, user)
    return Response(status_code=204)
