from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, Header, Response, UploadFile, status
from sqlalchemy import select

from app.adapters.csv_import import MAX_BYTES, CsvFormatError, ParsedCsv, fingerprint, parse_csv
from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError, error_responses, not_found
from app.db.models import Account, AuditEvent, DataSource, ImportBatch, User
from app.domain.enums import DataSourceKind, ImportStatus
from app.domain.ids import new_id
from app.modules.dedup import detect_duplicates
from app.modules.ledger import ingest_transactions
from app.schemas.imports import ImportIssue, ImportResultOut

router = APIRouter(prefix="/imports", tags=["imports"])

IdempotencyKey = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        max_length=80,
        description="Повтор запроса с тем же ключом вернёт тот же результат",
    ),
]

MAX_ISSUES = 50


def _issues(parsed: ParsedCsv) -> list[ImportIssue]:
    return [
        ImportIssue(row=i.row, column=i.column, code=i.code, message=i.message)
        for i in parsed.issues[:MAX_ISSUES]
    ]


def _period(records: list[dict[str, Any]]) -> tuple[date | None, date | None]:
    days = [datetime.fromisoformat(r["occurred_at"]).date() for r in records]
    return (min(days), max(days)) if days else (None, None)


def _from_batch(batch: ImportBatch, account_id: str) -> ImportResultOut:
    source = batch.source
    return ImportResultOut(
        import_id=batch.id,
        account_id=account_id,
        status=batch.status,
        fingerprint=batch.fingerprint,
        already_imported=True,
        rows_total=batch.rows_total,
        rows_imported=batch.rows_imported,
        rows_duplicate=batch.rows_duplicate,
        rows_rejected=batch.rows_rejected,
        period_from=source.history_from if source else None,
        period_to=source.history_to if source else None,
        column_mapping={},
        preview=[],
        issues=[],
    )


def _csv_source(db: DbSession, user: User, account: Account) -> DataSource:
    label = f"CSV · {account.name}"[:120]
    source = db.scalars(
        select(DataSource).where(
            DataSource.user_id == user.id,
            DataSource.kind == DataSourceKind.CSV,
            DataSource.label == label,
        )
    ).first()
    if source is None:
        source = DataSource(id=new_id("src"), user_id=user.id, kind=DataSourceKind.CSV, label=label)
        db.add(source)
        db.flush()
    return source


@router.post(
    "/csv",
    operation_id="importCsv",
    summary="Предпросмотр и импорт CSV-выписки; идемпотентно по fingerprint и Idempotency-Key",
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": ImportResultOut, "description": "Предпросмотр или повтор импорта"},
        **error_responses(400, 401, 404, 409, 413),
    },
)
def import_csv(
    response: Response,
    user: CurrentUser,
    db: DbSession,
    account_id: Annotated[str, Form(description="Счёт, к которому относится выписка")],
    mode: Annotated[Literal["preview", "import"], Form()] = "preview",
    file: Annotated[UploadFile | None, File(description="CSV-файл до 2 МБ")] = None,
    content: Annotated[
        str | None, Form(description="Текст CSV вместо файла", max_length=MAX_BYTES)
    ] = None,
    idempotency_key: IdempotencyKey = None,
) -> ImportResultOut:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise not_found("Счёт")
    if (file is None) == (content is None):
        raise APIError(
            status.HTTP_400_BAD_REQUEST, "need_file_or_content", "Передайте file или content"
        )
    raw = file.file.read(MAX_BYTES + 1) if file is not None else (content or "").encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise APIError(413, "file_too_large", "Файл больше 2 МБ — разбейте его")
    # Scope the fingerprint to its destination; the same bytes can belong to two accounts.
    digest = fingerprint(account.id.encode("utf-8") + b"\x00" + raw)

    if mode == "import":
        previous = None
        if idempotency_key:
            previous = db.scalars(
                select(ImportBatch).where(
                    ImportBatch.user_id == user.id, ImportBatch.idempotency_key == idempotency_key
                )
            ).first()
            if previous is not None and previous.fingerprint != digest:
                raise APIError(
                    status.HTTP_409_CONFLICT,
                    "idempotency_conflict",
                    "Этот Idempotency-Key уже использован для другого файла",
                )
        if previous is None:
            previous = db.scalars(
                select(ImportBatch).where(
                    ImportBatch.user_id == user.id, ImportBatch.fingerprint == digest
                )
            ).first()
        if previous is not None:
            response.status_code = status.HTTP_200_OK
            return _from_batch(previous, account.id)

    try:
        parsed = parse_csv(raw, user.timezone, account.id)
    except CsvFormatError as exc:
        raise APIError(status.HTTP_400_BAD_REQUEST, exc.code, exc.message) from exc
    period_from, period_to = _period(parsed.records)

    if mode == "preview":
        response.status_code = status.HTTP_200_OK
        return ImportResultOut(
            import_id=None,
            account_id=account.id,
            status=ImportStatus.PREVIEW,
            fingerprint=digest,
            already_imported=False,
            rows_total=parsed.rows_total,
            rows_imported=0,
            rows_duplicate=0,
            rows_rejected=parsed.rows_rejected,
            period_from=period_from,
            period_to=period_to,
            column_mapping=parsed.column_mapping,
            preview=parsed.preview,
            issues=_issues(parsed),
        )

    if not parsed.records:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "no_valid_rows",
            "В файле нет ни одной корректной строки",
            details={"issues": [i.model_dump() for i in _issues(parsed)]},
        )
    source = _csv_source(db, user, account)
    # An invalid subset is a gap, not a complete statement. Keep the flag until
    # completeness can be independently established; another file alone cannot prove it.
    source.is_partial = source.is_partial or parsed.rows_rejected > 0
    batch = ImportBatch(
        id=new_id("imp"),
        user_id=user.id,
        source_id=source.id,
        fingerprint=digest,
        idempotency_key=idempotency_key,
        filename=(file.filename or None) if file is not None else None,
        status=ImportStatus.IMPORTED,
        rows_total=parsed.rows_total,
        rows_rejected=parsed.rows_rejected,
    )
    db.add(batch)
    db.flush()
    inserted, duplicates = ingest_transactions(
        db, user, source, {account.id: account.id}, parsed.records, import_batch_id=batch.id
    )
    detect_duplicates(db, user)
    batch.rows_imported = inserted
    batch.rows_duplicate = duplicates
    latest = max(datetime.fromisoformat(r["occurred_at"]) for r in parsed.records)
    if source.data_as_of is None or latest > source.data_as_of:
        source.data_as_of = latest
    if period_from and (source.history_from is None or period_from < source.history_from):
        source.history_from = period_from
    if period_to and (source.history_to is None or period_to > source.history_to):
        source.history_to = period_to
    db.add(
        AuditEvent(
            user_id=user.id,
            action="csv_imported",
            object_type="import_batch",
            object_id=batch.id,
            meta={"rows": parsed.rows_total, "imported": inserted, "duplicates": duplicates},
        )
    )
    db.commit()
    return ImportResultOut(
        import_id=batch.id,
        account_id=account.id,
        status=ImportStatus.IMPORTED,
        fingerprint=digest,
        already_imported=False,
        rows_total=parsed.rows_total,
        rows_imported=inserted,
        rows_duplicate=duplicates,
        rows_rejected=parsed.rows_rejected,
        period_from=period_from,
        period_to=period_to,
        column_mapping=parsed.column_mapping,
        preview=parsed.preview,
        issues=_issues(parsed),
    )
