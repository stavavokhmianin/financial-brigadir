"""Демо-сессия (FR-01): изолированный профиль из seed без регистрации и банковских данных."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.adapters.synthetic import SyntheticDataAdapter
from app.core.security import hash_token, new_session_token
from app.db.models import (
    Account,
    AuditEvent,
    AuthSession,
    DataSource,
    IncomeEvent,
    NotificationSettings,
    Obligation,
    User,
)
from app.domain.enums import (
    AccountType,
    DataSourceKind,
    IncomeKind,
    ObligationKind,
    ObligationStatus,
    Priority,
    Recurrence,
)
from app.domain.ids import new_id
from app.modules.dedup import detect_duplicates
from app.modules.ledger import ingest_transactions

DEFAULT_RESERVE_MINOR = 500_000  # 5 000 ₽ — резерв по умолчанию для демо (раздел 9.6)
DEFAULT_ALPHA = 0.05  # допустимый риск для «безопасной суммы» (раздел 9.4)


@dataclass(frozen=True)
class DemoSessionResult:
    token: str
    expires_at: datetime
    user: User
    profile: dict[str, object]
    accounts: int
    transactions: int
    obligations: int
    incomes: int
    duplicates_skipped: int


def create_demo_session(
    db: Session,
    adapter: SyntheticDataAdapter,
    profile_id: str,
    seed: int,
    ttl_hours: int,
) -> DemoSessionResult:
    bundle = adapter.load(profile_id, seed)
    user = User(
        id=new_id("usr"),
        is_demo=True,
        demo_profile=profile_id,
        demo_seed=seed,
        timezone=str(bundle.profile["timezone"]),
        risk_preferences={"reserve_minor": DEFAULT_RESERVE_MINOR, "alpha": DEFAULT_ALPHA},
        consent_versions={"demo_terms": "2026-10-19"},
    )
    db.add(user)
    db.flush()

    source = DataSource(
        id=new_id("src"),
        user_id=user.id,
        kind=DataSourceKind.SYNTHETIC,
        label=f"Демо: {bundle.profile['title']}",
        data_as_of=bundle.as_of,
        history_from=bundle.history_from,
        history_to=bundle.as_of.date(),
        is_partial=any(a["is_partial"] for a in bundle.accounts),
    )
    db.add(source)
    db.add(NotificationSettings(user_id=user.id))
    db.flush()

    account_ids: dict[str, str] = {}
    for item in bundle.accounts:
        account = Account(
            id=new_id("acc"),
            user_id=user.id,
            source_id=source.id,
            external_id=item["account_id"],
            name=item["name"],
            bank_name=item["bank_name"],
            type=AccountType(item["type"]),
            currency=item["currency"],
            available_balance_minor=item["balance_minor"],
            credit_limit_minor=item["credit_limit_minor"],
            blocked_minor=item["blocked_minor"],
            is_liquid=item["is_liquid"],
            updated_at=datetime.fromisoformat(item["data_as_of"]),
        )
        db.add(account)
        account_ids[item["account_id"]] = account.id
    db.flush()

    inserted, _ = ingest_transactions(db, user, source, account_ids, bundle.transactions)
    # Повторная выгрузка выписки из профиля проверяет идемпотентность прямо при создании.
    _, duplicates = ingest_transactions(db, user, source, account_ids, bundle.reupload)
    detect_duplicates(db, user)

    for item in bundle.obligations:
        db.add(
            Obligation(
                id=new_id("obl"),
                user_id=user.id,
                account_id=account_ids.get(item["account_id"]),
                source_id=source.id,
                kind=ObligationKind(item["kind"]),
                title=item["title"],
                amount_minor=item["amount_minor"],
                amount_min_minor=item["amount_min_minor"],
                amount_max_minor=item["amount_max_minor"],
                due_date=date.fromisoformat(item["due_date"]),
                recurrence=Recurrence(item["recurrence"]),
                recurrence_day=item["recurrence_day"],
                priority=Priority(item["priority"]),
                status=ObligationStatus(item["status"]),
                confidence=item["confidence"],
                movable=item["movable"],
            )
        )
    for item in bundle.incomes:
        db.add(
            IncomeEvent(
                id=new_id("inc"),
                user_id=user.id,
                account_id=account_ids.get(item["account_id"]),
                source_id=source.id,
                kind=IncomeKind(item["kind"]),
                title=item["title"],
                date_from=date.fromisoformat(item["date_from"]),
                date_to=date.fromisoformat(item["date_to"]),
                amount_min_minor=item["amount_min_minor"],
                amount_max_minor=item["amount_max_minor"],
                probability=item["probability"],
                confirmed=item["confirmed"],
                recurrence=Recurrence(item["recurrence"]),
            )
        )

    token = new_session_token()
    expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)
    db.add(
        AuthSession(
            id=new_id("ses"),
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
    )
    db.add(
        AuditEvent(
            user_id=user.id,
            action="demo_session_created",
            object_type="user",
            object_id=user.id,
            meta={"profile": profile_id, "seed": seed},
        )
    )
    db.commit()
    return DemoSessionResult(
        token=token,
        expires_at=expires_at,
        user=user,
        profile=bundle.profile,
        accounts=len(account_ids),
        transactions=inserted,
        obligations=len(bundle.obligations),
        incomes=len(bundle.incomes),
        duplicates_skipped=duplicates,
    )
