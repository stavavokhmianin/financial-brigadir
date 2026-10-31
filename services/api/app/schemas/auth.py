"""Публичная регистрация и вход в личный профиль."""

import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import APIModel, DataQuality
from app.schemas.demo import LiveStateOut, UserOut

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(APIModel):
    display_name: str = Field(min_length=1, max_length=40)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Укажите имя")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if not EMAIL.fullmatch(value):
            raise ValueError("Некорректный email")
        return value


class SignInIn(APIModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return value.strip().casefold()


class UserSessionOut(APIModel):
    access_token: str = Field(description="Показывается один раз; хранится только хэш")
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — тип токена, не секрет
    expires_at: datetime
    user: UserOut
    data_quality: DataQuality
    live: LiveStateOut
