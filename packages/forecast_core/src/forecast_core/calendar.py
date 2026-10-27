"""Календарь будущих событий (уровень 0 раздела 23.1: «достоверный календарь»)."""

import calendar as _stdlib_calendar
from collections.abc import Iterator
from datetime import date, timedelta
from enum import StrEnum


class Recurrence(StrEnum):
    NONE = "none"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


def clamp_day(year: int, month: int, day: int) -> date:
    """31-е число в коротком месяце переносится на последний день месяца (12.3)."""
    last = _stdlib_calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def occurrences(
    first_due: date,
    recurrence: Recurrence | str,
    start: date,
    end: date,
    day_of_month: int | None = None,
) -> Iterator[date]:
    """Даты события в отрезке ``[start, end]``.

    ``first_due`` — ближайшая известная дата. Для ежемесячных событий
    ``day_of_month`` задаёт желаемый день (по умолчанию — день ``first_due``),
    поэтому платёж 31-го после февраля снова приходится на 31-е.
    """
    if end < start:
        return
    kind = Recurrence(recurrence)
    if kind is Recurrence.NONE:
        if start <= first_due <= end:
            yield first_due
        return
    if kind is Recurrence.WEEKLY:
        current = first_due
        while current <= end:
            if current >= start:
                yield current
            current += timedelta(days=7)
        return
    wanted = day_of_month or first_due.day
    year, month = first_due.year, first_due.month
    while True:
        current = clamp_day(year, month, wanted)
        if current > end:
            return
        if current >= start and current >= first_due:
            yield current
        month += 1
        if month > 12:
            year, month = year + 1, 1
