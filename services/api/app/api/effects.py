"""«Было / стало» прогноза для действий пользователя: метка траты, новое обязательство."""

from app.schemas.transactions import ForecastEffectOut, ForecastGlance
from forecast_core.baseline import ForecastResult


def glance(result: ForecastResult) -> ForecastGlance:
    return ForecastGlance(
        risk_level=result.risk_level,
        min_balance_minor=result.min_p50_minor,
        min_balance_date=result.min_p50_day,
        pessimistic_min_minor=result.min_p10_minor,
        excluded_one_off=result.spending.excluded_one_off,
    )


def forecast_effect(before: ForecastResult, after: ForecastResult) -> ForecastEffectOut:
    old, new = glance(before), glance(after)
    return ForecastEffectOut(
        before=old,
        after=new,
        changed=(old.risk_level, old.min_balance_minor, old.pessimistic_min_minor)
        != (new.risk_level, new.min_balance_minor, new.pessimistic_min_minor),
    )
