"""Explain API (раздел 7.8): объяснение риска детерминированными шаблонами, без LLM."""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from financial_sdk import ForecastResult, RiskDriver, SafeSpend, ScenarioComparison

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
    "simulation_skipped": (
        "Истории меньше 4 недель: вероятности не считаются, прогноз по календарю."
    ),
}


def rub(minor: int) -> str:
    sign = "−" if minor < 0 else ""
    units = round(abs(minor) / 100)
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


LEVEL_TEXT = {"low": "резерв сохраняется", "medium": "возможен риск", "high": "риск нехватки"}


def _event_text(event: Any) -> str:
    if event.type == "expense":
        when = day_text(event.date) if event.date else "сегодня"
        label = event.label or "покупку"
        return f"{when} купить «{label}» за {rub(event.amount_minor or 0)}"
    days = event.shift_days or 0
    direction = "позже" if days > 0 else "раньше"
    return f"доход придёт на {abs(days)} дн. {direction}"


def explain_comparison(
    comparison: ScenarioComparison,
    base: ForecastResult,
    scenario: ForecastResult,
    events: Sequence[Any],
    safe: SafeSpend,
) -> str:
    """«Что будет, если…» (раздел 11.3): изменение минимума, уровня и даты риска."""
    what = " и ".join(_event_text(e) for e in events)
    parts = [
        f"Если {what}: минимум остатка {rub(base.min_p50_minor)} → {rub(scenario.min_p50_minor)}"
        f", {LEVEL_TEXT[comparison.risk_level_before]} → {LEVEL_TEXT[comparison.risk_level_after]}."
    ]
    if comparison.risk_date_after and comparison.risk_date_after != comparison.risk_date_before:
        parts.append(f"Резерв под угрозой с {day_text(comparison.risk_date_after)}.")
    if safe.available:
        careful = (
            f"с запасом на плохой сценарий — до {rub(safe.conservative_minor)}"
            if safe.conservative_minor > 0
            else "в плохом сценарии лучше ничего не тратить"
        )
        parts.append(
            # Не «без риска»: модель — оценка, а не гарантия (ADR-0006).
            f"По расчёту резерв сохранится при покупке {day_text(safe.day)} до "
            f"{rub(safe.base_minor)} ({careful})."
        )
    else:
        parts.append("Данных недостаточно, чтобы назвать безопасную сумму.")
    return " ".join(parts)
