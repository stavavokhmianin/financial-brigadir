"""Visual regression smoke test against a real demo API; no mocked financial data."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://127.0.0.1:8081")
    parser.add_argument("--out", default="artifacts/design-qa")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel)
        page = browser.new_page(viewport={"width": 1440, "height": 1080}, locale="ru-RU")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.web)
        page.get_by_role("button", name="Начать без регистрации", exact=True).wait_for()
        page.wait_for_timeout(600)
        page.screenshot(path=str(out / "landing-desktop.png"))
        page.get_by_role("button", name="Технические сценарии демо", exact=True).click()
        page.get_by_role("button", name="Запустить демо", exact=True).click()
        page.get_by_text("Свободные средства", exact=True).wait_for(timeout=30000)
        page.wait_for_timeout(800)
        checks = []
        for width in [1440, 768, 390, 320]:
            page.set_viewport_size({"width": width, "height": 1000})
            page.wait_for_timeout(500)
            page.screenshot(path=str(out / f"dashboard-{width}.png"))
            checks.append(
                {
                    "width": width,
                    "overflow": page.evaluate("document.documentElement.scrollWidth > innerWidth"),
                }
            )
        page.set_viewport_size({"width": 1440, "height": 1080})
        page.get_by_role("button", name="Включить светлую тему").click()
        page.screenshot(path=str(out / "dashboard-light.png"))
        page.get_by_role("button", name="Включить тёмную тему").click()
        page.get_by_role("button", name="Прогноз", exact=True).click()
        page.get_by_text("Ваш финансовый резерв", exact=True).count()
        page.get_by_role("button", name="Следующая дата прогноза", exact=True).wait_for()
        page.wait_for_timeout(500)
        page.screenshot(path=str(out / "forecast-desktop.png"))
        page.get_by_role("button", name="Следующая дата прогноза", exact=True).click()
        page.get_by_role("button", name="Что, если?", exact=True).click()
        page.get_by_test_id("purchase-amount").wait_for()
        page.get_by_test_id("purchase-amount").fill("5000")
        page.screenshot(path=str(out / "simulate-desktop.png"))
        page.get_by_test_id("calculate-scenario").click()
        page.locator("[data-testid^=scenario-verdict-]").wait_for(timeout=30000)
        page.screenshot(path=str(out / "simulate-result.png"))
        page.get_by_role("button", name="Календарь", exact=True).click()
        page.wait_for_timeout(900)
        page.screenshot(path=str(out / "calendar-desktop.png"))
        print(json.dumps({"errors": errors, "checks": checks}, ensure_ascii=False))
        if errors:
            raise RuntimeError(str(errors))
        if any(c["overflow"] for c in checks):
            raise RuntimeError("Horizontal overflow detected")
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
