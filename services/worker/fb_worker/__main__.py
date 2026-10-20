import logging
import os

from app.db.session import SessionLocal
from app.modules.privacy import purge_expired_profiles
from fb_worker.runner import Worker


def _heartbeat() -> None:
    logging.getLogger("fb_worker").info("heartbeat")


def _retention() -> None:
    with SessionLocal() as db:
        count = purge_expired_profiles(db)
    if count:
        logging.getLogger("fb_worker").info("expired profiles removed: %d", count)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    worker = Worker(interval_seconds=float(os.environ.get("WORKER_INTERVAL_SECONDS", "60")))
    worker.register("heartbeat", _heartbeat)
    worker.register("retention", _retention)
    worker.run_forever()


if __name__ == "__main__":
    main()
