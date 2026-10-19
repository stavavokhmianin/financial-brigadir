"""CLI: ``fb-synth young_specialist --seed 42 --out profile.json`` или ``fb-synth --list``."""

import argparse
import json
import sys
from datetime import datetime

from synthetic_generator.generator import (
    DEFAULT_AS_OF,
    DEFAULT_HORIZON_DAYS,
    DEFAULT_MONTHS,
    DEFAULT_SEED,
    generate,
    list_profiles,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fb-synth", description="Синтетические профили")
    parser.add_argument("profile", nargs="?", help="id профиля")
    parser.add_argument("--list", action="store_true", help="показать профили")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF.isoformat(), help="ISO-время с таймзоной")
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS)
    parser.add_argument("--horizon-days", type=int, default=DEFAULT_HORIZON_DAYS)
    parser.add_argument("--out", help="файл для JSON (по умолчанию stdout)")
    args = parser.parse_args(argv)

    if args.list or not args.profile:
        for item in list_profiles():
            mark = "" if item["mvp"] else " (после MVP)"
            print(f"{item['id']:<18} {item['title']}{mark}")
        return 0

    as_of = datetime.fromisoformat(args.as_of)
    data = generate(args.profile, args.seed, as_of, args.months, args.horizon_days)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
