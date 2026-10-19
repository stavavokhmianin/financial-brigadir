import logging
import signal
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

log = logging.getLogger("fb_worker")

Job = Callable[[], None]


@dataclass
class Worker:
    """Периодически выполняет зарегистрированные задачи.

    Ошибка одной задачи логируется и не останавливает цикл: падение воркера не
    должно трогать уже импортированную историю (раздел 13.3). Задачи импорта и
    пересчёта прогнозов регистрируются на следующих этапах.
    """

    interval_seconds: float = 60.0
    jobs: dict[str, Job] = field(default_factory=dict)
    _stop: threading.Event = field(default_factory=threading.Event)

    def register(self, name: str, job: Job) -> None:
        self.jobs[name] = job

    def run_once(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name, job in self.jobs.items():
            try:
                job()
            except Exception:
                log.exception("job failed: %s", name)
                results[name] = False
            else:
                results[name] = True
        return results

    def stop(self, *_: object) -> None:
        self._stop.set()

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        log.info("worker started, jobs=%s", sorted(self.jobs))
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self.interval_seconds)
        log.info("worker stopped")
