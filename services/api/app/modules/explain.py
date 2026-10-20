"""Explain API (раздел 7.8): объяснение риска детерминированными шаблонами, без LLM."""

from datetime import date, datetime

from forecast_core.baseline import ForecastResult, RiskDriver

MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)  # fmt: skip

FLAG_NOTES = {
    "no_history": "Истории операций нет: повседневные траты не учтены, добавьте выписку.",
    "short_history": "История короче 4 недель: коридор прогноза расширен.",
    "large_expenses_excluded": "Крупные разовые покупки не считаются ежедневными тратами.",
    "unconfirmed_events": "Часть платежей и доходов не подтверждена — проверьте календарь.",
    "partial_coverage": "В выписке есть пропуски: часть операций может отсутствовать.",
    "card_spending_accrual": (
        "Платёж по кредитке учитывает ожидаемые траты по карте до даты погашения."
    ),
    "scenario_applied": "Расчёт со сценарием: история операций не изменена.",
    "stale_data": "Данные старше 3 дней: обновите остаток перед решением.",
}


def rub(minor: int) -> str:
    sign = "−" if minor < 0 else ""
    units = abs(minor) // 100
    return f"{sign}{units:,}".replace(",", " ") + " ₽"


def day_text(value: date) -> str:
    return f"{value.day} {MONTHS[value.month - 1]}"


def _driver_text(driver: RiskDriver) -> str:
    if driver.kind == "obligation" and driver.day is not None:
        return f"{driver.label.lower()} {rub(driver.amount_minor)} ({day_text(driver.day)})"
    if driver.kind == "scenario":
        return f"покупка {rub(driver.amount_minor)}"
    if driver.kind == "daily_spending":
        return f"повседневные траты ≈{rub(driver.amount_minor)}"
    return driver.label.lower()


def explain(result: ForecastResult, data_as_of: datetime) -> str:
    """Один тезис, дата, причина, ближайший доход и актуальность данных (11.4)."""
    reserve = rub(result.reserve_minor)
    causes = [_driver_text(d) for d in result.drivers if d.kind != "income_after_risk"]
    reasons = f" Основные причины: {', '.join(causes[:3])}." if causes else ""
    income = next((d for d in result.drivers if d.kind == "income_after_risk"), None)
    income_text = (
        f" {income.label} ожидается {day_text(income.day)}." if income and income.day else ""
    )
    freshness = f" Данные на {day_text(data_as_of.date())}."
    if result.risk_level == "high" and result.risk_date is not None:
        head = (
            f"На {day_text(result.risk_date)} остаток может опуститься ниже резерва "
            f"{reserve}: минимум около {rub(result.min_p50_minor)} "
            f"({day_text(result.min_p50_day)})."
        )
    elif result.risk_level == "medium" and result.risk_date is not None:
        head = (
            f"В базовом сценарии резерв {reserve} сохраняется, но при задержке дохода или "
            f"больших тратах остаток может опуститься до {rub(result.min_p10_minor)} "
            f"около {day_text(result.risk_date)}."
        )
    else:
        head = (
            f"На {len(result.points)} дней остаток не опускается ниже резерва {reserve}: "
            f"минимум около {rub(result.min_p50_minor)} ({day_text(result.min_p50_day)})."
        )
        return head + freshness
    return head + reasons + income_text + freshness


def notes(flags: list[str]) -> list[str]:
    return [FLAG_NOTES[f] for f in flags if f in FLAG_NOTES]
