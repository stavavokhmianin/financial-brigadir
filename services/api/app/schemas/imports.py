from datetime import date

from pydantic import Field

from app.domain.enums import ImportStatus
from app.schemas.common import APIModel


class ImportIssue(APIModel):
    row: int = Field(description="Номер строки файла (1 — заголовок)")
    column: str | None
    code: str
    message: str


class ImportResultOut(APIModel):
    import_id: str | None = Field(description="null для предпросмотра")
    account_id: str
    status: ImportStatus
    fingerprint: str = Field(description="SHA-256 файла: повторная загрузка идемпотентна")
    already_imported: bool = Field(description="Этот файл или ключ уже импортирован раньше")
    rows_total: int
    rows_imported: int
    rows_duplicate: int = Field(description="Строки, уже известные по external_id")
    rows_rejected: int
    period_from: date | None
    period_to: date | None
    column_mapping: dict[str, str] = Field(description="Поле → заголовок файла")
    preview: list[dict[str, str]] = Field(description="Первые 10 нормализованных строк")
    issues: list[ImportIssue]
