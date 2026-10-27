"""Денежные значения.

На границе системы деньги — целые копейки (``amount_minor: int``), раздел 8.1/14.
``float`` допустим только внутри статистического моделирования, не здесь.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MINOR_PER_UNIT = 100


def parse_rub_to_minor(value: str | int | Decimal) -> int:
    """Переводит сумму в рублях («1 234,56», «-1450.00», 12) в целые копейки.

    Дробная часть округляется до копейки по правилу half-up. Значения с
    плавающей точкой не принимаются намеренно, чтобы не тащить ошибку
    двоичного представления.
    """
    if isinstance(value, bool):
        raise TypeError("bool не является денежной суммой")
    if isinstance(value, int):
        return value * MINOR_PER_UNIT
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, str):
        cleaned = (
            value.strip()
            .replace(" ", "")
            .replace(" ", "")
            .replace(" ", "")
            .replace(",", ".")
            .replace("−", "-")
        )
        if not cleaned:
            raise ValueError("пустая сумма")
        try:
            amount = Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError(f"не удалось разобрать сумму: {value!r}") from exc
    else:
        raise TypeError(f"неподдерживаемый тип суммы: {type(value).__name__}")
    if not amount.is_finite():
        raise ValueError("сумма должна быть конечной")
    minor = (amount * MINOR_PER_UNIT).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(minor)


def format_rub(amount_minor: int) -> str:
    """Человекочитаемая сумма: ``-145000`` → ``"-1 450,00 ₽"``."""
    sign = "-" if amount_minor < 0 else ""
    units, minor = divmod(abs(amount_minor), MINOR_PER_UNIT)
    grouped = f"{units:,}".replace(",", " ")
    return f"{sign}{grouped},{minor:02d} ₽"
