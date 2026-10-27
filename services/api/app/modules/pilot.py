"""Режим пилота: персональные коды участников вместо демо-профилей.

Код выдаёт оператор стенда (``python -m app.cli invite``). Это секрет уровня токена:
80 бит энтропии, в БД хранится только SHA-256. Первый вход по коду создаёт пустой
профиль и фиксирует принятую версию условий пилота; повторный вход по тому же коду
открывает новую сессию в том же профиле, пока код не истёк и не отозван.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_token, new_session_token
from app.db.models import AuditEvent, AuthSession, PilotAccessCode, User
from app.domain.enums import Plan
from app.domain.ids import new_id

# Без 0/O, 1/I/L: код диктуют и вводят вручную.
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
GROUPS, GROUP_SIZE = 4, 4


class PilotAccessError(Exception):
    """Код неверный, истёк или отозван — причина наружу не раскрывается."""


@dataclass(frozen=True)
class IssuedCode:
    id: str
    code: str
    expires_at: datetime


@dataclass(frozen=True)
class PilotSession:
    token: str
    expires_at: datetime
    user: User
    created: bool


def normalize(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def issue_codes(db: Session, count: int, valid_days: int) -> list[IssuedCode]:
    if not 1 <= count <= 500 or not 1 <= valid_days <= 365:
        raise ValueError("count 1..500, valid_days 1..365")
    expires_at = datetime.now(UTC) + timedelta(days=valid_days)
    issued = []
    for _ in range(count):
        raw = "".join(secrets.choice(ALPHABET) for _ in range(GROUPS * GROUP_SIZE))
        code = "-".join(raw[i : i + GROUP_SIZE] for i in range(0, len(raw), GROUP_SIZE))
        row = PilotAccessCode(id=new_id("pac"), code_hash=hash_token(raw), expires_at=expires_at)
        db.add(row)
        issued.append(IssuedCode(row.id, code, expires_at))
    db.add(AuditEvent(action="pilot_codes_issued", meta={"count": count, "days": valid_days}))
    db.commit()
    return issued


def revoke_code(db: Session, code_id: str) -> bool:
    row = db.get(PilotAccessCode, code_id)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(UTC)
    db.add(AuditEvent(user_id=row.user_id, action="pilot_code_revoked", object_id=row.id))
    db.commit()
    return True


def sign_in(db: Session, code: str, terms_version: str, ttl_hours: int) -> PilotSession:
    now = datetime.now(UTC)
    row = db.scalar(
        select(PilotAccessCode)
        .where(PilotAccessCode.code_hash == hash_token(normalize(code)))
        .with_for_update()
    )
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise PilotAccessError
    created = row.user_id is None
    user = User(id=new_id("usr"), plan=Plan.PLUS) if created else db.get(User, row.user_id)
    if user is None:
        raise PilotAccessError
    if created:
        db.add(user)
        db.flush()
        row.user_id = user.id
    # Версия условий фиксируется при каждом входе: оператор может выпустить новую.
    user.consent_versions = {**(user.consent_versions or {}), "pilot_terms": terms_version}
    row.last_used_at = now
    token = new_session_token()
    # Сессия не переживает код: истёкший код закрывает и доступ.
    expires_at = min(now + timedelta(hours=ttl_hours), row.expires_at)
    db.add(
        AuthSession(
            id=new_id("ses"), user_id=user.id, token_hash=hash_token(token), expires_at=expires_at
        )
    )
    db.add(
        AuditEvent(
            user_id=user.id,
            action="pilot_joined" if created else "pilot_signed_in",
            object_type="user",
            object_id=user.id,
            meta={"terms_version": terms_version},
        )
    )
    db.commit()
    return PilotSession(token, expires_at, user, created)
