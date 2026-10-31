"""Видео-страховка демо 16.4: проход web-клиента с субтитрами шагов.

    pip install playwright && python -m playwright install chromium
    python scripts/record_demo.py --web http://127.0.0.1:8081 --out artifacts/demo

API должен работать в демо-режиме, web-клиент — собран с адресом этого API.
Видео (.webm) пишется в --out. Это страховка, а не замена живого показа (16.4).
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Literal

from playwright.sync_api import Page, ViewportSize, expect, sync_playwright

VIEWPORT: ViewportSize = {"width": 430, "height": 900}
CAPTION_JS = """
(text) => {
  let el = document.getElementById("demo-caption");
  if (!el) {
    el = document.createElement("div");
    el.id = "demo-caption";
    el.style.cssText = "position:fixed;left:8px;right:8px;bottom:8px;z-index:99999;" +
      "padding:10px 12px;border-radius:10px;background:rgba(15,17,21,.88);color:#fff;" +
      "font:600 15px/1.35 system-ui,sans-serif;pointer-events:none";
    document.body.appendChild(el);
  }
  el.textContent = text;
}
"""


# Expo Router держит прежние экраны стека в DOM скрытыми: ищем только видимые элементы.
class Demo:
    def __init__(self, page: Page, pace: float, out: Path) -> None:
        self.page = page
        self.pace = pace
        self.out = out
        self.shots = 0

    def snapshot(self, name: str) -> None:
        """Кадр для презентации и проверки субтитров без просмотра видео."""
        self.shots += 1
        self.page.screenshot(path=str(self.out / f"{self.shots:02d}-{name}.png"))

    def caption(self, text: str, hold: float = 2.5) -> None:
        self.page.evaluate(CAPTION_JS, text)
        self.wait(hold)

    def wait(self, seconds: float) -> None:
        self.page.wait_for_timeout(int(seconds * 1000 * self.pace))

    def button(self, name: str, role: Literal["button", "radio"] = "button") -> None:
        target = self.page.get_by_role(role, name=name, exact=True).filter(visible=True).first
        target.scroll_into_view_if_needed()
        self.wait(0.6)
        target.click()

    def scroll(self, pixels: int, steps: int = 4) -> None:
        for _ in range(steps):
            self.page.mouse.wheel(0, pixels // steps)
            self.wait(0.5)

    def show(self, test_id: str) -> None:
        element = self.page.get_by_test_id(test_id).filter(visible=True).first
        expect(element).to_be_visible(timeout=15_000)
        # По центру кадра: снизу экран закрывает строка субтитров.
        element.evaluate("e => e.scrollIntoView({block: 'center'})")
        self.wait(0.8)

    def expect_text(self, text: str) -> None:
        element = self.page.get_by_text(text).filter(visible=True).first
        expect(element).to_be_visible(timeout=20_000)
        element.evaluate("e => e.scrollIntoView({block: 'center'})")

    def back(self) -> None:
        self.page.go_back()
        self.wait(1.2)

    def close_panel(self) -> None:
        close = self.page.get_by_text("Закрыть", exact=True).filter(visible=True).first
        expect(close).to_be_visible(timeout=15_000)
        close.click()
        self.wait(0.8)


def run(demo: Demo) -> None:
    page = demo.page
    demo.caption("«Финансовый бригадир»: хватит ли денег до следующего дохода — до покупки.", 3)

    demo.caption("Шаг 1. Личный учебный аккаунт: синтетика, без банковских паролей.")
    demo.button("Попробовать без регистрации")
    demo.expect_text("Свободные средства")
    demo.caption("История, счета и будущие операции принадлежат одному изолированному профилю.", 3)
    demo.snapshot("dashboard")
    demo.scroll(500)

    demo.caption("Шаг 2. Прогноз на 30 дней прямо на главной: коридор, день риска и причины.")
    # Отдельного экрана прогноза нет: график и решение — на главной (docs/product-ux.md).
    demo.expect_text("Возможен риск")
    demo.caption("«Возможен риск»: резерв сохраняется в базовом сценарии, но не в плохом.", 3)
    demo.expect_text("Остаток по дням")
    demo.caption("Коридор на графике — неопределённость; он расширяется в окно зарплаты.", 3)
    demo.snapshot("forecast")
    page.mouse.wheel(0, -3000)
    demo.wait(0.8)

    demo.caption("Шаг 3. Проверяем покупку 12 000 ₽ до оплаты.")
    demo.button("Что если купить?")
    amount = page.get_by_test_id("purchase-amount").filter(visible=True).first
    expect(amount).to_be_visible(timeout=15_000)
    amount.click()
    amount.press_sequentially("12000", delay=120)
    demo.button("Посчитать")
    # Сначала вердикт; шкала и таблица «до / после» — под «Показать расчёт» (REPORT_7.7).
    demo.show("scenario-verdict-shortfall")
    demo.button("Показать расчёт")
    demo.show("risk-scale-high")
    demo.caption("Риск вырос: «Средний» → «Высокий». В истории операций ничего не появилось.", 4)
    demo.snapshot("purchase")
    demo.scroll(700, steps=5)

    demo.caption("Шаг 4. Покупку убираем. А если зарплата придёт на 2 дня позже?")
    # Как в живом показе: без «Не учитывать» задержка считалась бы вместе с покупкой.
    demo.button("Не учитывать")
    page.mouse.wheel(0, -3000)
    demo.wait(0.8)
    demo.button("на 2 дн.", role="radio")
    demo.button("Посчитать")
    demo.button("Показать расчёт")
    demo.expect_text("Если доход придёт на 2 дн. позже")
    demo.caption("Минимум 6 551 → 3 828 ₽, резерв под угрозой с 26 октября.", 3)
    demo.snapshot("salary-delay")
    demo.scroll(600)
    demo.back()

    demo.caption("Шаг 5. Одно полезное предупреждение; повтор того же риска подавлен.")
    # Уведомления — панель поверх главной по колокольчику, отдельного экрана нет.
    page.mouse.wheel(0, -3000)
    demo.wait(0.8)
    bell = page.get_by_role("button", name=re.compile("^Уведомления")).filter(visible=True).first
    expect(bell).to_be_visible(timeout=15_000)
    bell.click()
    demo.expect_text("Уведомления")
    demo.expect_text("Не показано")
    demo.wait(2)
    demo.snapshot("alerts")
    demo.close_panel()

    demo.caption("Учебный банк: явное согласие на 24 часа, только синтетические данные.")
    demo.button("Данные и настройки")
    demo.button("Учебный банк (мок)")
    demo.button("Разрешить чтение синтетики на 24 часа")
    demo.wait(1)
    demo.button("Синхронизировать учебный счёт")
    demo.expect_text("Новых операций")
    demo.caption("Операции загружены. Повторная загрузка не создаёт дублей.", 2)
    demo.snapshot("bank-mock")
    demo.button("Синхронизировать учебный счёт")
    demo.expect_text("Новых операций: 0")
    demo.wait(2)
    demo.back()

    demo.caption("Шаг 6. Код, тесты, сравнение с baseline и бизнес-модель — в репозитории.", 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://127.0.0.1:8081")
    parser.add_argument("--out", default="artifacts/demo")
    parser.add_argument("--pace", type=float, default=1.0, help="0.2 — быстрая проверка")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,
            locale="ru-RU",
            color_scheme="light",
            record_video_dir=str(out),
            record_video_size=VIEWPORT,
        )
        page = context.new_page()
        page.goto(args.web)
        try:
            run(Demo(page, args.pace, out))
        except Exception:
            page.screenshot(path=str(out / "failure.png"))
            raise
        finally:
            video = page.video
            context.close()
            browser.close()
            if video:
                target = out / "demo-16-4.webm"
                Path(video.path()).replace(target)
                print(f"видео: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
