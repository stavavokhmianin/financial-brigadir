"""Экспорт контракта: ``python services/api/scripts/export_openapi.py [--check]``.

Пишет ``packages/api_contracts/openapi.yaml``. С ``--check`` только сравнивает и
возвращает 1, если файл устарел.
"""

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from app.main import create_app

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / "packages" / "api_contracts" / "openapi.yaml"
HEADER = "# Сгенерировано services/api/scripts/export_openapi.py — не редактировать вручную.\n"


def current_schema() -> dict[str, Any]:
    # JSON-круг нормализует типы (кортежи → списки), чтобы сравнение с YAML было честным.
    schema: dict[str, Any] = json.loads(json.dumps(create_app().openapi()))
    return schema


def render(schema: dict[str, Any]) -> str:
    return HEADER + yaml.safe_dump(schema, allow_unicode=True, sort_keys=False, width=100)


def main(argv: list[str]) -> int:
    text = render(current_schema())
    if "--check" in argv:
        actual = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if actual != text:
            print(f"{TARGET} устарел: запустите scripts/export_openapi.py", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"записан {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
