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


class DemoSessionOut(APIModel):
    access_token: str = Field(description="Показывается один раз; на сервере хранится только хэш")
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — тип токена, не секрет
    expires_at: datetime
    user: UserOut
    profile: DemoProfileOut
    summary: DemoSummary
    data_quality: DataQuality
