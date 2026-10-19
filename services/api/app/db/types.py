from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Dialect, Enum, TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Время только в UTC и всегда с таймзоной (раздел 14).

    SQLite не хранит смещение, поэтому значение нормализуется на записи и
    помечается как UTC при чтении. Время без таймзоны отклоняется, чтобы
    локальное время не сохранилось молча как UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("datetime без таймзоны запрещён: передайте aware-значение")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Перечисление как VARCHAR + CHECK: одинаково в SQLite и PostgreSQL."""

    def values(members: Any) -> list[str]:
        return [member.value for member in members]

    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=values,
        validate_strings=True,
    )
