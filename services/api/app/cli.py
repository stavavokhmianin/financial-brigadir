"""Команды оператора пилотного стенда: ``python -m app.cli <команда>``.

- ``invite --count 5 --days 30`` — выдать персональные коды участников;
- ``list-codes`` — коды без секретов: id, срок, отзыв, привязан ли профиль;
- ``revoke-code <id>`` — отозвать код, новые входы по нему невозможны;
- ``reapply-erasures`` — после восстановления бэкапа снова удалить стёртые профили;
- ``pilot-report [--out файл]`` — точность прогноза против факта, только агрегаты;
- ``retention`` — удалить заброшенные демо-профили старше 7 дней (для таймера systemd).
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import PilotAccessCode
from app.db.session import SessionLocal
from app.modules.evaluation import collect, render
from app.modules.pilot import issue_codes, revoke_code
from app.modules.privacy import purge_expired_profiles, reapply_erasures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    invite = commands.add_parser("invite", help="выдать коды участников пилота")
    invite.add_argument("--count", type=int, default=1)
    invite.add_argument("--days", type=int, default=30)
    commands.add_parser("list-codes", help="список кодов без секретов")
    revoke = commands.add_parser("revoke-code", help="отозвать код по id")
    revoke.add_argument("code_id")
    commands.add_parser("reapply-erasures", help="повторить удаления после восстановления")
    report = commands.add_parser("pilot-report", help="прогноз против факта на данных пилота")
    report.add_argument("--out", help="записать Markdown в файл вместо вывода")
    report.add_argument("--include-demo", action="store_true", help="учитывать демо-профили")
    commands.add_parser("retention", help="удалить заброшенные демо-профили старше 7 дней")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.command == "invite":
            # Коды выводятся один раз и только в терминал оператора, в лог не пишутся.
            for issued in issue_codes(db, args.count, args.days):
                print(f"{issued.id}\t{issued.code}\tдо {issued.expires_at:%Y-%m-%d}")
        elif args.command == "list-codes":
            for row in db.scalars(select(PilotAccessCode).order_by(PilotAccessCode.created_at)):
                state = "отозван" if row.revoked_at else "активен"
                profile = "профиль создан" if row.user_id else "не использован"
                print(f"{row.id}\t{state}\tдо {row.expires_at:%Y-%m-%d}\t{profile}")
        elif args.command == "revoke-code":
            if not revoke_code(db, args.code_id):
                print("код не найден или уже отозван", file=sys.stderr)
                return 1
            print("отозван")
        elif args.command == "pilot-report":
            text = render(collect(db, include_demo=args.include_demo))
            if args.out:
                Path(args.out).write_text(text, encoding="utf-8")
                print(f"отчёт: {args.out}")
            else:
                print(text, end="")
        elif args.command == "retention":
            count = purge_expired_profiles(db, log_path=get_settings().erasure_log_path)
            print(f"удалено заброшенных демо-профилей: {count}")
        else:
            count = reapply_erasures(db, get_settings().erasure_log_path)
            print(f"повторно удалено профилей: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
