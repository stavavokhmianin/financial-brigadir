"""Контракт прогноза (разделы 22.2–22.3).

Поля верхнего уровня ``baseline_risk``, ``scenario_risk``, ``risk_date`` и
``risk_drivers`` совпадают с примером из ТЗ. Вероятности остаются ``null``, пока
модель не откалибрована: показывать псевдопроценты запрещено (раздел 9.3).
"""

import datetime as dt
from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.enums import Coverage
from app.schemas.common import APIModel, Minor, NonNegativeMinor, PositiveMinor

RiskLevel = Literal["low", "medium", "high"]


class ScenarioEvent(APIModel):
    """Гипотетическое событие: не меняет историю операций (раздел 7.6)."""

    type: Literal["expense", "income_shift"]
    amount_minor: PositiveMinor | None = Field(default=None, description="Для expense")
    date: dt.date | None = Field(
        default=None, description="Для expense; по умолчанию — первый день прогноза"
    )
    label: str | None = Field(default=None, max_length=80)
    merchant: str | None = Field(
        default=None, max_length=120, description="Торговая точка или получатель, если известны"
    )
    category: str | None = Field(default=None, max_length=64)
    shift_days: int | None = Field(default=None, ge=-31, le=31, description="Для income_shift")
    target_id: str | None = Field(default=None, description="id дохода для income_shift")

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.type == "expense" and self.amount_minor is None:
            raise ValueError("для expense нужен amount_minor")
        if self.type == "income_shift" and (self.shift_days is None or not self.target_id):
            raise ValueError("для income_shift нужны target_id и shift_days")
        return self


class ForecastRequest(APIModel):
    account_ids: list[str] | None = Field(default=None, description="По умолчанию все счета")
    horizon_days: int = Field(default=30, ge=1, le=90)
    reserve_minor: NonNegativeMinor | None = Field(
        default=None, description="Резерв R; по умолчанию — из настроек пользователя"
    )
    scenario: ScenarioEvent | None = None


class RiskPreferencesOut(APIModel):
    """Личная граница, ниже которой пользователь не хочет опускать остаток."""

    reserve_minor: NonNegativeMinor


class RiskPreferencesPatch(APIModel):
    reserve_minor: NonNegativeMinor


class ForecastPointOut(APIModel):
    day: dt.date
    p10_minor: Minor = Field(description="Пессимистичный сценарий")
    p50_minor: Minor = Field(description="Базовый сценарий")
    p90_minor: Minor = Field(description="Оптимистичный сценарий")
    risk_probability: float | None = Field(
        ge=0,
        le=1,
        description="Доля траекторий симуляции ниже резерва в этот день; null без симуляции",
    )
    below_reserve: bool = Field(description="Базовый сценарий ниже резерва")
    inflow_minor: NonNegativeMinor = Field(description="Ожидаемые поступления дня")
    outflow_minor: NonNegativeMinor = Field(description="Обязательные платежи дня")
    spending_minor: NonNegativeMinor = Field(description="Ожидаемые повседневные траты дня")


class ForecastQuality(APIModel):
    coverage: Coverage
    confidence: Literal["insufficient", "illustrative", "calibrated"] = Field(
        description="Вероятности не считаются реальными, пока модель не откалибрована"
    )
    history_days: int
    flags: list[str]
    notes: list[str] = Field(description="Ограничения расчёта для показа пользователю")


class RiskDriverOut(APIModel):
    kind: Literal["obligation", "daily_spending", "scenario", "income_after_risk"]
    code: str
    label: str
    amount_minor: NonNegativeMinor
    date: dt.date | None


class RiskOut(APIModel):
    level: RiskLevel = Field(
        description="high — резерв нарушен в базовом сценарии; medium — только в пессимистичном"
    )
    date: dt.date | None
    shortfall_minor: NonNegativeMinor = Field(description="Насколько остаток ниже резерва")
    min_balance_minor: Minor
    min_balance_date: dt.date
    pessimistic_min_minor: Minor
    pessimistic_min_date: dt.date
    next_income_date: dt.date | None
    explanation: str = Field(description="Структурированное объяснение по шаблону (раздел 9.6)")
    drivers: list[RiskDriverOut]


class SpendingModelOut(APIModel):
    estimator: str
    daily_by_weekday_minor: list[NonNegativeMinor] = Field(description="Понедельник — первый")
    history_days: int
    excluded_large: int
    recency_half_life_days: int | None = Field(
        default=None,
        description="Период полураспада веса истории; null у сравнительного median baseline",
    )
    income_phase_aware: bool = Field(
        default=False, description="Есть ли достаточно истории доходов для фаз денежного цикла"
    )


class SafeSpendOut(APIModel):
    """Сумма условно безопасной покупки в день ``date`` (раздел 9.4) — диапазон, а не точка."""

    date: dt.date
    base_minor: NonNegativeMinor = Field(description="Не опускает базовый сценарий ниже резерва")
    conservative_minor: NonNegativeMinor = Field(
        description="Не опускает ниже резерва даже пессимистичный сценарий"
    )
    available: bool = Field(description="false — данных недостаточно, сумму не показываем")


class ForecastOut(APIModel):
    forecast_id: str
    created_at: datetime
    data_as_of: datetime
    today: dt.date
    horizon_days: int
    reserve_minor: NonNegativeMinor
    model_version: str
    start_balance_minor: Minor
    quality: ForecastQuality
    baseline_risk: float | None = Field(ge=0, le=1)
    scenario_risk: float | None = Field(ge=0, le=1)
    risk_level: RiskLevel
    risk_date: dt.date | None
    risk_drivers: list[str]
    risk: RiskOut
    spending: SpendingModelOut
    scenario: ScenarioEvent | None
    safe_to_spend: SafeSpendOut
    points: list[ForecastPointOut]


class ScenarioRequest(APIModel):
    base_forecast_id: str
    events: list[ScenarioEvent] = Field(min_length=1, max_length=10)


class PurchaseContextOut(APIModel):
    """Сравнение покупки с личной историей, без оценки решения пользователя."""

    basis: Literal[
        "merchant_income_phase",
        "merchant_weekday",
        "merchant",
        "category_income_phase",
        "category_weekday",
        "category",
        "amount_only",
    ]
    observations: int = Field(ge=0)
    median_minor: NonNegativeMinor | None
    lower_minor: NonNegativeMinor | None
    upper_minor: NonNegativeMinor | None
    amount_position: Literal["below", "typical", "above", "unknown"]


class ScenarioOut(APIModel):
    """Сравнение «до/после» (раздел 11.3): исходные операции не меняются."""

    scenario_id: str
    created_at: datetime
    base: ForecastOut
    result: ForecastOut
    delta_risk: float | None = Field(description="Изменение вероятности нарушения резерва")
    min_balance_delta_minor: Minor
    pessimistic_min_delta_minor: Minor
    risk_level_before: RiskLevel
    risk_level_after: RiskLevel
    risk_date_before: dt.date | None
    risk_date_after: dt.date | None
    days_below_reserve_before: int
    days_below_reserve_after: int
    worsened: bool
    base_recomputed: bool = Field(
        description="Данные изменились после базового расчёта — база пересчитана"
    )
    explanation: str
    purchase_context: PurchaseContextOut | None = None
