from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel, DataQuality
from app.schemas.demo import UserOut


class MetaOut(APIModel):
    mode: Literal["demo", "pilot"]
    pilot_terms_version: str | None = Field(
        description="Версия условий пилота, которую клиент показывает и передаёт при входе"
    )
    demo_available: bool
    bank_mock_available: bool


class PilotSignIn(APIModel):
    access_code: str = Field(min_length=16, max_length=40, examples=["ABCD-EFGH-JKMN-PQRS"])
    accepted_terms_version: str = Field(max_length=32)


class PilotSessionOut(APIModel):
    access_token: str = Field(description="Показывается один раз; на сервере хранится только хэш")
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — тип токена, не секрет
    expires_at: datetime
    user: UserOut
    first_sign_in: bool = Field(description="true — профиль только что создан и пуст")
    data_quality: DataQuality
