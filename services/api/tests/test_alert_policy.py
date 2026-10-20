"""Правила Alert Policy Engine (разделы 10, 23.4) — чистые функции."""

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.modules.alert_policy import (
    PastAlert,
    Preferences,
    RiskSignal,
    decide,
    in_quiet_hours,
)

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
NOON = time(12, 0)
SIGNAL = RiskSignal(
    level="high",
    risk_date=date(2026, 10, 23),
    shortfall_minor=1_000_000,
    today=date(2026, 10, 19),
    critical_payment=True,
    stale=False,
    insufficient=False,
)
PREFS = Preferences("smart", None, None, 2, ())


def _decide(signal: RiskSignal = SIGNAL, prefs: Preferences = PREFS, history=(), local=NOON):  # type: ignore[no-untyped-def]
    return decide(signal, prefs, list(history), NOW, local)


def _sent(
    days_ago: float,
    priority: str = "critical",
    shortfall: int = 1_000_000,
    risk_date: date = date(2026, 10, 23),
) -> PastAlert:
    return PastAlert("send", priority, risk_date, shortfall, NOW - timedelta(days=days_ago))


def test_no_risk_no_alert() -> None:
    assert _decide(replace(SIGNAL, level="low", risk_date=None)) is None


def test_new_critical_risk_is_sent() -> None:
    decision = _decide()
    assert decision is not None
    assert (decision.action, decision.reason, decision.priority) == ("send", "new_risk", "critical")


def test_repeat_without_change_is_suppressed_but_change_is_sent() -> None:
    assert _decide(history=[_sent(1)]).reason == "repeat_without_change"  # type: ignore[union-attr]
    moved = _decide(history=[_sent(1, risk_date=date(2026, 10, 29))])
    assert moved is not None and (moved.action, moved.reason) == ("send", "risk_changed")
    deeper = _decide(replace(SIGNAL, shortfall_minor=2_000_000), history=[_sent(1)])
    assert deeper is not None and deeper.action == "send"
    old = _decide(history=[_sent(8)])
    assert old is not None and old.action == "send"  # прошло больше недели


def test_weekly_limit_for_noncritical() -> None:
    minor = replace(SIGNAL, critical_payment=False)
    history = [
        _sent(2, "normal", risk_date=date(2026, 11, 5)),
        _sent(4, "normal", risk_date=date(2026, 11, 15)),
    ]
    decision = _decide(minor, history=history)
    assert decision is not None and decision.reason == "weekly_limit"
    critical = _decide(SIGNAL, history=history)
    assert critical is not None and critical.action == "send"  # лимит не для критичных


@pytest.mark.parametrize(
    ("signal", "prefs", "reason"),
    [
        (replace(SIGNAL, stale=True), PREFS, "stale_data"),
        (replace(SIGNAL, insufficient=True), PREFS, "insufficient_data"),
        (replace(SIGNAL, risk_date=date(2026, 11, 10)), PREFS, "far_horizon"),
        (replace(SIGNAL, critical_payment=False), replace(PREFS, mode="quiet"), "mode_quiet"),
        (replace(SIGNAL, level="medium", critical_payment=False), PREFS, "mode_smart_minor"),
        (SIGNAL, replace(PREFS, disabled_types=("reserve_risk",)), "type_disabled"),
    ],
)
def test_suppression_and_deferral_reasons(
    signal: RiskSignal, prefs: Preferences, reason: str
) -> None:
    decision = _decide(signal, prefs)
    assert decision is not None and decision.reason == reason


def test_active_mode_sends_minor_risks() -> None:
    minor = replace(SIGNAL, level="medium", critical_payment=False)
    decision = _decide(minor, replace(PREFS, mode="active"))
    assert decision is not None and decision.action == "send" and decision.priority == "normal"


def test_quiet_hours_defer_including_overnight() -> None:
    night = Preferences("smart", time(22, 0), time(8, 0), 2, ())
    late = _decide(prefs=night, local=time(23, 30))
    assert late is not None and (late.action, late.reason) == ("defer", "quiet_hours")
    morning = _decide(prefs=night, local=time(8, 0))
    assert morning is not None and morning.action == "send"
    assert in_quiet_hours(time(13, 0), time(13, 0), time(14, 0))
    assert not in_quiet_hours(time(13, 0), None, None)
