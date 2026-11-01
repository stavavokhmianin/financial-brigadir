from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses, not_found
from app.db.models import Account, AuditEvent, DataSource, User
from app.domain.enums import AccountType, DataSourceKind
from app.domain.ids import new_id
from app.modules.plans import ensure_account_capacity, lock_profile
from app.modules.quality import data_quality
from app.schemas.accounts import AccountCreate, AccountOut, AccountPatch, AccountsOut
from financial_sdk import AccountSnapshot, liquid_balance_minor

router = APIRouter(prefix="/accounts", tags=["accounts"])

_NOT_LIQUID_BY_DEFAULT = {AccountType.CREDIT_CARD, AccountType.DEPOSIT}


def _snapshot(account: Account) -> AccountSnapshot:
    return AccountSnapshot(
        id=account.id,
        type=account.type,
        currency=account.currency,
        balance_minor=account.available_balance_minor,
        data_as_of=account.updated_at,
        is_liquid=account.is_liquid,
        credit_limit_minor=account.credit_limit_minor,
        blocked_minor=account.blocked_minor,
    )


@router.get(
    "",
    operation_id="listAccounts",
    summary="Счета пользователя, свободные средства и свежесть источников",
    responses=error_responses(401, 403),
)
def list_accounts(user: CurrentUser, db: DbSession) -> AccountsOut:
    accounts = db.scalars(
        select(Account)
        .where(Account.user_id == user.id, Account.archived.is_(False))
        .options(selectinload(Account.source))
        .order_by(Account.is_liquid.desc(), Account.name, Account.id)
    ).all()
    return AccountsOut(
        items=[AccountOut.model_validate(a) for a in accounts],
        liquid_balance_minor=liquid_balance_minor(_snapshot(a) for a in accounts),
        data_quality=data_quality(db, user),
    )


def _manual_source(db: DbSession, user: User) -> DataSource:
    source = db.scalars(
        select(DataSource).where(
            DataSource.user_id == user.id, DataSource.kind == DataSourceKind.MANUAL
        )
    ).first()
    if source is None:
        source = DataSource(
            id=new_id("src"), user_id=user.id, kind=DataSourceKind.MANUAL, label="Ручной ввод"
        )
        db.add(source)
        db.flush()
    return source


@router.post(
    "",
    operation_id="createAccount",
    summary="Ручное создание счёта и стартового остатка (FR-03)",
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 403),
)
def create_account(body: AccountCreate, user: CurrentUser, db: DbSession) -> AccountOut:
    user = lock_profile(db, user)
    ensure_account_capacity(db, user)
    now = datetime.now(UTC)
    source = _manual_source(db, user)
    source.data_as_of = now
    is_liquid = body.is_liquid
    if is_liquid is None:
        is_liquid = body.type not in _NOT_LIQUID_BY_DEFAULT
    account = Account(
        id=new_id("acc"),
        user_id=user.id,
        source_id=source.id,
        name=body.name,
        bank_name=body.bank_name,
        type=body.type,
        currency=body.currency,
        available_balance_minor=body.available_balance_minor,
        credit_limit_minor=body.credit_limit_minor,
        blocked_minor=0,
        is_liquid=is_liquid,
        updated_at=now,
    )
    db.add(account)
    db.add(
        AuditEvent(
            user_id=user.id, action="account_created", object_type="account", object_id=account.id
        )
    )
    db.commit()
    db.refresh(account)
    return AccountOut.model_validate(account)


@router.patch(
    "/{account_id}",
    operation_id="updateAccount",
    summary="Обновить остаток или название счёта вручную",
    responses=error_responses(400, 401, 404),
)
def update_account(
    account_id: str, body: AccountPatch, user: CurrentUser, db: DbSession
) -> AccountOut:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise not_found("Счёт")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(account, field, value)
    if account.type == AccountType.CREDIT_CARD and account.is_liquid:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "credit_not_liquid",
            "Кредитный лимит не является свободными средствами",
        )
    if account.type != AccountType.CREDIT_CARD and account.credit_limit_minor is not None:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "limit_only_for_credit",
            "credit_limit_minor допустим только для кредитной карты",
        )
    if "available_balance_minor" in changes or "blocked_minor" in changes:
        account.updated_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            user_id=user.id,
            action="account_updated",
            object_type="account",
            object_id=account.id,
            meta={"fields": sorted(changes)},
        )
    )
    db.commit()
    db.refresh(account)
    return AccountOut.model_validate(account)
