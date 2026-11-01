"""JSON-safe сериализация результатов без зависимости от Pydantic."""

import json
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

INTERNAL_FIELDS = frozenset({"trajectories", "daily_history"})


def to_jsonable(value: Any, *, include_internal: bool = False) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: to_jsonable(getattr(value, item.name), include_internal=include_internal)
            for item in fields(value)
            if include_internal or item.name not in INTERNAL_FIELDS
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): to_jsonable(item, include_internal=include_internal)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list, set, frozenset)):
        return [to_jsonable(item, include_internal=include_internal) for item in value]
    return value


def dumps(value: Any, *, include_internal: bool = False, indent: int | None = None) -> str:
    return json.dumps(
        to_jsonable(value, include_internal=include_internal),
        ensure_ascii=False,
        indent=indent,
    )
