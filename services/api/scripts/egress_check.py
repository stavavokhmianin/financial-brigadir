"""Проверка изоляции пилотного контура: из контейнера API интернет недоступен.

``python scripts/egress_check.py`` — код 0, если исходящее соединение не удалось.
"""

import sys
import urllib.request

TARGETS = ("https://example.com", "https://pypi.org", "http://1.1.1.1")


def main() -> int:
    for url in TARGETS:
        try:
            urllib.request.urlopen(url, timeout=5)  # noqa: S310 — проверяем именно выход наружу
        except OSError as exc:
            print(f"ok   нет выхода: {url} ({type(exc).__name__})")
        else:
            print(f"FAIL исходящее соединение открылось: {url}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
