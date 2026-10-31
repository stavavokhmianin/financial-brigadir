"""Парольная аутентификация зарегистрированного пользователя."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_token, new_session_token
from app.db.models import AuditEvent, AuthSession, LiveClock, User
from app.domain.ids import new_id

hasher = PasswordHasher()


class SignInError(Exception):
    """Одинаковая внешняя ошибка для неизвестного email и неверного пароля."""


@dataclass(frozen=True)
class SignedIn:
    token: str
    expires_at: datetime
    user: User


def password_hash(password: str) -> str:
    return hasher.hash(password)


def sign_in(db: Session, email: str, password: str, ttl_hours: int) -> SignedIn:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.password_hash is None or db.get(LiveClock, user.id) is None:
        # Выравниваем основную стоимость ответа, чтобы не подсказывать существование email.
        hasher.hash(password)
        raise SignInError
    try:
        hasher.verify(user.password_hash, password)
    except (VerifyMismatchError, InvalidHashError) as exc:
        raise SignInError from exc
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(password)

    now = datetime.now(UTC)
    token = new_session_token()
    expires_at = now + timedelta(hours=ttl_hours)
    db.add(
        AuthSession(
            id=new_id("ses"),
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
    )
    db.add(
        AuditEvent(
            user_id=user.id,
            action="user_signed_in",
            object_type="user",
            object_id=user.id,
        )
    )
    db.commit()
    return SignedIn(token=token, expires_at=expires_at, user=user)
