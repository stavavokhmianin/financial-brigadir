"""Качество данных (раздел 13.2): что показать рядом с любым числом."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Account, DataSource, Transaction, User
from app.domain.enums import AccountType, Coverage, DataSourceKind
from app.schemas.common import DataQuality

STALE_AFTER = timedelta(days=3)


def data_quality(db: Session, user: User, now: datetime | None = None) -> DataQuality:
    now = now or datetime.now(UTC)
    accounts = db.scalars(
        select(Account).where(Account.user_id == user.id, Account.archived.is_(False))
    ).all()
    source_ids = {a.source_id for a in accounts if a.source_id}
    sources = (
        db.scalars(select(DataSource).where(DataSource.id.in_(source_ids))).all()
        if source_ids
        else []
    )

    notes: list[str] = []
    if not accounts:
        notes.append("Нет ни одного счёта: добавьте счёт и остаток вручную или загрузите выписку.")
    freshness = [s.data_as_of for s in sources if s.data_as_of is not None]
    manual_dates = [a.updated_at for a in accounts if a.source_id is None]
    data_as_of = min(freshness + manual_dates, default=None)
    history_starts = [s.history_from for s in sources if s.history_from is not None]
    history_days = (
        (data_as_of.date() - min(history_starts)).days if data_as_of and history_starts else 0
    )

    if any(s.is_partial for s in sources):
        coverage = Coverage.PARTIAL
        notes.append("В выписке есть пропуски: часть операций может отсутствовать.")
    elif sources and all(s.kind == DataSourceKind.SYNTHETIC for s in sources):
        coverage = Coverage.FULL
    else:
        coverage = Coverage.UNKNOWN
        notes.append(
            "Прогноз строится по указанным счетам. Обязательства в других банках "
            "добавьте вручную — неизвестные средства не считаются нулём."
        )
    if accounts and len({a.bank_name for a in accounts}) == 1 and coverage != Coverage.FULL:
        notes.append("Подключён один банк: это прогноз по выбранному счёту, а не общий.")
    if history_days < 60:
        notes.append("История короче 60 дней: диапазоны прогноза будут шире.")
    pending = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.duplicate_candidate_id.is_not(None),
            Transaction.duplicate_of_id.is_(None),
            Transaction.needs_review.is_(True),
        )
    )
    if pending:
        notes.append(f"Найдены вероятные дубли операций: {pending} — проверьте их.")
    if any(a.type == AccountType.CREDIT_CARD for a in accounts):
        notes.append("Кредитный лимит не считается свободными деньгами.")

    stale = bool(not user.is_demo and data_as_of and now - data_as_of > STALE_AFTER)
    if stale:
        notes.append("Данные устарели: обновите выписку перед прогнозом.")
    if user.is_demo:
        notes.append("Демо-профиль на синтетических данных.")
    return DataQuality(
        coverage=coverage,
        data_as_of=data_as_of,
        history_days=history_days,
        stale=stale,
        is_demo=user.is_demo,
        notes=notes,
    )
