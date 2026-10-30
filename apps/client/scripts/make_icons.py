"""Иконки приложения без графических зависимостей: python apps/client/scripts/make_icons.py

Рисунок — три столбика остатка и синяя линия резерва (образ продукта) на почти чёрном фоне,
как знак в самом приложении.
"""

import struct
import zlib
from pathlib import Path

BACKGROUND = (10, 10, 10, 255)
WHITE = (255, 255, 255, 255)
RESERVE = (0, 112, 243, 255)
CLEAR = (0, 0, 0, 0)
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def png(path: Path, size: int, pixel) -> None:  # type: ignore[no-untyped-def]
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # фильтр строки: None
        for x in range(size):
            rows.extend(pixel(x / size, y / size))
    chunk = lambda tag, data: (  # noqa: E731
        struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    )
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    body = zlib.compress(bytes(rows), 9)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", body)
                     + chunk(b"IEND", b""))


def mark(u: float, v: float) -> tuple[int, int, int, int] | None:
    """Рисунок в квадрате 0..1: столбики остатка и пунктир резерва."""
    # Пунктир резерва поверх столбиков: главный смысл продукта — не опуститься ниже него.
    if 0.585 <= v <= 0.615 and 0.18 <= u <= 0.84 and int(u * 30) % 2 == 0:
        return RESERVE
    bars = ((0.25, 0.34), (0.44, 0.50), (0.63, 0.24))  # (левый край, верх столбика)
    for left, top in bars:
        if left <= u <= left + 0.13 and top <= v <= 0.72:
            return WHITE
    return None


def icon(u: float, v: float) -> tuple[int, int, int, int]:
    return mark(u, v) or BACKGROUND


def adaptive(u: float, v: float) -> tuple[int, int, int, int]:
    # Android обрезает края адаптивной иконки: рисунок — в центральных 2/3.
    inner_u, inner_v = (u - 1 / 6) * 1.5, (v - 1 / 6) * 1.5
    if 0 <= inner_u <= 1 and 0 <= inner_v <= 1:
        return mark(inner_u, inner_v) or CLEAR
    return CLEAR


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    png(ASSETS / "icon.png", 1024, icon)
    png(ASSETS / "adaptive-icon.png", 1024, adaptive)
    png(ASSETS / "favicon.png", 48, icon)
    print(f"иконки записаны в {ASSETS}")
