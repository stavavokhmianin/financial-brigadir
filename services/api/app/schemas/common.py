from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Coverage

INT64_MAX = 2**63 - 1

# Денежная сумма в копейках (int64). Знак зависит от поля.
Minor = Annotated[int, Field(ge=-INT64_MAX, le=INT64_MAX, examples=[1_200_000])]
PositiveMinor = Annotated[int, Field(gt=0, le=INT64_MAX, examples=[1_200_000])]
NonNegativeMinor = Annotated[int, Field(ge=0, le=INT64_MAX, examples=[500_000])]
Currency = Literal["RUB"]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DataQuality(APIModel):
    """Метка качества данных (разделы 13.2, FR-04): свежесть, охват, длина истории."""

    coverage: Coverage = Field(description="Полнота охвата счетов пользователя")
    data_as_of: datetime | None = Field(description="Самые старые из актуальных данных")
    history_days: int = Field(ge=0, description="Длина доступной истории операций, дней")
    stale: bool = Field(description="Данные устарели: сначала обновить, потом прогнозировать")
    is_demo: bool
    notes: list[str] = Field(description="Ограничения, которые нужно показать пользователю")
