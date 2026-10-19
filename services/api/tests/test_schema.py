"""Инварианты схемы данных (раздел 8, 23.2), проверяемые на уровне БД."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Account,
    DataSource,
    IncomeEvent,
    Obligation,
    Transaction,
    User,
)
from app.domain.enums import (
    AccountType,
    DataSourceKind,
    IncomeKind,
    ObligationKind,
    ObligationStatus,
    TxStatus,
    TxType,
)

NOW = datetime(2026, 10, 19, 7, 0, tzinfo=UTC)


@pytest.fixture
def db(db_session_factory: sessionmaker[Session]) -> Session:
    session = db_session_factory()
    session.add(User(id="usr_1"))
    session.flush()
    session.add(
        DataSource(id="src_1", user_id="usr_1", kind=DataSourceKind.SYNTHETIC, label="demo")
    )
    session.flush()
    session.add(
        Account(
            id="acc_1",
            user_id="usr_1",
            source_id="src_1",
            name="Дебетовая",
            type=AccountType.DEBIT,
            available_balance_minor=3_500_000,
        )
    )
    session.commit()
    return session


def _tx(external_id: str, **kw: object) -> Transaction:
    values: dict[str, object] = {
        "id": f"tx_{external_id}",
        "user_id": "usr_1",
        "account_id": "acc_1",
        "source_id": "src_1",
        "external_id": external_id,
        "occurred_at": NOW,
        "amount_minor": -145_000,
        "type": TxType.EXPENSE,
        "status": TxStatus.POSTED,
    }
    values.update(kw)
    return Transaction(**values)


def test_redelivery_of_same_external_id_is_rejected(db: Session) -> None:
    db.add(_tx("demo-001"))
    db.commit()
    db.add(_tx("demo-001", id="tx_other"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_datetimes_are_stored_and_returned_as_utc(db: Session) -> None:
    moscow = timezone(timedelta(hours=3))
    db.add(_tx("demo-002", occurred_at=datetime(2026, 10, 9, 14, 10, tzinfo=moscow)))
    db.commit()
    db.expire_all()
    stored = db.scalars(select(Transaction).where(Transaction.external_id == "demo-002")).one()
    assert stored.occurred_at == datetime(2026, 10, 9, 11, 10, tzinfo=UTC)
    assert stored.occurred_at.tzinfo is not None


def test_naive_datetime_is_rejected(db: Session) -> None:
    db.add(_tx("demo-003", occurred_at=datetime(2026, 10, 9, 14, 10)))  # noqa: DTZ001
    with pytest.raises(StatementError):
        db.commit()


def test_unknown_enum_value_is_rejected(db: Session) -> None:
    db.add(_tx("demo-004", type="salary"))
    with pytest.raises(StatementError):
        db.commit()


def _obligation(**kw: object) -> Obligation:
    values: dict[str, object] = {
        "id": "obl_1",
        "user_id": "usr_1",
        "kind": ObligationKind.RENT,
        "title": "Аренда",
        "amount_minor": 1_800_000,
        "due_date": date(2026, 10, 25),
        "status": ObligationStatus.CONFIRMED,
    }
    values.update(kw)
    return Obligation(**values)


@pytest.mark.parametrize(
    "bad",
    [
        {"amount_minor": 0},
        {"amount_min_minor": 2_000_000, "amount_max_minor": 1_000_000},
        {"confidence": 1.5},
        {"recurrence_day": 32},
    ],
)
def test_obligation_constraints(db: Session, bad: dict[str, object]) -> None:
    db.add(_obligation(**bad))
    with pytest.raises(IntegrityError):
        db.commit()


def test_income_event_requires_ordered_ranges(db: Session) -> None:
    db.add(
        IncomeEvent(
            id="inc_1",
            user_id="usr_1",
            kind=IncomeKind.SALARY,
            title="Зарплата",
            date_from=date(2026, 10, 27),
            date_to=date(2026, 10, 25),
            amount_min_minor=9_000_000,
            amount_max_minor=9_000_000,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_user_cascades_to_personal_data(db: Session) -> None:
    db.add(_tx("demo-005"))
    db.add(_obligation())
    db.commit()
    db.delete(db.get(User, "usr_1"))
    db.commit()
    assert db.scalars(select(Transaction)).all() == []
    assert db.scalars(select(Obligation)).all() == []
    assert db.scalars(select(Account)).all() == []
