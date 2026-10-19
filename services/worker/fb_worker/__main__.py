import logging
import os

from fb_worker.runner import Worker


def _heartbeat() -> None:
    logging.getLogger("fb_worker").info("heartbeat")


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    worker = Worker(interval_seconds=float(os.environ.get("WORKER_INTERVAL_SECONDS", "60")))
    worker.register("heartbeat", _heartbeat)
    worker.run_forever()


if __name__ == "__main__":
    main()
