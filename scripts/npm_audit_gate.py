"""Шлюз аудита npm (раздел 25: аудит зависимостей).

    npm audit --json | python scripts/npm_audit_gate.py apps/client/audit-allowlist.json

Падает на любой находке high/critical, которой нет в allowlist, и на просроченном
пересмотре allowlist. Принятые находки печатаются, чтобы оставаться на виду.
"""

import json
import sys
from datetime import UTC, date, datetime
from typing import Any

GATED = {"high", "critical"}


def advisories(report: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    found: dict[str, tuple[str, str, str]] = {}
    for vulnerability in report.get("vulnerabilities", {}).values():
        for source in vulnerability.get("via", []):
            if isinstance(source, dict):
                ghsa = str(source.get("url", "")).rsplit("/", 1)[-1]
                found[ghsa] = (source["severity"], source["name"], source["title"])
    return found


def main(allowlist_path: str) -> int:
    report = json.load(sys.stdin)
    with open(allowlist_path, encoding="utf-8") as file:
        allowlist = json.load(file)
    accepted = allowlist["advisories"]
    failed = False

    if date.fromisoformat(allowlist["review_by"]) < datetime.now(UTC).date():
        print(f"FAIL срок пересмотра allowlist истёк: {allowlist['review_by']}")
        failed = True
    for ghsa, (severity, package, title) in sorted(advisories(report).items()):
        if severity not in GATED:
            print(f"info {severity:8} {package}: {title} ({ghsa})")
        elif ghsa in accepted:
            print(f"ok   принято {package}: {ghsa} — {accepted[ghsa]['reason']}")
        else:
            print(f"FAIL {severity:8} {package}: {title} ({ghsa})")
            failed = True
    stale = set(accepted) - set(advisories(report))
    for ghsa in sorted(stale):
        print(f"info {ghsa} больше не находится — уберите из allowlist")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
