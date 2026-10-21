"""Run Maestro on the CI emulator and preserve diagnostics before it shuts down."""

import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    output = Path("artifacts/mobile")
    output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [  # noqa: S607 — fixed CI tools and test path
            "maestro",
            "test",
            "apps/client/.maestro/mvp.yaml",
            "--format",
            "junit",
            "--output",
            str(output / "results.xml"),
            "--debug-output",
            str(output / "debug"),
        ],
        check=False,
    )
    if result.returncode:
        with (output / "failure.png").open("wb") as screenshot:
            subprocess.run(
                ["adb", "exec-out", "screencap", "-p"],  # noqa: S607
                stdout=screenshot,
                timeout=30,
                check=False,
            )
        subprocess.run(
            ["adb", "shell", "uiautomator", "dump", "/sdcard/window.xml"],  # noqa: S607
            timeout=30,
            check=False,
        )
        subprocess.run(
            ["adb", "pull", "/sdcard/window.xml", str(output / "failure.xml")],  # noqa: S607
            timeout=30,
            check=False,
        )
        with (output / "android-crash.log").open("w", encoding="utf-8") as crash:
            subprocess.run(
                ["adb", "logcat", "-d", "-s", "AndroidRuntime"],  # noqa: S607
                stdout=crash,
                timeout=30,
                check=False,
            )
    api_log = Path(os.environ.get("RUNNER_TEMP", ".")) / "mobile-api.log"
    if api_log.exists():
        shutil.copyfile(api_log, output / "api.log")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
