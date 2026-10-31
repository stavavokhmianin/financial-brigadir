from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.enums import Plan
from app.schemas.common import APIModel, DataQuality


class DemoProfileOut(APIModel):
    id: str = Field(examples=["young_specialist"])
    title: str
    description: str
    segment: str
    mvp: bool = Field(description="false — профиль из дорожной карты, демо-сессию не создать")
    anomalies: list[str]


class DemoSessionCreate(APIModel):
    profile_id: str = Field(default="young_specialist", max_length=64)
    seed: int = Field(default=42, ge=0, le=2**31 - 1, description="Для воспроизводимости")


class UserOut(APIModel):
    id: str
    display_name: str | None = None
    email: str | None = None
    locale: str
    timezone: str
    plan: Plan
    is_demo: bool
    demo_profile: str | None


class DemoSummary(APIModel):
    accounts: int
    transactions: int
    obligations: int
    incomes: int
    duplicates_skipped: int = Field(
        description="Сколько операций повторной выгрузки отброшено как уже известные"
    )


class LiveSessionCreate(APIModel):
    seed: int | None = Field(
        default=None,
        ge=0,
        le=2**31 - 1,
        description="По умолчанию случайный: у каждого учебного аккаунта своя синтетика",
    )


class LiveStateOut(APIModel):
    """Виртуальное время учебного аккаунта (ADR-0007)."""

    virtual_now: datetime = Field(description="Текущий момент учебного аккаунта")
    virtual_start: datetime
    ends_at: datetime = Field(description="Дальше синтетического будущего нет")
    seconds_per_day: int = Field(description="Реальных секунд на виртуальный день")
    paused: bool
    finished: bool = Field(description="Учебный период закончился, время стоит")
    revealed_total: int = Field(description="Сколько новых операций уже поступило")
    pending: int = Field(description="Сколько операций ещё впереди")


class DemoSessionOut(APIModel):
    access_token: str = Field(description="Показывается один раз; на сервере хранится только хэш")
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — тип токена, не секрет
    expires_at: datetime
    user: UserOut
    profile: DemoProfileOut
    summary: DemoSummary
    data_quality: DataQuality
    live: LiveStateOut | None = Field(
        default=None, description="Есть только у живого учебного аккаунта"
    )
