"""Обход всех экранов web-клиента: ничего не должно «отваливаться».

    python scripts/qa_screens.py --web http://127.0.0.1:8081 [--out artifacts/qa]

Для каждого демо-профиля открывает каждый экран и нажимает основные действия.
Падает, если на экране появилась ошибка («Не удалось…», «Ошибка сервера…»), если в
браузере было исключение JS или API ответил 5xx. Кадры каждого экрана — в --out.
API должен работать в демо-режиме.
"""

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page, Response, ViewportSize, expect, sync_playwright

PROFILES = ("Молодой специалист", "Кредитная карта и рассрочка", "Фрилансер", "Два банка")
ERROR_TEXT = re.compile(
    r"Не удалось|Ошибка сервера|Неизвестная ошибка|Сервер недоступен|Импорт не выполнен|Нет связи"
)
VIEWPORT: ViewportSize = {"width": 430, "height": 900}


class Run:
    def __init__(self, page: Page, out: Path) -> None:
        self.page = page
        self.out = out
        self.problems: list[str] = []
        self.where = "старт"
        page.on("pageerror", lambda error: self.problems.append(f"{self.where}: JS {error}"))
        page.on("response", self._response)

    def _response(self, response: Response) -> None:
        if "/api/" in response.url and response.status >= 500:
            self.problems.append(f"{self.where}: {response.status} {response.url}")

    def tap(self, name: str | re.Pattern[str], role: str = "button") -> None:
        exact = isinstance(name, str)
        target = (
            self.page.get_by_role(role, name=name, exact=exact)  # type: ignore[arg-type]
            .filter(visible=True)
            .first
        )
        expect(target).to_be_visible(timeout=15_000)
        target.click()
        self.page.wait_for_timeout(700)

    def settle(self) -> None:
        # Ждём, пока уйдут индикаторы загрузки, затем проверяем текст экрана.
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(400)
        text = self.page.locator("body").inner_text()
        visible_errors = [
            line for line in text.splitlines() if ERROR_TEXT.search(line) and line.strip()
        ]
        if visible_errors:
            self.problems.append(f"{self.where}: {visible_errors[0][:160]}")

    def screen(self, name: str, button: str, actions: Callable[[], None] | None = None) -> None:
        self.where = name
        self.tap(button)
        self.settle()
        if actions:
            actions()
            self.settle()
        slug = re.sub(r"\W+", "-", name.lower()).strip("-")
        self.page.screenshot(path=str(self.out / f"{slug}.png"), full_page=True)
        self.page.go_back()
        self.page.wait_for_timeout(800)


def profile_pass(run: Run, profile: str) -> None:
    page = run.page
    run.where = f"{profile}: старт"
    # Имя карточки профиля включает описание: сопоставляем по началу.
    run.tap(re.compile("^" + re.escape(profile)), role="radio")
    run.tap("Запустить демо")
    expect(page.get_by_text("Свободные средства").filter(visible=True).first).to_be_visible(
        timeout=20_000
    )
    run.where = f"{profile}: главная"
    run.settle()

    def forecast() -> None:
        run.tap("0 ₽", role="radio")
        run.tap("Пересчитать")

    def simulate() -> None:
        amount = page.get_by_test_id("purchase-amount").filter(visible=True).first
        amount.fill("5000")
        run.tap("Посчитать")
        expect(page.get_by_text("Что изменится").filter(visible=True).first).to_be_visible(
            timeout=15_000
        )

    def add() -> None:
        for section in ("Доход", "Счёт", "Обязательство"):
            run.tap(section, role="radio")
        page.get_by_label("Название", exact=True).filter(visible=True).first.fill("Спортзал")
        page.get_by_label("Сумма, ₽", exact=True).filter(visible=True).first.fill("2500")
        page.get_by_label("Дата платежа", exact=True).filter(visible=True).first.fill("05.11")
        run.tap("Сохранить")
        saved = page.get_by_text("Обязательство добавлено").filter(visible=True).first
        expect(saved).to_be_visible(timeout=15_000)

    def bank() -> None:
        run.tap("Разрешить чтение синтетики на 24 часа")
        run.tap("Синхронизировать учебный счёт")
        expect(page.get_by_text("Новых операций").filter(visible=True).first).to_be_visible(
            timeout=20_000
        )

    def import_csv() -> None:
        run.tap("Вставить пример")
        run.tap("Проверить")
        expect(page.get_by_text("Предпросмотр").filter(visible=True).first).to_be_visible(
            timeout=15_000
        )
        run.tap("Импортировать")
        done = page.get_by_text(re.compile("Выписка загружена|Эта выписка уже загружена"))
        expect(done.filter(visible=True).first).to_be_visible(timeout=15_000)

    def plans() -> None:
        run.tap("Проверить Free в демо")
        run.tap("Проверить Plus в демо")

    screens: list[tuple[str, str, Callable[[], None] | None]] = [
        ("прогноз", "Открыть прогноз", forecast),
        ("покупка", "Что если купить?", simulate),
        ("календарь", "Календарь платежей", None),
        ("предупреждения", "Предупреждения", None),
        ("добавить", "Добавить обязательство, доход или счёт", add),
        ("импорт", "Загрузить выписку CSV", import_csv),
        ("тарифы", "Free и Plus", plans),
        ("учебный-банк", "Учебный банк (мок)", bank),
        ("приватность", "Приватность, экспорт и выход", None),
    ]
    for name, button, actions in screens:
        run.screen(f"{profile}: {name}", button, actions)

    duplicates = page.get_by_role("button", name=re.compile("Проверить")).filter(visible=True)
    if duplicates.count():
        run.screen(f"{profile}: дубли", duplicates.first.inner_text().strip(), None)

    # Выход возвращает на старт: следующий профиль начинается с чистого состояния.
    run.where = f"{profile}: выход"
    run.tap("Приватность, экспорт и выход")
    run.tap("Выйти и отозвать сессии")
    expect(page.get_by_role("button", name="Запустить демо")).to_be_visible(timeout=15_000)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", default="http://127.0.0.1:8081")
    parser.add_argument("--out", default="artifacts/qa")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, locale="ru-RU")
        page.goto(args.web)
        run = Run(page, out)
        try:
            for profile in PROFILES:
                profile_pass(run, profile)
        except Exception as error:
            page.screenshot(path=str(out / "failure.png"), full_page=True)
            run.problems.append(f"{run.where}: {type(error).__name__}: {str(error)[:300]}")
        finally:
            browser.close()

    for problem in run.problems:
        print(f"FAIL {problem}")
    if run.problems:
        return 1
    print(f"ok   все экраны {len(PROFILES)} профилей без ошибок; кадры в {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
