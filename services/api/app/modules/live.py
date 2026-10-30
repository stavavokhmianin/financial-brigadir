"""Живой учебный аккаунт (ADR-0007, пп. 5–6): ленивое виртуальное время поверх синтетики.

Фонового процесса нет. Виртуальная дата вычисляется из реального времени при каждом
запросе пользователя, и в этот момент в реестр переносятся операции синтетического
будущего, которые по виртуальному времени уже случились. Будущее сгенерировано один
раз при создании аккаунта, до раскрытия лежит в отдельной таблице, и прогноз его не
читает. Неактивный аккаунт ничего не стоит серверу.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Account, DataSource, LiveClock, LivePendingTransaction, User
from app.domain.enums import DataSourceKind
from app.domain.ids import new_id
from app.modules.ledger import ingest_transactions

if TYPE_CHECKING:
    from app.adapters.synthetic import SyntheticBundle

# Без новых операций дата актуальности сдвигается не чаще раза в виртуальный час:
# иначе каждый запрос писал бы в базу.
IDLE_WRITE_STEP = timedelta(hours=1)


@dataclass(frozen=True)
class LiveOptions:
    seconds_per_day: int
    horizon_days: int


@dataclass(frozen=True)
class LiveState:
    virtual_now: datetime
    virtual_start: datetime
    ends_at: datetime
    seconds_per_day: int
    paused: bool
    finished: bool
    revealed_total: int
    pending: int


def pick_profile(available: list[str], seed: int) -> str:
    """Основа синтетики выбирается сервером и пользователю как персонаж не показывается."""
    ordered = sorted(available)
    return ordered[seed % len(ordered)]


def attach_live_clock(
    db: Session, user: User, bundle: "SyntheticBundle", options: LiveOptions, now: datetime
) -> LiveClock:
    """Скрытое будущее профиля — в очередь раскрытия, виртуальные часы — на дату выгрузки."""
    for record in bundle.hidden:
        db.add(
            LivePendingTransaction(
                id=new_id("lpt"),
                user_id=user.id,
                occurred_at=datetime.fromisoformat(record["occurred_at"]),
                payload=record,
                counts_in_balance=record["status"] == "posted"
                and record["external_id"] not in bundle.duplicate_external_ids,
            )
        )
    clock = LiveClock(
        user_id=user.id,
        virtual_start=bundle.as_of,
        virtual_end=bundle.as_of + timedelta(days=options.horizon_days),
        real_start=now,
        seconds_per_day=options.seconds_per_day,
        paused_at=None,
        paused_seconds=0.0,
        skipped_days=0,
        revealed_until=bundle.as_of,
        revealed_total=0,
    )
    db.add(clock)
    return clock


def virtual_now(clock: LiveClock, now: datetime) -> datetime:
    reference = clock.paused_at or now
    elapsed = (reference - clock.real_start).total_seconds() - clock.paused_seconds
    days = max(0.0, elapsed) / clock.seconds_per_day + clock.skipped_days
    return min(clock.virtual_start + timedelta(days=days), clock.virtual_end)


def sync(db: Session, user: User, now: datetime) -> int:
    """Перенести в реестр то, что по виртуальному времени уже случилось. Возвращает число."""
    clock = db.get(LiveClock, user.id)
    if clock is None:
        return 0
    moment = virtual_now(clock, now)
    if moment <= clock.revealed_until:
        return 0
    due = list(
        db.scalars(
            select(LivePendingTransaction)
            .where(
                LivePendingTransaction.user_id == user.id,
                LivePendingTransaction.occurred_at <= moment,
            )
            .order_by(LivePendingTransaction.occurred_at, LivePendingTransaction.id)
        )
    )
    if not due and moment - clock.revealed_until < IDLE_WRITE_STEP:
        return 0
    source = db.scalars(
        select(DataSource).where(
            DataSource.user_id == user.id, DataSource.kind == DataSourceKind.SYNTHETIC
        )
    ).first()
    if source is None:
        return 0
    accounts = {
        a.external_id: a
        for a in db.scalars(select(Account).where(Account.user_id == user.id))
        if a.external_id is not None
    }
    try:
        if due:
            ingest_transactions(
                db,
                user,
                source,
                {external: account.id for external, account in accounts.items()},
                [item.payload for item in due],
            )
            for item in due:
                # Остаток меняется так же, как в генераторе: проведённые операции без дублей.
                if item.counts_in_balance:
                    accounts[item.payload["account_id"]].available_balance_minor += int(
                        item.payload["amount_minor"]
                    )
                db.delete(item)
        for account in accounts.values():
            account.updated_at = moment
        source.data_as_of = moment
        source.history_to = moment.date()
        clock.revealed_until = moment
        clock.revealed_total += len(due)
        db.commit()
    except IntegrityError:
        # Параллельный запрос того же пользователя уже раскрыл эти операции.
        db.rollback()
        return 0
    return len(due)


def state(db: Session, clock: LiveClock, now: datetime) -> LiveState:
    moment = virtual_now(clock, now)
    pending = db.scalar(
        select(func.count())
        .select_from(LivePendingTransaction)
        .where(LivePendingTransaction.user_id == clock.user_id)
    )
    return LiveState(
        virtual_now=moment,
        virtual_start=clock.virtual_start,
        ends_at=clock.virtual_end,
        seconds_per_day=clock.seconds_per_day,
        paused=clock.paused_at is not None,
        finished=moment >= clock.virtual_end,
        revealed_total=clock.revealed_total,
        pending=pending or 0,
    )


def next_day(db: Session, user: User, clock: LiveClock, now: datetime) -> None:
    """Ручной шаг для показа: плюс виртуальные сутки, и в паузе тоже."""
    clock.skipped_days += 1
    db.commit()
    sync(db, user, now)


def pause(db: Session, clock: LiveClock, now: datetime) -> None:
    if clock.paused_at is None:
        clock.paused_at = now
        db.commit()


def resume(db: Session, clock: LiveClock, now: datetime) -> None:
    if clock.paused_at is not None:
        clock.paused_seconds += (now - clock.paused_at).total_seconds()
        clock.paused_at = None
        db.commit()
