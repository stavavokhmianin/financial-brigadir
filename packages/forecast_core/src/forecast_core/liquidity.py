"""Доступные ликвидные средства (раздел 7.3 и инвариант 23.2.3).

Кредитные лимиты, заблокированные суммы и неликвидные счета (депозиты) не
складываются с деньгами на расчётных счетах.
"""

from collections.abc import Iterable

from forecast_core.types import AccountSnapshot, AccountType

_LIQUID_TYPES = frozenset({AccountType.DEBIT, AccountType.CASH, AccountType.SAVINGS})


def liquid_balance_minor(accounts: Iterable[AccountSnapshot], currency: str = "RUB") -> int:
    """Сумма свободных собственных средств в копейках.

    Кредитная карта учитывается как обязательство, а не как ликвидность, поэтому
    её баланс (и тем более лимит) сюда не входит. Отрицательный баланс дебетовой
    карты (технический овердрафт) уменьшает сумму — его нельзя молча обнулять.
    """
    total = 0
    for account in accounts:
        if account.currency != currency:
            raise ValueError(
                f"счёт {account.id}: валюта {account.currency} не поддерживается в MVP"
            )
        if account.type not in _LIQUID_TYPES or not account.is_liquid:
            continue
        total += account.balance_minor - account.blocked_minor
    return total
