from fb_worker.runner import Worker


def test_failing_job_does_not_stop_others() -> None:
    calls: list[str] = []

    def broken() -> None:
        raise RuntimeError("boom")

    worker = Worker(interval_seconds=0)
    worker.register("broken", broken)
    worker.register("ok", lambda: calls.append("ok"))

    assert worker.run_once() == {"broken": False, "ok": True}
    assert calls == ["ok"]
