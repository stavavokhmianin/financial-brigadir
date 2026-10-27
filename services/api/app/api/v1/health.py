from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.db.session import get_db

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok", "unavailable"]
    version: str


@router.get("/health", operation_id="getHealth", summary="Liveness: процесс API отвечает")
def health() -> HealthOut:
    return HealthOut(status="ok", version=__version__)


@router.get(
    "/health/ready",
    operation_id="getReadiness",
    summary="Readiness: API готово обслуживать запросы (доступна БД)",
    responses={503: {"model": HealthOut}},
)
def readiness(response: Response, db: Annotated[Session, Depends(get_db)]) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(status="unavailable", version=__version__)
    return HealthOut(status="ok", version=__version__)
