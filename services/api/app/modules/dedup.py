"""Дедупликация (FR-08, раздел 7.2): точные дубли отбрасываются при загрузке по
``(account, source, external_id)``; здесь — **вероятные** дубли, которые нельзя
удалять молча.

Правила — консервативные, чтобы не принять две настоящие покупки за дубль:

* ``same_moment`` — тот же счёт, сумма и время с точностью до минуты, но разные
  ``external_id`` (выписка задвоила платёж с другой датой учёта, раздел 12.3);
* ``cross_source`` — тот же счёт, сумма и календарный день, похожее описание,
  но операции пришли из разных источников (например, демо-история и CSV).

Две поездки в метро за день из одного источника — разные операции, это не дубль.
Решение принимает пользователь; подтверждённый дубль не участвует в модели трат.
"""

import re
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Transaction, User
from app.domain.enums import TxStatus

REASON_SAME_MOMENT = "same_moment"
REASON_CROSS_SOURCE = "cross_source"
REASON_NOT_DUPLICATE = "not_duplicate"
_WORDS = re.compile(r"[^\w]+", re.UNICODE)


def _normalize(text: str | None) -> str:
    return " ".join(_WORDS.split((text or "").lower().replace("ё", "е"))).strip()


def _similar(a: str | None, b: str | None) -> bool:
    left, right = _normalize(a), _normalize(b)
    if not left or not right:
        return True  # у одной из сторон описания нет — решает пользователь
    return left == right or left in right or right in left


def _minute(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(second=0, microsecond=0)


def detect_duplicates(db: Session, user: User) -> int:
    """Помечает новые вероятные дубли; возвращает их число. Идемпотентно."""
    rows = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.status != TxStatus.CANCELED,
            Transaction.duplicate_of_id.is_(None),
        )
        .order_by(Transaction.occurred_at, Transaction.id)
    ).all()
    groups: dict[tuple[str, int, str], list[Transaction]] = defaultdict(list)
    for tx in rows:
        groups[(tx.account_id, tx.amount_minor, tx.occurred_at.date().isoformat())].append(tx)

    flagged = 0
    for group in groups.values():
        if len(group) < 2:
            continue
        for later_index in range(1, len(group)):
            later = group[later_index]
            if later.duplicate_candidate_id or later.review_reason == REASON_NOT_DUPLICATE:
                continue
            for earlier in group[:later_index]:
                if earlier.duplicate_candidate_id == later.id:
                    continue
                if _minute(earlier.occurred_at) == _minute(later.occurred_at):
                    reason = REASON_SAME_MOMENT
                elif earlier.source_id != later.source_id and _similar(
                    earlier.description, later.description
                ):
                    reason = REASON_CROSS_SOURCE
                else:
                    continue
                later.duplicate_candidate_id = earlier.id
                later.review_reason = reason
                later.needs_review = True
                flagged += 1
                break
    db.flush()
    return flagged


def pending_duplicates(db: Session, user: User) -> list[tuple[Transaction, Transaction]]:
    rows = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.duplicate_candidate_id.is_not(None),
            Transaction.duplicate_of_id.is_(None),
            Transaction.review_reason.in_([REASON_SAME_MOMENT, REASON_CROSS_SOURCE]),
        )
    ).all()
    pairs: list[tuple[Transaction, Transaction]] = []
    for tx in rows:
        original = db.get(Transaction, tx.duplicate_candidate_id)
        if original is not None:
            pairs.append((tx, original))
    pairs.sort(key=lambda pair: (pair[0].occurred_at, pair[0].id), reverse=True)
    return pairs


def resolve(tx: Transaction, decision: str) -> None:
    if decision == "duplicate":
        tx.duplicate_of_id = tx.duplicate_candidate_id
        tx.review_reason = "confirmed_duplicate"
    else:
        tx.duplicate_candidate_id = None
        tx.review_reason = REASON_NOT_DUPLICATE
    tx.needs_review = False
