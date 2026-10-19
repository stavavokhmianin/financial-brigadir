"""Генератор синтетических профилей (раздел 12 ТЗ).

Профиль — 6–12 месяцев истории, подтверждённые и скрытые будущие события и
обязательные аномалии. Результат полностью определяется ``(profile_id, seed,
as_of, months, horizon_days)``.
"""

from synthetic_generator.generator import (
    DEFAULT_AS_OF,
    DEFAULT_HORIZON_DAYS,
    DEFAULT_MONTHS,
    DEFAULT_SEED,
    SCHEMA_VERSION,
    generate,
    list_profiles,
)
from synthetic_generator.profiles import PROFILES

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_AS_OF",
    "DEFAULT_HORIZON_DAYS",
    "DEFAULT_MONTHS",
    "DEFAULT_SEED",
    "PROFILES",
    "SCHEMA_VERSION",
    "generate",
    "list_profiles",
]
