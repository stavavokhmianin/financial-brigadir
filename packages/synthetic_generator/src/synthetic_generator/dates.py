"""Календарные помощники без внешних зависимостей."""

import calendar
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta, timezone

# Москва живёт без перехода на летнее время с 2014 года, поэтому фиксированного
# смещения достаточно и не нужен tzdata на Windows.
MSK = timezone(timedelta(hours=3), "MSK")


def clamp_day(year: int, month: int, day: int) -> date:
    """День месяца с переносом на последний день: 31 → 30 апреля, 28/29 февраля."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def add_months(value: date, months: int) -> date:
    index = value.year * 12 + (value.month - 1) + months
    year, month = divmod(index, 12)
    return clamp_day(year, month + 1, value.day)


def iter_months(start: date, end: date) -> Iterator[tuple[int, int]]:
    """Все (год, месяц), пересекающиеся с отрезком [start, end]."""
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > 12:
            year, month = year + 1, 1


def iter_days(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=MSK)


def is_short_month(day: date) -> bool:
    return calendar.monthrange(day.year, day.month)[1] < 31
