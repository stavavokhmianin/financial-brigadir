from pathlib import Path

import pytest

from app.adapters.csv_import import CsvFormatError, ParsedCsv, parse_csv, sanitize_text

TEMPLATE = (
    Path(__file__).resolve().parents[3] / "packages" / "api_contracts" / "examples"
    / "statement-template.csv"
)  # fmt: skip
TZ = "Europe/Moscow"


def _parse(text: str, encoding: str = "utf-8") -> ParsedCsv:
    return parse_csv(text.encode(encoding), TZ, "acc_1")


def test_template_parses_completely() -> None:
    parsed = parse_csv(TEMPLATE.read_bytes(), TZ, "acc_1")
    assert parsed.rows_total == 9
    assert parsed.issues == []
    by_desc = {r["description"]: r for r in parsed.records}
    groceries = by_desc["Супермаркет Пятёрочка"]
    assert groceries["amount_minor"] == -145_000
    assert groceries["occurred_at"] == "2026-10-01T06:15:00+00:00"  # 09:15 MSK
    assert groceries["category"] == "groceries" and groceries["category_source"] == "rule"
    assert by_desc["Перевод между своими счетами"]["type"] == "transfer_in"
    assert by_desc["Возврат OZON"]["type"] == "refund"
    assert by_desc["Аванс"]["category"] == "salary"
    assert by_desc["Мобильная связь"]["category_source"] == "source"
    assert by_desc["Яндекс Такси"]["status"] == "pending"
    assert parsed.column_mapping["amount"] == "Сумма"
    assert len(parsed.preview) == 9


def test_comma_delimiter_english_headers_and_bom() -> None:
    text = "﻿date,amount,description,currency\n2026-10-02,-99.90,Coffee,RUB\n"
    parsed = _parse(text)
    [record] = parsed.records
    assert record["amount_minor"] == -9_990
    assert record["occurred_at"] == "2026-10-02T09:00:00+00:00"  # полдень MSK
    assert record["category"] == "cafe"


def test_cp1251_and_russian_date_format_with_direction_column() -> None:
    text = (
        "Дата;Сумма;Тип операции;Назначение платежа\n"
        "19.10.2026 13:05;1200,50;Списание;Аптека\n"
        "20.10.26;5000;Зачисление;Перевод от Ивана\n"
    )
    parsed = _parse(text, "cp1251")
    amounts = [r["amount_minor"] for r in parsed.records]
    assert amounts == [-120_050, 500_000]


@pytest.mark.parametrize(
    ("line", "code"),
    [
        ("2026-13-45;-100;x", "bad_date"),
        ("2026-10-01;сто рублей;x", "bad_amount"),
        ("2026-10-01;0;x", "zero_amount"),
    ],
)
def test_bad_rows_are_rejected_with_reason(line: str, code: str) -> None:
    parsed = _parse(f"date;amount;description\n2026-10-01;-100;ok\n{line}\n")
    assert parsed.rows_total == 2
    assert len(parsed.records) == 1
    [issue] = parsed.issues
    assert (issue.row, issue.code) == (3, code)


def test_foreign_currency_and_unknown_status_are_not_silently_fixed() -> None:
    parsed = _parse(
        "date;amount;currency;status\n2026-10-01;-10;USD;\n2026-10-01;-10;RUB;странный\n"
    )
    assert [i.code for i in parsed.issues] == ["unsupported_currency", "bad_status"]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "empty_file"),
        ("описание;категория\nx;y\n", "missing_columns"),
    ],
)
def test_file_level_errors(text: str, code: str) -> None:
    with pytest.raises(CsvFormatError) as exc:
        _parse(text)
    assert exc.value.code == code


def test_formula_injection_is_neutralized() -> None:
    assert sanitize_text('=HYPERLINK("http://x")') == '\'=HYPERLINK("http://x")'
    assert sanitize_text("@SUM(A1)") == "'@SUM(A1)"
    assert sanitize_text("  обычный   текст ") == "обычный текст"
    assert sanitize_text("   ") is None
    parsed = _parse("date;amount;description\n2026-10-01;-10;=1+1\n")
    assert parsed.records[0]["description"] == "'=1+1"


def test_external_ids_are_stable_and_distinguish_identical_rows() -> None:
    text = "date;amount;description\n2026-10-01;-100;Метро\n2026-10-01;-100;Метро\n"
    first = [r["external_id"] for r in _parse(text).records]
    second = [r["external_id"] for r in _parse(text).records]
    assert first == second
    assert len(set(first)) == 2
    explicit = _parse("id;date;amount\nop-1;2026-10-01;-100\n")
    assert explicit.records[0]["external_id"] == "op-1"
