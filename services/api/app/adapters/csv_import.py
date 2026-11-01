"""CsvImportAdapter (раздел 7.1–7.2, FR-02): разбор выписки в единый формат 8.2.

Адаптер не пишет в БД: он возвращает нормализованные строки, проблемы по
строкам и сопоставление колонок. Неизвестные или конфликтующие значения не
исправляются молча — строка отклоняется с понятной причиной.
"""

import csv
import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from financial_sdk import parse_rub_to_minor

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 20_000
PREVIEW_ROWS = 10

# Каноническое поле → допустимые заголовки (в нижнем регистре, без кавычек).
HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "date": ("date", "дата", "дата операции", "дата транзакции", "operation date",
             "transaction date", "occurred_at"),
    "booked_at": ("booked_at", "дата списания", "дата проводки", "дата обработки",
                  "booking date"),
    "amount": ("amount", "сумма", "сумма операции", "сумма в валюте счёта",
               "сумма в валюте счета", "amount_rub"),
    "currency": ("currency", "валюта", "валюта операции"),
    "description": ("description", "описание", "назначение", "назначение платежа",
                    "комментарий", "получатель", "merchant"),
    "category": ("category", "категория"),
    "status": ("status", "статус"),
    "external_id": ("external_id", "id", "номер", "номер операции", "идентификатор"),
    "direction": ("direction", "направление", "тип операции", "тип"),
}  # fmt: skip
REQUIRED = ("date", "amount")

STATUS_MAP = {
    "posted": "posted", "ok": "posted", "success": "posted", "исполнено": "posted",
    "выполнено": "posted", "проведено": "posted", "успешно": "posted",
    "pending": "pending", "hold": "pending", "холд": "pending", "в обработке": "pending",
    "canceled": "canceled", "cancelled": "canceled", "declined": "canceled",
    "отменено": "canceled", "отклонено": "canceled",
}  # fmt: skip
OUTFLOW_WORDS = ("списание", "расход", "debit", "out", "покупка", "оплата")
INFLOW_WORDS = ("зачисление", "приход", "поступление", "credit", "in", "пополнение")

# Правила категоризации (FR-10): ключевые слова в описании → категория.
CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("salary", ("зарплата", "заработная плата", "аванс", "salary")),
    ("rent", ("аренда", "наём", "найм")),
    ("utilities", ("жкх", "коммунал", "электроэнерг", "водоканал")),
    ("groceries", ("супермаркет", "продукты", "пятёрочка", "пятерочка", "перекрёсток",
                   "перекресток", "магнит", "вкусвилл", "лента")),
    ("cafe", ("кафе", "ресторан", "кофе", "coffee", "бургер")),
    ("taxi", ("такси", "taxi")),
    ("transport", ("метро", "транспорт", "автобус", "тройка")),
    ("pharmacy", ("аптека",)),
    ("marketplace", ("ozon", "озон", "wildberries", "вайлдберриз", "маркетплейс")),
    ("subscription", ("подписка", "subscription")),
)  # fmt: skip
OWN_TRANSFER_WORDS = ("между своими", "собственный счёт", "собственный счет", "own transfer")
CARD_PAYMENT_WORDS = ("погашение кредитной карты", "погашение задолженности по карте")
REFUND_WORDS = ("возврат", "refund")

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


class _Semicolon(csv.excel):
    delimiter = ";"


class CsvFormatError(ValueError):
    """Файл нельзя разобрать целиком (кодировка, нет обязательных колонок, пустой)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Issue:
    row: int
    column: str | None
    code: str
    message: str


@dataclass
class ParsedCsv:
    fingerprint: str
    column_mapping: dict[str, str]
    rows_total: int
    records: list[dict[str, Any]] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    preview: list[dict[str, str]] = field(default_factory=list)

    @property
    def rows_rejected(self) -> int:
        return self.rows_total - len(self.records)


def fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sanitize_text(value: str | None, limit: int = 255) -> str | None:
    """Обрезка и защита от CSV-формул при последующей выгрузке в таблицы (раздел 25)."""
    if value is None:
        return None
    text = " ".join(value.split())[:limit]
    if not text:
        return None
    if text.startswith(_FORMULA_PREFIXES):
        text = "'" + text[: limit - 1]
    return text


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CsvFormatError("bad_encoding", "Не удалось определить кодировку (ожидается UTF-8)")


def _normalize_header(name: str) -> str:
    return " ".join(name.strip().strip('"').strip("'").lower().replace("ё", "е").split())


def map_columns(headers: list[str]) -> dict[str, str]:
    """Каноническое поле → заголовок файла."""
    normalized = {_normalize_header(h): h for h in headers if h and h.strip()}
    mapping: dict[str, str] = {}
    for canonical, synonyms in HEADER_SYNONYMS.items():
        for synonym in synonyms:
            key = _normalize_header(synonym)
            if key in normalized and normalized[key] not in mapping.values():
                mapping[canonical] = normalized[key]
                break
    return mapping


def _parse_moment(raw: str, tz: ZoneInfo) -> datetime:
    value = raw.strip()
    if not value:
        raise ValueError("пустая дата")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            # Только дата — середина дня, чтобы сдвиг в UTC не менял календарный день.
            if len(value) <= 10:
                parsed = datetime.combine(parsed.date(), time(12, 0))
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(UTC)
    date_part, _, time_part = value.partition(" ")
    day: date | None = None
    for fmt in _DATE_FORMATS:
        try:
            day = datetime.strptime(date_part, fmt).date()  # noqa: DTZ007 — tz ставится ниже
            break
        except ValueError:
            continue
    if day is None:
        raise ValueError(f"неизвестный формат даты: {value!r}")
    moment = time(12, 0)
    if time_part:
        match = _TIME_RE.match(time_part.strip())
        if not match:
            raise ValueError(f"неизвестный формат времени: {time_part!r}")
        moment = time(int(match[1]), int(match[2]), int(match[3] or 0))
    return datetime.combine(day, moment, tz).astimezone(UTC)


def _categorize(description: str | None) -> str | None:
    if not description:
        return None
    text = description.lower().replace("ё", "е")
    for category, words in CATEGORY_RULES:
        if any(word.replace("ё", "е") in text for word in words):
            return category
    return None


def _contains(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _infer_type(amount: int, description: str, category: str | None) -> str:
    """Экономический тип (FR-09). Неоднозначные переводы помечаются на проверку."""
    if _contains(description, OWN_TRANSFER_WORDS):
        return "transfer_in" if amount > 0 else "transfer_out"
    if amount < 0 and _contains(description, CARD_PAYMENT_WORDS):
        return "credit_payment"
    if amount > 0 and _contains(description, REFUND_WORDS):
        return "refund"
    return "income" if amount > 0 else "expense"


def parse_csv(raw: bytes, timezone: str, account_id: str) -> ParsedCsv:
    """Разбирает файл; бросает ``CsvFormatError``, если файл непригоден целиком."""
    if not raw.strip():
        raise CsvFormatError("empty_file", "Файл пустой")
    text = _decode(raw)
    sample = text[:4096]
    dialect: type[csv.Dialect]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = _Semicolon if sample.count(";") >= sample.count(",") else csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = list(reader.fieldnames or [])
    mapping = map_columns(headers)
    missing = [c for c in REQUIRED if c not in mapping]
    if missing:
        names = ", ".join(missing)
        raise CsvFormatError(
            "missing_columns", f"Нет обязательных колонок: {names}. Найдены: {', '.join(headers)}"
        )

    tz = ZoneInfo(timezone)
    result = ParsedCsv(fingerprint=fingerprint(raw), column_mapping=mapping, rows_total=0)
    occurrences: Counter[tuple[str, int, str]] = Counter()

    def cell(row: dict[str, str | None], canonical: str) -> str:
        column = mapping.get(canonical)
        return (row.get(column) or "").strip() if column else ""

    for index, row in enumerate(reader, start=2):  # строка 1 — заголовок
        if not any((value or "").strip() for value in row.values()):
            continue
        result.rows_total += 1
        if result.rows_total > MAX_ROWS:
            raise CsvFormatError("too_many_rows", f"Больше {MAX_ROWS} строк — разбейте файл")
        try:
            occurred_at = _parse_moment(cell(row, "date"), tz)
        except ValueError as exc:
            result.issues.append(Issue(index, mapping["date"], "bad_date", str(exc)))
            continue
        booked_raw = cell(row, "booked_at")
        try:
            booked_at = _parse_moment(booked_raw, tz) if booked_raw else None
        except ValueError as exc:
            result.issues.append(Issue(index, mapping.get("booked_at"), "bad_date", str(exc)))
            continue
        try:
            amount = parse_rub_to_minor(cell(row, "amount"))
        except ValueError as exc:
            result.issues.append(Issue(index, mapping["amount"], "bad_amount", str(exc)))
            continue
        if amount == 0:
            result.issues.append(Issue(index, mapping["amount"], "zero_amount", "Нулевая сумма"))
            continue
        direction = cell(row, "direction").lower()
        if direction and amount > 0:
            if any(word == direction or direction.startswith(word) for word in OUTFLOW_WORDS):
                amount = -amount
            elif not any(direction.startswith(word) for word in INFLOW_WORDS):
                result.issues.append(
                    Issue(index, mapping.get("direction"), "bad_direction",
                          f"Непонятное направление операции: {direction!r}")
                )  # fmt: skip
                continue
        currency = cell(row, "currency").upper() or "RUB"
        if currency in ("RUR", "₽", "РУБ", "РУБ."):
            currency = "RUB"
        if currency != "RUB":
            result.issues.append(
                Issue(index, mapping.get("currency"), "unsupported_currency",
                      f"Валюта {currency} пока не поддерживается (MVP — только RUB)")
            )  # fmt: skip
            continue
        status_raw = cell(row, "status").lower()
        status = STATUS_MAP.get(status_raw, "posted" if not status_raw else "")
        if not status:
            result.issues.append(
                Issue(index, mapping.get("status"), "bad_status",
                      f"Неизвестный статус: {status_raw!r}")
            )  # fmt: skip
            continue

        description = sanitize_text(cell(row, "description"))
        category = sanitize_text(cell(row, "category"), 64)
        category_source = "source"
        if category is None:
            category = _categorize(description)
            category_source = "rule"
        external_id = cell(row, "external_id")
        if not external_id:
            # Стабильный id: одинаковые строки внутри файла различаются порядковым номером,
            # поэтому та же выписка или пересекающийся период не создают дублей.
            key = (occurred_at.isoformat(), amount, description or "")
            occurrences[key] += 1
            digest = hashlib.sha1(  # noqa: S324 — не криптография, только идентификатор
                f"{key[0]}|{key[1]}|{key[2]}|{occurrences[key]}".encode()
            ).hexdigest()
            external_id = f"csv-{digest[:20]}"
        tx_type = _infer_type(amount, description or "", category)
        record = {
            "account_id": account_id,
            "external_id": sanitize_text(external_id, 80) or external_id[:80],
            "occurred_at": occurred_at.isoformat(),
            "booked_at": booked_at.isoformat() if booked_at else None,
            "amount_minor": amount,
            "currency": "RUB",
            "type": tx_type,
            "status": status,
            "category": category,
            "category_source": category_source,
            "description": description,
        }
        result.records.append(record)
        if len(result.preview) < PREVIEW_ROWS:
            result.preview.append(
                {
                    "row": str(index),
                    "occurred_at": occurred_at.isoformat(),
                    "amount_minor": str(amount),
                    "type": tx_type,
                    "status": status,
                    "category": category or "",
                    "description": description or "",
                }
            )
    return result
