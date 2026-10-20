"""Replay-тесты (разделы 13.3, 23.2.6): повторная доставка не удваивает финансовый эффект.

Проверяются три свойства:
* повторная загрузка того же набора — 0 новых операций, суммы не меняются;
* перемешанный порядок доставки даёт тот же реестр;
* произвольные пересекающиеся куски выписки, импортированные в любом порядке,
  дают ровно уникальные строки (property-based, hypothesis).
"""

import random
from collections.abc import Iterator
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.adapters.csv_import import parse_csv
from app.db.base import Base
from app.db.models import Account, DataSource, Transaction, User
from app.db.session import make_engine
from app.domain.enums import AccountType, DataSourceKind
from app.modules.dedup import detect_duplicates
from app.modules.ledger import ingest_transactions
from synthetic_generator import generate


def _session() -> Iterator[Session]:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _setup(db: Session, account_ids: list[str]) -> tuple[User, DataSource, dict[str, str]]:
    user = User(id="usr_r")
    db.add(user)
    db.flush()
    source = DataSource(id="src_r", user_id=user.id, kind=DataSourceKind.SYNTHETIC, label="r")
    db.add(source)
    db.flush()
    mapping = {}
    for i, external in enumerate(account_ids):
        db.add(
            Account(
                id=f"acc_{i}",
                user_id=user.id,
                source_id=source.id,
                name=external,
                type=AccountType.DEBIT,
                available_balance_minor=0,
            )
        )
        mapping[external] = f"acc_{i}"
    db.flush()
    return user, source, mapping


def _totals(db: Session) -> tuple[int, int]:
    count, total = db.execute(
        select(func.count(), func.coalesce(func.sum(Transaction.amount_minor), 0))
    ).one()
    return int(count), int(total)


def test_replaying_the_same_delivery_changes_nothing() -> None:
    data = generate("two_banks", seed=5)
    records = data["known"]["transactions"]
    for db in _session():
        user, source, mapping = _setup(db, [a["account_id"] for a in data["known"]["accounts"]])
        inserted, duplicates = ingest_transactions(db, user, source, mapping, records)
        first = _totals(db)
        assert (inserted, duplicates) == (len(records), 0)
        again = ingest_transactions(db, user, source, mapping, records)
        assert again == (0, len(records))
        assert _totals(db) == first
        flagged_once = detect_duplicates(db, user)
        assert detect_duplicates(db, user) == 0  # повторный поиск не плодит пометки
        assert flagged_once == len(data["truth"]["duplicate_external_ids"])


def test_shuffled_delivery_gives_the_same_ledger() -> None:
    data = generate("credit_card", seed=3)
    records = data["known"]["transactions"]
    results: list[set[tuple[str, int]]] = []
    for order_seed in (1, 2):
        shuffled: list[dict[str, Any]] = list(records)
        random.Random(order_seed).shuffle(shuffled)  # noqa: S311
        for db in _session():
            user, source, mapping = _setup(db, [a["account_id"] for a in data["known"]["accounts"]])
            ingest_transactions(db, user, source, mapping, shuffled)
            rows = db.execute(select(Transaction.external_id, Transaction.amount_minor)).all()
            results.append({(e, a) for e, a in rows})
    assert results[0] == results[1]
    assert len(results[0]) == len(records)


# Строки уникальны: одинаковые строки в разных кусках получают хэш-id по порядку внутри
# своего файла — известное ограничение (надёжнее, когда в выписке есть id операции банка).
STATEMENT_LINES = [
    f"2026-10-{day:02d};-{100 + day * 7},{day:02d};Покупка {day % 4}" for day in range(1, 29)
]


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    cuts=st.lists(
        st.tuples(st.integers(0, len(STATEMENT_LINES) - 1), st.integers(1, 12)),
        min_size=1,
        max_size=6,
    ),
)
def test_overlapping_statements_import_each_row_once(cuts: list[tuple[int, int]]) -> None:
    header = "Дата;Сумма;Описание\n"
    full = parse_csv((header + "\n".join(STATEMENT_LINES)).encode(), "Europe/Moscow", "acc_0")
    expected = {r["external_id"]: r["amount_minor"] for r in full.records}
    for db in _session():
        user = User(id="usr_r")
        db.add(user)
        db.flush()
        source = DataSource(id="src_csv", user_id=user.id, kind=DataSourceKind.CSV, label="csv")
        db.add(source)
        db.flush()
        db.add(
            Account(
                id="acc_0",
                user_id=user.id,
                name="x",
                type=AccountType.DEBIT,
                available_balance_minor=0,
            )
        )
        db.flush()
        chunks = [STATEMENT_LINES[start : start + size] for start, size in cuts]
        chunks.append(STATEMENT_LINES)  # в конце пользователь загружает всю выписку
        for chunk in chunks:
            parsed = parse_csv((header + "\n".join(chunk)).encode(), "Europe/Moscow", "acc_0")
            ingest_transactions(db, user, source, {"acc_0": "acc_0"}, parsed.records)
        rows = dict(db.execute(select(Transaction.external_id, Transaction.amount_minor)).all())
        assert rows == expected
        assert sum(rows.values()) == sum(expected.values())
