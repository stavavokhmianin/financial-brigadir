from datetime import date

from forecast_core.calendar import Recurrence, occurrences


def test_monthly_31st_follows_short_months_and_returns() -> None:
    dates = list(
        occurrences(date(2027, 1, 31), Recurrence.MONTHLY, date(2027, 1, 1), date(2027, 4, 30))
    )
    assert dates == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]


def test_window_cuts_and_first_due_is_respected() -> None:
    dates = list(occurrences(date(2026, 10, 23), "monthly", date(2026, 10, 1), date(2026, 11, 22)))
    assert dates == [date(2026, 10, 23)]


def test_one_off_and_weekly() -> None:
    assert list(occurrences(date(2026, 10, 25), "none", date(2026, 10, 19), date(2026, 11, 1))) == [
        date(2026, 10, 25)
    ]
    assert list(occurrences(date(2026, 11, 2), "none", date(2026, 10, 19), date(2026, 11, 1))) == []
    weekly = list(occurrences(date(2026, 10, 20), "weekly", date(2026, 10, 19), date(2026, 11, 3)))
    assert weekly == [date(2026, 10, 20), date(2026, 10, 27), date(2026, 11, 3)]


def test_empty_window() -> None:
    assert (
        list(occurrences(date(2026, 10, 25), "monthly", date(2026, 11, 1), date(2026, 10, 1))) == []
    )
