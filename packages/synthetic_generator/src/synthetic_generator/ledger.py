"""Построитель синтетической истории: счета, операции, будущие события.

Генератор намеренно **не** использует алгоритм прогноза: он моделирует
«как было на самом деле» (включая скрытое будущее), а прогнозный движок потом
оценивается на этих данных (раздел 23.1).
"""

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from synthetic_generator.dates import MSK, at, clamp_day, iter_days, iter_months

POSTED = "posted"
PENDING = "pending"
CANCELED = "canceled"


@dataclass
class AccountSpec:
    key: str
    name: str
    bank_name: str
    type: str  # debit | credit_card | savings | deposit | cash
    credit_limit_minor: int | None = None
    is_liquid: bool = True
    owner: str | None = None  # для семейного профиля


@dataclass
class IncomeSpec:
    key: str
    title: str
    kind: str  # salary | advance | freelance | other
    account: str
    day: int
    amount_minor: int
    jitter_minor: int = 0
    # Фактические задержки: (год, месяц) → дни. Используются и в истории,
    # и в скрытом будущем.
    delays: dict[tuple[int, int], int] = field(default_factory=dict)
    max_delay_days: int = 0
    probability: float = 1.0
    confirmed: bool = True


@dataclass
class ObligationSpec:
    key: str
    kind: str  # rent | loan | utilities | subscription | installment | credit_card | manual
    title: str
    account: str
    day: int
    amount_minor: int
    jitter_minor: int = 0
    status: str = "confirmed"
    priority: str = "critical"
    movable: bool = False
    confidence: float = 1.0
    starts: date | None = None
    ends: date | None = None
    category: str | None = None


@dataclass
class SpendSpec:
    category: str
    account: str
    probability: float
    median_minor: int
    sigma: float = 0.5
    weekend_factor: float = 1.0
    description: str | None = None


@dataclass
class Tx:
    external_id: str
    account: str
    occurred_at: datetime
    booked_at: datetime
    amount_minor: int
    type: str
    category: str | None
    status: str
    description: str | None = None
    transfer_group_id: str | None = None
    related_external_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class Ledger:
    def __init__(
        self,
        profile_key: str,
        prefix: str,
        seed: int,
        as_of: datetime,
        months: int,
        horizon_days: int,
    ) -> None:
        if as_of.tzinfo is None:
            raise ValueError("as_of должен быть с таймзоной")
        self.profile_key = profile_key
        self.prefix = prefix
        # Не криптография: воспроизводимая синтетика, строковый seed детерминирован.
        self.rng = random.Random(f"{profile_key}:{seed}")  # noqa: S311
        self.as_of = as_of.astimezone(MSK)
        self.today = self.as_of.date()
        self.history_from = self._months_back(self.today, months)
        self.horizon_end = self.today + timedelta(days=horizon_days)
        self.accounts: dict[str, AccountSpec] = {}
        self.incomes: list[IncomeSpec] = []
        self.obligations: list[ObligationSpec] = []
        self.spending: list[SpendSpec] = []
        self.txs: list[Tx] = []
        self.openings: dict[str, int] = {}
        self.anomalies: list[dict[str, Any]] = []
        self.hidden_events: list[dict[str, Any]] = []
        self.reupload: list[Tx] = []
        self.manual_balances: dict[str, int] = {}
        self.missing: list[Tx] = []  # реальные операции, которых нет в выписке
        self.duplicates: list[str] = []  # ложные дубли выписки (не влияют на остаток)
        self.partial_accounts: set[str] = set()
        self.extra_incomes: list[dict[str, Any]] = []
        self.extra_obligations: list[dict[str, Any]] = []
        self._seq: dict[str, int] = defaultdict(int)
        self._groups = 0

    @staticmethod
    def _months_back(value: date, months: int) -> date:
        index = value.year * 12 + (value.month - 1) - months
        year, month = divmod(index, 12)
        return clamp_day(year, month + 1, value.day)

    # --- справочники -------------------------------------------------------

    def account_id(self, key: str) -> str:
        return f"acc_{self.prefix}_{key}"

    def add_account(self, spec: AccountSpec) -> None:
        self.accounts[spec.key] = spec

    # --- операции ----------------------------------------------------------

    def random_time(self, day: date, start_hour: int = 8, end_hour: int = 22) -> datetime:
        return at(day, self.rng.randint(start_hour, end_hour), self.rng.randint(0, 59))

    def tx(
        self,
        account: str,
        when: datetime,
        amount_minor: int,
        type_: str,
        category: str | None,
        *,
        status: str | None = None,
        description: str | None = None,
        transfer_group_id: str | None = None,
        related_external_id: str | None = None,
        booked_delay_days: int = 0,
        extra: dict[str, Any] | None = None,
    ) -> Tx:
        if account not in self.accounts:
            raise KeyError(f"неизвестный счёт {account}")
        if amount_minor == 0:
            raise ValueError("нулевая операция")
        self._seq[account] += 1
        external_id = f"{self.prefix}-{account}-{self._seq[account]:05d}"
        if status is None:
            # Сегодняшние карточные списания до момента выгрузки ещё не проведены.
            is_card_spend = type_ in ("expense", "credit_purchase") and amount_minor < 0
            status = (
                PENDING
                if is_card_spend and when.date() == self.today and when <= self.as_of
                else POSTED
            )
        tx = Tx(
            external_id=external_id,
            account=account,
            occurred_at=when,
            booked_at=when + timedelta(days=booked_delay_days),
            amount_minor=amount_minor,
            type=type_,
            category=category,
            status=status,
            description=description,
            transfer_group_id=transfer_group_id,
            related_external_id=related_external_id,
            extra=extra or {},
        )
        self.txs.append(tx)
        return tx

    def next_group(self) -> str:
        self._groups += 1
        return f"tg_{self.prefix}_{self._groups:04d}"

    def transfer(
        self, src: str, dst: str, when: datetime, amount_minor: int, interbank: bool = False
    ) -> tuple[Tx, Tx]:
        """Перевод между своими счетами: две связанные операции с суммой 0."""
        group = self.next_group()
        delay = 1 if interbank else 0
        out = self.tx(
            src,
            when,
            -amount_minor,
            "transfer_out",
            "transfer",
            description="Перевод между своими счетами",
            transfer_group_id=group,
        )
        inn = self.tx(
            dst,
            when + timedelta(minutes=1),
            amount_minor,
            "transfer_in",
            "transfer",
            description="Перевод между своими счетами",
            transfer_group_id=group,
            booked_delay_days=delay,
        )
        return out, inn

    def credit_card_payment(
        self, src: str, card: str, when: datetime, amount_minor: int
    ) -> tuple[Tx, Tx]:
        """Погашение кредитки: уменьшает ликвидность и долг, но не является новой тратой."""
        group = self.next_group()
        out = self.tx(
            src,
            when,
            -amount_minor,
            "credit_payment",
            "credit_card_payment",
            description="Погашение кредитной карты",
            transfer_group_id=group,
        )
        inn = self.tx(
            card,
            when,
            amount_minor,
            "credit_payment",
            "credit_card_payment",
            description="Погашение кредитной карты",
            transfer_group_id=group,
        )
        return out, inn

    def refund(self, original: Tx, when: datetime, amount_minor: int | None = None) -> Tx:
        amount = amount_minor if amount_minor is not None else -original.amount_minor
        if amount <= 0 or amount > -original.amount_minor:
            raise ValueError("возврат должен быть положительным и не больше покупки")
        return self.tx(
            original.account,
            when,
            amount,
            "refund",
            original.category,
            description=f"Возврат: {original.description or original.category}",
            related_external_id=original.external_id,
        )

    def anomaly(self, type_: str, note: str, **data: Any) -> None:
        self.anomalies.append({"type": type_, "note": note, **data})

    # --- регулярная часть --------------------------------------------------

    def simulate_regular(self) -> None:
        start, end = self.history_from, self.horizon_end
        for year, month in iter_months(start, end):
            for income in self.incomes:
                scheduled = clamp_day(year, month, income.day)
                actual = scheduled + timedelta(days=income.delays.get((year, month), 0))
                if not start <= actual <= end:
                    continue
                jitter = self.rng.randint(-income.jitter_minor, income.jitter_minor)
                self.tx(
                    income.account,
                    at(actual, 9, self.rng.randint(0, 50)),
                    income.amount_minor + jitter,
                    "income",
                    income.kind,
                    description=income.title,
                )
            for obligation in self.obligations:
                due = clamp_day(year, month, obligation.day)
                if not start <= due <= end:
                    continue
                if obligation.starts and due < obligation.starts:
                    continue
                if obligation.ends and due > obligation.ends:
                    continue
                jitter = self.rng.randint(-obligation.jitter_minor, obligation.jitter_minor)
                type_ = (
                    "credit_purchase"
                    if self.accounts[obligation.account].type == "credit_card"
                    else "expense"
                )
                self.tx(
                    obligation.account,
                    at(due, 8, self.rng.randint(0, 50)),
                    -(obligation.amount_minor + jitter),
                    type_,
                    obligation.category or obligation.kind,
                    description=obligation.title,
                )
        for day in iter_days(start, end):
            weekend = day.weekday() >= 5
            for spend in self.spending:
                probability = spend.probability * (spend.weekend_factor if weekend else 1.0)
                if self.rng.random() >= min(probability, 0.95):
                    continue
                amount = max(
                    100, round(spend.median_minor * self.rng.lognormvariate(0, spend.sigma))
                )
                type_ = (
                    "credit_purchase"
                    if self.accounts[spend.account].type == "credit_card"
                    else "expense"
                )
                self.tx(
                    spend.account,
                    self.random_time(day),
                    -amount,
                    type_,
                    spend.category,
                    description=spend.description,
                    booked_delay_days=self.rng.choice((0, 0, 1)),
                )

    # --- остатки -----------------------------------------------------------

    def counts_in_balance(self, tx: Tx) -> bool:
        return tx.status == POSTED and tx.external_id not in self.duplicates

    def running_min(self, account: str, until: datetime) -> int:
        """Минимум накопленной суммы проведённых операций (без входящего остатка)."""
        balance = 0
        minimum = 0
        for tx in sorted(self._true_txs(account), key=lambda t: t.occurred_at):
            if tx.occurred_at > until:
                break
            balance += tx.amount_minor
            minimum = min(minimum, balance)
        return minimum

    def _true_txs(self, account: str) -> list[Tx]:
        true = [t for t in self.txs if t.account == account and self.counts_in_balance(t)]
        return true + [t for t in self.missing if t.account == account]

    def balance_at(self, account: str, when: datetime) -> int:
        total = self.openings.get(account, 0)
        for tx in self._true_txs(account):
            if tx.occurred_at <= when:
                total += tx.amount_minor
        return total

    def set_openings(self, floors: dict[str, int], targets: dict[str, int] | None = None) -> None:
        """Входящие остатки.

        По умолчанию минимум истории равен заданному «полу». Если для счёта задан
        целевой остаток на дату выгрузки, входящий остаток подбирается под него
        (так строится воспроизводимый демо-сценарий).
        """
        targets = targets or {}
        for key, spec in self.accounts.items():
            if spec.type == "credit_card":
                self.openings[key] = 0
            elif key in targets:
                self.openings[key] = 0
                self.openings[key] = targets[key] - self.balance_at(key, self.as_of)
            else:
                floor = floors.get(key, 500_000)
                self.openings[key] = max(0, floor - self.running_min(key, self.as_of))

    def pending_minor(self, account: str) -> int:
        return sum(
            -t.amount_minor
            for t in self.txs
            if t.account == account and t.status == PENDING and t.amount_minor < 0
        )
