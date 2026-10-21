"""Synthetic bank consent and synchronization; no real banking integration."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from anyio.from_thread import run as run_on_loop
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.adapters.bank import ConsentToken, SourceAccount, SourceBalance
from app.adapters.bank_mock import BankAccessError, BankMockConnector, BankNetworkError
from app.api.deps import CurrentUser, DbSession, demo_only
from app.core.errors import APIError, error_responses
from app.db.models import Account, AuditEvent, BankConsent, DataSource
from app.domain.enums import AccountType, DataSourceKind
from app.domain.ids import new_id
from app.modules.dedup import detect_duplicates
from app.modules.ledger import ingest_transactions
from app.modules.plans import ensure_account_capacity, lock_profile
from app.schemas.bank_mock import (
    BankConsentOut,
    BankConsentRequest,
    BankMockSyncOut,
    BankMockSyncRequest,
)

router = APIRouter(
    prefix="/connectors/bank-mock", tags=["connectors"], dependencies=[Depends(demo_only)]
)


def _token(consent: BankConsent) -> ConsentToken:
    return ConsentToken(consent.id, tuple(consent.scopes), consent.expires_at)


async def _fetch(
    connector: BankMockConnector, consent: ConsentToken
) -> tuple[list[SourceAccount], dict[str, SourceBalance], list[dict[str, Any]], bool]:
    accounts = await connector.list_accounts(consent)
    balances = {a.external_id: await connector.get_balances(a.external_id) for a in accounts}
    records: list[dict[str, Any]] = []
    partial = False
    for account in accounts:
        cursor = None
        while True:
            page = await connector.list_transactions(
                account.external_id,
                connector.bundle.history_from,
                connector.as_of.date(),
                cursor,
            )
            partial = partial or page.is_partial
            for item in page.items:
                record = asdict(item)
                record["account_id"] = account.external_id
                record["occurred_at"] = item.occurred_at.isoformat()
                record["booked_at"] = item.booked_at.isoformat() if item.booked_at else None
                records.append(record)
            cursor = page.next_cursor
            if cursor is None:
                break
    return accounts, balances, records, partial


@router.get("/consent", operation_id="getBankMockConsent", responses=error_responses(401))
def get_consent(user: CurrentUser, db: DbSession) -> BankConsentOut | None:
    consent = db.get(BankConsent, user.id)
    return BankConsentOut.model_validate(consent) if consent else None


@router.post("/consent", operation_id="grantBankMockConsent", responses=error_responses(401))
def grant_consent(body: BankConsentRequest, user: CurrentUser, db: DbSession) -> BankConsentOut:
    consent = db.scalar(select(BankConsent).where(BankConsent.user_id == user.id).with_for_update())
    if consent is None:
        consent = BankConsent(user_id=user.id)
        db.add(consent)
    consent.id = new_id("con")
    consent.scopes = sorted(set(body.scopes))
    consent.created_at = datetime.now(UTC)
    consent.expires_at = consent.created_at + timedelta(hours=body.ttl_hours)
    consent.revoked_at = None
    db.add(
        AuditEvent(
            user_id=user.id, action="bank_mock_consent_granted", meta={"scopes": consent.scopes}
        )
    )
    db.commit()
    return BankConsentOut.model_validate(consent)


@router.delete(
    "/consent",
    operation_id="revokeBankMockConsent",
    status_code=204,
    responses=error_responses(401),
)
def revoke_consent(user: CurrentUser, db: DbSession) -> Response:
    consent = db.scalar(select(BankConsent).where(BankConsent.user_id == user.id).with_for_update())
    if consent:
        run_on_loop(BankMockConnector(_token(consent)).revoke_access, _token(consent))
        consent.revoked_at = datetime.now(UTC)
        db.add(AuditEvent(user_id=user.id, action="bank_mock_consent_revoked"))
        db.commit()
    return Response(status_code=204)


@router.post(
    "/sync",
    operation_id="syncBankMock",
    summary="Мок банка: только синтетические данные",
    responses=error_responses(401, 403, 409, 503),
)
def sync_bank_mock(body: BankMockSyncRequest, user: CurrentUser, db: DbSession) -> BankMockSyncOut:
    user = lock_profile(db, user)
    # PostgreSQL serializes sync/revoke/renew on the same consent row.
    consent = db.scalar(select(BankConsent).where(BankConsent.user_id == user.id).with_for_update())
    if consent is None or consent.revoked_at is not None:
        raise APIError(403, "consent_required", "Разрешите доступ к синтетическим данным мока.")
    connector = BankMockConnector(_token(consent), body.scenario)
    try:
        # Обработчик синхронный (БД блокирующая), чтение коннектора — в event loop.
        accounts, balances, records, partial = run_on_loop(_fetch, connector, _token(consent))
    except BankAccessError as exc:
        raise APIError(
            403, "consent_unavailable", "Согласие истекло или не хватает разрешений."
        ) from exc
    except BankNetworkError as exc:
        raise APIError(
            503,
            "bank_unavailable",
            "Учебный банк временно недоступен. Повторите синхронизацию.",
            headers={"Retry-After": "1"},
        ) from exc

    source = db.get(DataSource, consent.source_id) if consent.source_id else None
    if source and source.data_as_of and connector.as_of < source.data_as_of:
        raise APIError(409, "stale_bank_snapshot", "Ответ банка старее уже сохранённых данных.")
    existing_ids = (
        set(
            db.scalars(
                select(Account.external_id).where(
                    Account.user_id == user.id,
                    Account.source_id == source.id,
                )
            )
        )
        if source
        else set()
    )
    ensure_account_capacity(db, user, sum(a.external_id not in existing_ids for a in accounts))
    if source is None:
        source = DataSource(
            id=new_id("src"),
            user_id=user.id,
            kind=DataSourceKind.BANK_MOCK,
            label="Учебный банк — синтетика",
        )
        db.add(source)
        db.flush()
        consent.source_id = source.id
    account_ids: dict[str, str] = {}
    for remote in accounts:
        local_account = db.scalar(
            select(Account).where(
                Account.user_id == user.id,
                Account.source_id == source.id,
                Account.external_id == remote.external_id,
            )
        )
        if local_account is None:
            local_account = Account(
                id=new_id("acc"),
                user_id=user.id,
                source_id=source.id,
                external_id=remote.external_id,
                name=remote.name,
                bank_name="Учебный банк",
                type=AccountType(remote.type),
                currency=remote.currency,
                is_liquid=True,
            )
            db.add(local_account)
        balance = balances[remote.external_id]
        local_account.available_balance_minor = balance.available_minor
        local_account.blocked_minor = balance.blocked_minor
        local_account.updated_at = balance.as_of
        account_ids[remote.external_id] = local_account.id
    db.flush()
    inserted, duplicates = ingest_transactions(db, user, source, account_ids, records)
    detect_duplicates(db, user)
    source.data_as_of = connector.as_of
    source.history_from = connector.bundle.history_from
    source.history_to = connector.as_of.date()
    source.is_partial = partial
    db.add(
        AuditEvent(
            user_id=user.id,
            action="bank_mock_synced",
            object_type="data_source",
            object_id=source.id,
            meta={"new": inserted, "duplicates": duplicates, "partial": partial},
        )
    )
    db.commit()
    return BankMockSyncOut(
        status="partial" if partial else "synced",
        accounts_seen=len(accounts),
        transactions_new=inserted,
        transactions_duplicate=duplicates,
        data_as_of=connector.as_of,
        message="Загружена синтетика учебного банка. Реального подключения нет.",
    )
