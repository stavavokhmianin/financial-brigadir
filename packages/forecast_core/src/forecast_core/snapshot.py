"""Воспроизводимость расчёта (раздел 13.3): отпечаток входного снимка."""

import dataclasses
import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any

from forecast_core.types import ForecastInputSnapshot


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"не сериализуется: {type(value).__name__}")


def snapshot_fingerprint(snapshot: ForecastInputSnapshot) -> str:
    """SHA-256 канонического JSON снимка.

    Одинаковые входные данные дают одинаковый отпечаток независимо от порядка
    счетов и событий, поэтому его можно хранить в ``ForecastRun`` и использовать
    как ключ идемпотентности расчёта.
    """
    raw = dataclasses.asdict(snapshot)
    for key in ("accounts", "obligations", "incomes", "history"):
        raw[key] = sorted(raw[key], key=lambda item: str(item["id"]))
    raw["extra_expenses"] = sorted(
        raw["extra_expenses"],
        key=lambda item: (item["day"], item["amount_minor"], item["label"]),
    )
    raw["income_shifts"] = sorted(
        raw["income_shifts"], key=lambda item: (item["income_id"], item["shift_days"])
    )
    canonical = json.dumps(raw, default=_default, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
