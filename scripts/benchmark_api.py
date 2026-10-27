"""Local synthetic API latency check for TZ 13.4/26.1, excluding import time."""

import argparse
import json
import platform
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx


def benchmark(api: str, rows: int, samples: int) -> dict[str, Any]:
    with httpx.Client(base_url=api.rstrip("/"), timeout=120, trust_env=False) as client:
        created = client.post("/api/v1/demo/sessions", json={})
        created.raise_for_status()
        session = created.json()
        client.headers["Authorization"] = "Bearer " + session["access_token"]
        try:

            def measure(path: str, body: dict[str, Any]) -> tuple[float, dict[str, Any]]:
                started = time.perf_counter()
                response = client.post(path, json=body)
                elapsed = time.perf_counter() - started
                response.raise_for_status()
                return elapsed, response.json()

            demo_times = [measure("/api/v1/forecasts", {})[0] for _ in range(samples)]
            account = client.get("/api/v1/accounts")
            account.raise_for_status()
            account_id = account.json()["items"][0]["id"]
            now = datetime.now(UTC)
            csv = "date;amount;id\n" + "\n".join(
                f"{(now - timedelta(minutes=i * 30)).isoformat()};-{10 + i % 17}.00;bench-{i}"
                for i in range(rows)
            )
            imported = client.post(
                "/api/v1/imports/csv",
                data={
                    "account_id": account_id,
                    "content": csv,
                    "mode": "import",
                },
            )
            imported.raise_for_status()
            if imported.json()["rows_imported"] != rows:
                raise RuntimeError("Benchmark input was not fully imported")
            forecast_times: list[float] = []
            scenario_times: list[float] = []
            for _ in range(samples):
                elapsed, base = measure("/api/v1/forecasts", {"horizon_days": 30})
                forecast_times.append(elapsed)
                elapsed, _ = measure(
                    "/api/v1/scenarios",
                    {
                        "base_forecast_id": base["forecast_id"],
                        "events": [{"type": "expense", "amount_minor": 1_200_000}],
                    },
                )
                scenario_times.append(elapsed)

            def summary(values: list[float], limit: float) -> dict[str, Any]:
                return {
                    "samples": len(values),
                    "seconds": [round(x, 4) for x in values],
                    "median_seconds": round(statistics.median(values), 4),
                    "max_seconds": round(max(values), 4),
                    "limit_seconds": limit,
                    "passed": max(values) < limit,
                }

            result = {
                "measured_at": datetime.now(UTC).isoformat(),
                "environment": {"system": platform.system(), "python": platform.python_version()},
                "synthetic_only": True,
                "additional_csv_rows": rows,
                "demo_forecast": summary(demo_times, 2),
                "forecast_after_import": summary(forecast_times, 3),
                "scenario_after_import": summary(scenario_times, 3),
                "scope": "sequential local latency smoke; not a concurrency/p95 benchmark",
            }
        finally:
            erased = client.request(
                "DELETE", "/api/v1/privacy/profile", json={"confirmation": "DELETE"}
            )
            erased.raise_for_status()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not 1 <= args.rows <= 20_000 or not 1 <= args.samples <= 10:
        parser.error("rows must be 1..20000, samples 1..10")
    result = benchmark(args.api, args.rows, args.samples)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if not all(
        result[key]["passed"]
        for key in (
            "demo_forecast",
            "forecast_after_import",
            "scenario_after_import",
        )
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
