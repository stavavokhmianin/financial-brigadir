"""Контракт банковского адаптера (раздел 22.4).

``ConsentToken`` — абстракция, а не реальный токен банка. Живой коннектор
допускается только после официального доступа и описания протокола; пароли
интернет-банка никогда не вводятся.
"""

from financial_sdk import (
    BankConnector,
    ConsentToken,
    SourceAccount,
    SourceBalance,
    SourcePage,
    SourceTransaction,
)

__all__ = [
    "BankConnector",
    "ConsentToken",
    "SourceAccount",
    "SourceBalance",
    "SourcePage",
    "SourceTransaction",
]
