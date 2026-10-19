from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.security import hash_token
from app.db.models import AuthSession, User
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False, description="Токен сессии из POST /api/v1/demo/sessions")


def _unauthorized(message: str) -> APIError:
    return APIError(
        status.HTTP_401_UNAUTHORIZED,
        "unauthorized",
        message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """``user_id`` берётся только из токена, клиент его не передаёт (раздел 22.2)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Нужен заголовок Authorization: Bearer <token>")
    session = db.scalars(
        select(AuthSession).where(AuthSession.token_hash == hash_token(credentials.credentials))
    ).one_or_none()
    now = datetime.now(UTC)
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise _unauthorized("Сессия не найдена или истекла")
    user = db.get(User, session.user_id)
    if user is None:
        raise _unauthorized("Сессия не найдена или истекла")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
