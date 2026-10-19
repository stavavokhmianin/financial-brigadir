"""Запись нормализованных операций в реестр с дедупликацией (7.2, 23.2.6)."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataSource, Transaction, User
from app.domain.enums import TxStatus, TxType
from app.domain.ids import new_id


def ingest_transactions(
    db: Session,
    user: User,
    source: DataSource,
    account_ids: dict[str, str],
    records: Iterable[dict[str, Any]],
) -> tuple[int, int]:
    """Добавляет операции; уже известные ``(account, source, external_id)`` пропускает.

    ``account_ids`` сопоставляет id счёта источника с id счёта в реестре.
    Возвраты связываются с исходной операцией по ``related_external_id``.
    Возвращает ``(добавлено, пропущено как дубли)``.
    """
    batch = list(records)
    target_accounts = {account_ids[r["account_id"]] for r in batch}
    known: dict[tuple[str, str], str] = {
        (account_id, external_id): tx_id
        for account_id, external_id, tx_id in db.execute(
            select(Transaction.account_id, Transaction.external_id, Transaction.id).where(
                Transaction.source_id == source.id,
                Transaction.account_id.in_(target_accounts),
            )
        )
    }
    inserted, duplicates = 0, 0
    pending_links: list[tuple[Transaction, str, str]] = []
    for record in batch:
        account_id = account_ids[record["account_id"]]
        key = (account_id, record["external_id"])
        if key in known:
            duplicates += 1
            continue
        tx = Transaction(
            id=new_id("tx"),
            user_id=user.id,
            account_id=account_id,
            source_id=source.id,
            external_id=record["external_id"],
            occurred_at=datetime.fromisoformat(record["occurred_at"]),
            booked_at=(
                datetime.fromisoformat(record["booked_at"]) if record.get("booked_at") else None
            ),
            amount_minor=int(record["amount_minor"]),
            currency=record.get("currency", "RUB"),
            type=TxType(record["type"]),
            status=TxStatus(record["status"]),
            category=record.get("category"),
            description=record.get("description"),
            transfer_group_id=record.get("transfer_group_id"),
        )
        db.add(tx)
        known[key] = tx.id
        inserted += 1
        if record.get("related_external_id"):
            pending_links.append((tx, account_id, record["related_external_id"]))
    for tx, account_id, related_external_id in pending_links:
        original = known.get((account_id, related_external_id))
        if original is None:
            tx.needs_review = True  # исходная покупка не найдена — отметить для пользователя
        else:
            tx.related_transaction_id = original
    db.flush()
    return inserted, duplicates
