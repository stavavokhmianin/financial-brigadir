"""Расширяемая граница источников данных."""

from collections.abc import Callable
from typing import Protocol

from financial_sdk.models import FinancialData


class DataAdapter(Protocol):
    """Синхронный адаптер: источник → нормализованный документ SDK."""

    def load(self) -> FinancialData: ...


class AsyncDataAdapter(Protocol):
    """Асинхронный адаптер для сетевых источников и Open Banking."""

    async def load(self) -> FinancialData: ...


Adapter = DataAdapter | AsyncDataAdapter
AdapterFactory = Callable[..., Adapter]


class AdapterRegistry:
    """Реестр без глобального состояния; приложение само выбирает доступные коннекторы."""

    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}

    def register(self, name: str, factory: AdapterFactory, *, replace: bool = False) -> None:
        key = name.strip().casefold()
        if not key:
            raise ValueError("имя адаптера не может быть пустым")
        if key in self._factories and not replace:
            raise ValueError(f"адаптер уже зарегистрирован: {key}")
        self._factories[key] = factory

    def create(self, name: str, **config: object) -> Adapter:
        key = name.strip().casefold()
        try:
            factory = self._factories[key]
        except KeyError as exc:
            raise KeyError(f"неизвестный адаптер: {key}") from exc
        return factory(**config)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
