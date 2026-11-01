"""Конфигурируемый CSV-адаптер истории операций."""

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import StringIO
from zoneinfo import ZoneInfo

from financial_sdk.models import FinancialData
from financial_sdk.normalization import NormalizationError
from forecast_core import (
    AccountSnapshot,
    Coverage,
    HistoricalTransaction,
    TxStatus,
    TxType,
)


@dataclass(frozen=True, slots=True)
class CSVColumns:
    occurred_at: str = "occurred_at"
    amount: str = "amount_minor"
    external_id: str = "id"
    description: str = "description"
    category: str = "category"
    type: str = "type"
    status: str = "status"


@dataclass(frozen=True, slots=True)
class CSVTransactionsAdapter:
    """Одна CSV-выписка + переданный вызывающей стороной снимок счёта.

    ``amount_unit='minor'`` означает целые копейки, ``'major'`` — рубли с
    десятичной частью. SDK не угадывает формат денег молча.
    """

    content: str
    account: AccountSnapshot
    as_of: datetime
    timezone: str = "UTC"
    columns: CSVColumns = CSVColumns()
    delimiter: str = ","
    amount_unit: str = "minor"
    default_type: TxType = TxType.EXPENSE

    def _amount(self, value: str) -> int:
        if self.amount_unit == "minor":
            try:
                return int(value.replace(" ", ""))
            except ValueError as exc:
                raise NormalizationError(f"некорректная сумма: {value}") from exc
        if self.amount_unit != "major":
            raise NormalizationError("amount_unit должен быть minor или major")
        try:
            amount = Decimal(value.replace(" ", "").replace(",", "."))
        except InvalidOperation as exc:
            raise NormalizationError(f"некорректная сумма: {value}") from exc
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def _moment(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(self.timezone))
        return parsed.astimezone(UTC)

    def load(self) -> FinancialData:
        rows = csv.DictReader(StringIO(self.content), delimiter=self.delimiter)
        transactions: list[HistoricalTransaction] = []
        for index, row in enumerate(rows, start=2):
            try:
                transaction_id = row.get(self.columns.external_id) or f"csv-{index}"
                transactions.append(
                    HistoricalTransaction(
                        id=transaction_id,
                        account_id=self.account.id,
                        occurred_at=self._moment(row[self.columns.occurred_at]),
                        amount_minor=self._amount(row[self.columns.amount]),
                        type=TxType(row.get(self.columns.type) or self.default_type),
                        status=TxStatus(row.get(self.columns.status) or TxStatus.POSTED),
                        category=row.get(self.columns.category) or None,
                        description=row.get(self.columns.description) or None,
                    )
                )
            except (KeyError, ValueError) as exc:
                raise NormalizationError(f"CSV, строка {index}: {exc}") from exc
        return FinancialData(
            as_of=self.as_of,
            timezone=self.timezone,
            accounts=(self.account,),
            transactions=tuple(transactions),
            coverage=Coverage.UNKNOWN,
            currency=self.account.currency,
        )
