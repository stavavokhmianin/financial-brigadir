from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from financial_sdk.models import FinancialData
from financial_sdk.normalization import normalize_financial_data


@dataclass(frozen=True, slots=True)
class InMemoryAdapter:
    """Адаптер для уже загруженного JSON/dict — удобен для API и тестов."""

    source: FinancialData | Mapping[str, Any]

    def load(self) -> FinancialData:
        if isinstance(self.source, FinancialData):
            return self.source
        return normalize_financial_data(self.source)
