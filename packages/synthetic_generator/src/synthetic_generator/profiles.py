"""Пять типов синтетических профилей (раздел 12.2) и обязательные аномалии (12.3)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from synthetic_generator.dates import add_months, at, clamp_day, is_short_month, iter_months
from synthetic_generator.ledger import (
    CANCELED,
    POSTED,
    AccountSpec,
    IncomeSpec,
    Ledger,
    ObligationSpec,
    RecurringSpec,
    SpendSpec,
    Tx,
)

RUB = 100  # копеек в рубле


@dataclass(frozen=True)
class ProfileInfo:
    id: str
    prefix: str
    title: str
    description: str
    segment: str
    mvp: bool
    coverage: str
    anomalies: tuple[str, ...]
    build: Callable[[Ledger], None]


def _pick(ledger: Ledger, txs: list[Tx], what: str) -> Tx:
    if not txs:
        raise RuntimeError(f"не нашлось операции для аномалии: {what}")
    return ledger.rng.choice(txs)


def _known(ledger: Ledger, tx: Tx) -> bool:
    return tx.occurred_at <= ledger.as_of


# --- 1. Молодой специалист ---------------------------------------------------


def build_young_specialist(ledger: Ledger) -> None:
    today = ledger.today
    delayed = add_months(today, -3)
    ledger.add_account(AccountSpec("card", "Зарплатная карта", "Банк А", "debit"))
    ledger.incomes = [
        IncomeSpec("advance", "Аванс", "advance", "card", 10, 25_000 * RUB),
        IncomeSpec(
            "salary",
            "Зарплата",
            "salary",
            "card",
            25,
            60_000 * RUB,
            delays={(delayed.year, delayed.month): 3, (today.year, today.month): 2},
            max_delay_days=3,
            probability=0.97,
        ),
    ]
    ledger.obligations = [
        ObligationSpec("loan", "loan", "Потребкредит", "card", 21, 12_000 * RUB),
        ObligationSpec("rent", "rent", "Аренда квартиры", "card", 23, 30_000 * RUB),
        ObligationSpec(
            "utilities",
            "utilities",
            "ЖКХ",
            "card",
            15,
            5_500 * RUB,
            jitter_minor=1_500 * RUB,
            status="uncertain",
            confidence=0.8,
        ),
        ObligationSpec(
            "mobile", "subscription", "Мобильная связь", "card", 3, 500 * RUB, priority="normal"
        ),
        ObligationSpec(
            "music",
            "subscription",
            "Музыкальный сервис",
            "card",
            5,
            399 * RUB,
            status="inferred",
            priority="normal",
            movable=True,
            confidence=0.9,
        ),
    ]
    ledger.spending = [
        SpendSpec("groceries", "card", 0.55, 1_000 * RUB, description="Супермаркет"),
        SpendSpec("clothes", "card", 0.04, 3_000 * RUB, sigma=0.4, description="Одежда"),
        SpendSpec("cafe", "card", 0.25, 450 * RUB, weekend_factor=1.6, description="Кафе"),
        SpendSpec(
            "transport", "card", 0.7, 65 * RUB, sigma=0.2, weekend_factor=0.5, description="Метро"
        ),
        SpendSpec("taxi", "card", 0.08, 450 * RUB, description="Такси"),
        SpendSpec("marketplace", "card", 0.07, 2_300 * RUB, sigma=0.6, description="Маркетплейс"),
        SpendSpec("pharmacy", "card", 0.04, 600 * RUB, description="Аптека"),
        SpendSpec(
            "entertainment",
            "card",
            0.08,
            1_200 * RUB,
            weekend_factor=2.0,
            description="Кино и развлечения",
        ),
    ]
    ledger.simulate_regular()

    # Неожиданная медицинская трата в текущем месяце (12.3).
    medical_day = clamp_day(today.year, today.month, 8)
    medical = ledger.tx(
        "card",
        at(medical_day, 18, 40),
        -14_800 * RUB,
        "expense",
        "medical",
        description="Стоматология",
    )
    ledger.anomaly(
        "unexpected_expense", "Внеплановая медицинская трата", external_ids=[medical.external_id]
    )
    late_salary = [
        t
        for t in ledger.txs
        if t.type == "income"
        and t.category == "salary"
        and (t.occurred_at.year, t.occurred_at.month) == (delayed.year, delayed.month)
    ]
    ledger.anomaly(
        "salary_delay",
        "Зарплата три месяца назад пришла на 3 дня позже обычного",
        external_ids=[t.external_id for t in late_salary],
        delay_days=3,
        expected_date=clamp_day(delayed.year, delayed.month, 25).isoformat(),
    )
    expected = clamp_day(today.year, today.month, 25)
    ledger.hidden_events.append(
        {
            "type": "salary_delay",
            "expected_date": expected.isoformat(),
            "actual_date": (expected + timedelta(days=2)).isoformat(),
        }
    )
    # Целевой остаток на дату выгрузки — для демо-сценария раздела 16.4.
    ledger.set_openings({"card": 300_000}, targets={"card": 55_000 * RUB})


# --- 2. Кредитная карта и рассрочка ------------------------------------------


def build_credit_card(ledger: Ledger) -> None:
    today = ledger.today
    ledger.add_account(AccountSpec("debit", "Дебетовая карта", "Банк Б", "debit"))
    ledger.add_account(
        AccountSpec(
            "credit",
            "Кредитная карта",
            "Банк Б",
            "credit_card",
            credit_limit_minor=150_000 * RUB,
            is_liquid=False,
        )
    )
    ledger.incomes = [
        IncomeSpec("salary1", "Зарплата", "salary", "debit", 5, 32_000 * RUB),
        IncomeSpec("salary2", "Зарплата (вторая часть)", "salary", "debit", 20, 36_000 * RUB),
    ]
    installment_start = clamp_day(2026, 4, 30)
    ledger.obligations = [
        ObligationSpec("rent", "rent", "Аренда комнаты", "debit", 1, 20_000 * RUB),
        # Платёж 31-го числа: в коротких месяцах — последний день (12.3).
        ObligationSpec(
            "phone",
            "installment",
            "Рассрочка за телефон",
            "debit",
            31,
            6_500 * RUB,
            starts=installment_start,
            ends=date(2027, 3, 31),
        ),
        ObligationSpec(
            "streaming",
            "subscription",
            "Онлайн-кинотеатр",
            "credit",
            7,
            299 * RUB,
            status="inferred",
            priority="normal",
            movable=True,
            confidence=0.9,
        ),
    ]
    ledger.spending = [
        SpendSpec("groceries", "credit", 0.5, 900 * RUB, description="Супермаркет"),
        SpendSpec("cafe", "credit", 0.3, 600 * RUB, weekend_factor=1.5, description="Кафе"),
        SpendSpec("marketplace", "credit", 0.1, 3_000 * RUB, sigma=0.6, description="Маркетплейс"),
        SpendSpec("taxi", "credit", 0.1, 450 * RUB, description="Такси"),
        SpendSpec(
            "transport", "debit", 0.6, 65 * RUB, sigma=0.2, weekend_factor=0.5, description="Метро"
        ),
    ]
    ledger.simulate_regular()

    # Возврат и отмена покупки (12.3).
    purchases = [
        t
        for t in ledger.txs
        if t.account == "credit"
        and t.category == "marketplace"
        and _known(ledger, t)
        and t.occurred_at.date() < today - timedelta(days=40)
    ]
    bought = _pick(ledger, purchases, "возврат")
    refund = ledger.refund(bought, bought.occurred_at + timedelta(days=6))
    canceled = ledger.tx(
        "credit",
        at(today - timedelta(days=12), 21, 5),
        -4_590 * RUB,
        "credit_purchase",
        "marketplace",
        status=CANCELED,
        description="Маркетплейс (заказ отменён)",
    )
    ledger.anomaly(
        "refund_and_cancel",
        "Возврат покупки по кредитке и отменённый заказ",
        external_ids=[bought.external_id, refund.external_id, canceled.external_id],
    )

    # Погашение кредитки: 18-го числа полностью гасится долг на дату выписки (10-е).
    payments: list[str] = []
    for year, month in iter_months(ledger.history_from, ledger.horizon_end):
        statement = at(clamp_day(year, month, 10), 23, 59)
        pay_day = clamp_day(year, month, 18)
        if not ledger.history_from < statement.date() or pay_day > ledger.horizon_end:
            continue
        debt = -ledger.balance_at("credit", statement)
        if debt <= 0:
            continue
        out, inn = ledger.credit_card_payment("debit", "credit", at(pay_day, 12, 0), debt)
        payments += [out.external_id, inn.external_id]
    ledger.anomaly(
        "credit_purchase_and_payment",
        "Покупки по кредитке и отдельное погашение с дебетовой карты: трата учитывается один раз",
        external_ids=payments[:6],
    )
    phone = [
        t
        for t in ledger.txs
        if t.category == "installment" and is_short_month(t.occurred_at.date())
    ]
    ledger.anomaly(
        "day_31_short_month",
        "Рассрочка 31-го числа списывается в последний день короткого месяца",
        external_ids=[t.external_id for t in phone],
    )
    ledger.set_openings({"debit": 400_000})

    debt_now = -ledger.balance_at("credit", ledger.as_of)
    next_pay = clamp_day(today.year, today.month, 18)
    if next_pay <= today:
        next_pay = clamp_day(*_next_month(today), 18)
    if debt_now > 0:
        ledger.extra_obligations.append(
            {
                "key": "credit_card_payment",
                "kind": "credit_card",
                "title": "Погашение кредитной карты",
                "account": "debit",
                "due_date": next_pay,
                "amount_minor": debt_now,
                "amount_min_minor": max(1, debt_now * 5 // 100),
                "amount_max_minor": debt_now * 16 // 10,
                "recurrence": "monthly",
                "recurrence_day": 18,
                "status": "uncertain",
                "priority": "critical",
                "confidence": 0.7,
                "movable": False,
            }
        )


def _next_month(day: date) -> tuple[int, int]:
    return (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)


# --- 3. Фрилансер ------------------------------------------------------------


def build_freelancer(ledger: Ledger) -> None:
    today = ledger.today
    rng = ledger.rng
    ledger.add_account(AccountSpec("card", "Карта", "Банк В", "debit"))
    ledger.add_account(AccountSpec("cash", "Наличные", "—", "cash"))
    ledger.obligations = [
        ObligationSpec("rent", "rent", "Аренда квартиры", "card", 1, 35_000 * RUB),
        ObligationSpec(
            "utilities",
            "utilities",
            "ЖКХ",
            "card",
            12,
            4_500 * RUB,
            jitter_minor=1_500 * RUB,
            status="uncertain",
            confidence=0.8,
        ),
        ObligationSpec(
            "mobile", "subscription", "Мобильная связь", "card", 3, 600 * RUB, priority="normal"
        ),
    ]
    ledger.spending = [
        SpendSpec("groceries", "card", 0.45, 950 * RUB, description="Супермаркет"),
        SpendSpec("cafe", "card", 0.3, 500 * RUB, description="Кафе"),
        SpendSpec(
            "coworking",
            "card",
            0.15,
            500 * RUB,
            sigma=0.2,
            weekend_factor=0.2,
            description="Коворкинг",
        ),
        SpendSpec("marketplace", "card", 0.08, 2_800 * RUB, sigma=0.6, description="Маркетплейс"),
        SpendSpec("market", "cash", 0.15, 400 * RUB, description="Рынок"),
    ]
    ledger.simulate_regular()

    # Неравномерные поступления: 2–4 оплаты в месяц, иногда с задержкой.
    monthly_income: dict[tuple[int, int], int] = {}
    for year, month in iter_months(ledger.history_from, ledger.horizon_end):
        for _ in range(rng.randint(2, 4)):
            day = clamp_day(year, month, rng.randint(1, 28))
            if not ledger.history_from <= day <= today:
                continue  # будущие оплаты задаются отдельно (скрытое будущее ниже)
            amount = rng.randint(12_000, 42_000) * RUB
            ledger.tx(
                "card",
                ledger.random_time(day, 10, 19),
                amount,
                "income",
                "freelance",
                description="Оплата от клиента",
            )
            monthly_income[(year, month)] = monthly_income.get((year, month), 0) + amount
        # Снятие наличных — перевод между своими счетами.
        cash_day = clamp_day(year, month, 6)
        if ledger.history_from <= cash_day <= ledger.horizon_end:
            ledger.transfer("card", "cash", at(cash_day, 13, 0), 6_000 * RUB)
    # Налог самозанятого 25-го: 6 % от поступлений прошлого месяца.
    for year, month in iter_months(ledger.history_from, ledger.horizon_end):
        prev = (year - 1, 12) if month == 1 else (year, month - 1)
        tax = monthly_income.get(prev, 0) * 6 // 100
        day = clamp_day(year, month, 25)
        if tax and ledger.history_from <= day <= ledger.horizon_end:
            ledger.tx(
                "card",
                at(day, 11, 0),
                -tax,
                "expense",
                "tax",
                description="Налог на профессиональный доход",
            )

    # Ожидаемая оплата: известен диапазон дат и сумм; фактически приходит позже.
    expected_from = today + timedelta(days=4)
    expected_to = today + timedelta(days=11)
    actual_day = today + timedelta(days=13)
    paid = ledger.tx(
        "card",
        at(actual_day, 15, 30),
        48_000 * RUB,
        "income",
        "freelance",
        description="Оплата от клиента",
    )
    ledger.extra_incomes.append(
        {
            "key": "client_payment",
            "kind": "freelance",
            "title": "Оплата по договору с клиентом",
            "account": "card",
            "date_from": expected_from,
            "date_to": expected_to,
            "amount_min_minor": 40_000 * RUB,
            "amount_max_minor": 55_000 * RUB,
            "probability": 0.7,
            "confirmed": False,
            "recurrence": "none",
        }
    )
    ledger.hidden_events.append(
        {
            "type": "income_delay",
            "expected_date_to": expected_to.isoformat(),
            "actual_date": actual_day.isoformat(),
            "external_id": paid.external_id,
        }
    )
    this_month_tax = monthly_income.get((today.year, today.month), 0) * 6 // 100
    if this_month_tax:
        ledger.extra_obligations.append(
            {
                "key": "npd_tax",
                "kind": "manual",
                "title": "Налог на профессиональный доход",
                "account": "card",
                "due_date": clamp_day(*_next_month(today), 25),
                "amount_minor": this_month_tax,
                "amount_min_minor": None,
                "amount_max_minor": None,
                "recurrence": "monthly",
                "recurrence_day": 25,
                "status": "inferred",
                "priority": "critical",
                "confidence": 0.8,
                "movable": False,
            }
        )

    ledger.set_openings({"card": 300_000, "cash": 150_000})

    # Технический овердрафт: внеплановая трата уводит карту в минус, через 3 дня
    # друг возвращает долг. Остатки после этого окна не меняются.
    when = at(today - timedelta(days=75), 20, 15)
    shortfall = 2_500 * RUB
    repair_amount = max(ledger.balance_at("card", when), 0) + shortfall
    repair = ledger.tx(
        "card", when, -repair_amount, "expense", "household", description="Срочный ремонт ноутбука"
    )
    back = ledger.tx(
        "card",
        when + timedelta(days=3),
        repair_amount,
        "income",
        "other",
        description="Перевод от друга",
    )
    ledger.anomaly(
        "negative_balance",
        "Технический овердрафт после внеплановой траты",
        external_ids=[repair.external_id, back.external_id],
        min_balance_minor=-shortfall,
    )
    ledger.anomaly(
        "unexpected_expense", "Срочный ремонт техники", external_ids=[repair.external_id]
    )
    balance = ledger.balance_at("card", ledger.as_of)
    ledger.manual_balances["card"] = balance + 1_250 * RUB
    ledger.anomaly(
        "balance_mismatch",
        "Пользователь вручную указал остаток, который расходится с выпиской на 1 250 ₽",
        account_id=ledger.account_id("card"),
        imported_minor=balance,
        manual_minor=balance + 1_250 * RUB,
    )


# --- 4. Два банка ------------------------------------------------------------


def build_two_banks(ledger: Ledger) -> None:
    today = ledger.today
    rng = ledger.rng
    ledger.add_account(AccountSpec("main", "Зарплатная карта", "Банк А", "debit"))
    ledger.add_account(AccountSpec("spend", "Карта для трат", "Банк Б", "debit"))
    ledger.add_account(AccountSpec("deposit", "Вклад", "Банк А", "deposit", is_liquid=False))
    ledger.incomes = [
        IncomeSpec("salary", "Зарплата", "salary", "main", 15, 110_000 * RUB),
        IncomeSpec(
            "interest",
            "Проценты по вкладу",
            "other",
            "deposit",
            28,
            1_500 * RUB,
            jitter_minor=100 * RUB,
        ),
    ]
    ledger.obligations = [
        ObligationSpec("mortgage", "loan", "Ипотека", "main", 17, 42_000 * RUB),
        ObligationSpec(
            "utilities",
            "utilities",
            "ЖКХ",
            "spend",
            10,
            6_000 * RUB,
            jitter_minor=2_000 * RUB,
            status="uncertain",
            confidence=0.8,
        ),
    ]
    ledger.spending = [
        SpendSpec("groceries", "spend", 0.5, 1_000 * RUB, description="Супермаркет"),
        SpendSpec("cafe", "spend", 0.3, 700 * RUB, weekend_factor=1.5, description="Кафе"),
        SpendSpec("marketplace", "spend", 0.1, 3_500 * RUB, sigma=0.6, description="Маркетплейс"),
        SpendSpec("fuel", "spend", 0.15, 2_500 * RUB, sigma=0.2, description="АЗС"),
        SpendSpec("groceries", "main", 0.08, 700 * RUB, description="Супермаркет"),
    ]
    ledger.simulate_regular()

    transfers: list[str] = []
    for year, month in iter_months(ledger.history_from, ledger.horizon_end):
        day = clamp_day(year, month, 16)
        if ledger.history_from <= day <= ledger.horizon_end:
            out, inn = ledger.transfer(
                "main", "spend", at(day, 10, 0), 50_000 * RUB, interbank=True
            )
            transfers += [out.external_id, inn.external_id]
        back_day = clamp_day(year, month, 3)
        if rng.random() < 0.3 and ledger.history_from <= back_day <= ledger.horizon_end:
            ledger.transfer("spend", "main", at(back_day, 19, 0), 10_000 * RUB, interbank=True)
    ledger.anomaly(
        "own_transfer",
        "Переводы между своими картами в разных банках не являются расходом",
        external_ids=transfers[:4],
    )

    purchases = [
        t
        for t in ledger.txs
        if t.account == "spend"
        and t.category == "marketplace"
        and _known(ledger, t)
        and t.occurred_at.date() < today - timedelta(days=30)
    ]
    bought = _pick(ledger, purchases, "частичный возврат")
    refund = ledger.refund(
        bought, bought.occurred_at + timedelta(days=9), -bought.amount_minor // 2
    )
    ledger.anomaly(
        "refund_and_cancel",
        "Частичный возврат покупки",
        external_ids=[bought.external_id, refund.external_id],
    )

    # Дубли платежей с разными датами учёта: в выписке, но не в реальном остатке.
    candidates = [
        t
        for t in ledger.txs
        if t.account == "spend"
        and t.category == "groceries"
        and t.status == POSTED
        and today - timedelta(days=60) <= t.occurred_at.date() < today - timedelta(days=2)
    ]
    dupes: list[dict[str, Any]] = []
    for original in rng.sample(candidates, k=min(2, len(candidates))):
        copy = ledger.tx(
            "spend",
            original.occurred_at,
            original.amount_minor,
            original.type,
            original.category,
            description=original.description,
            booked_delay_days=(original.booked_at - original.occurred_at).days + 1,
        )
        ledger.duplicates.append(copy.external_id)
        dupes.append({"original": original.external_id, "duplicate": copy.external_id})
    ledger.anomaly(
        "duplicate_payment", "Платёж задвоен в выписке с другой датой учёта", pairs=dupes
    )

    # Частично отсутствующая история: 12 дней выписки Банка Б потеряны.
    gap_from = today - timedelta(days=130)
    gap_to = gap_from + timedelta(days=11)
    lost = [
        t
        for t in ledger.txs
        if t.account == "spend"
        and gap_from <= t.occurred_at.date() <= gap_to
        and t.transfer_group_id is None
        and t.external_id not in {bought.external_id, refund.external_id}
    ]
    for tx in lost:
        ledger.txs.remove(tx)
        ledger.missing.append(tx)
    ledger.partial_accounts.add("spend")
    ledger.anomaly(
        "partial_history",
        "В выписке Банка Б нет 12 дней операций; остаток банка их учитывает",
        account_id=ledger.account_id("spend"),
        date_from=gap_from.isoformat(),
        date_to=gap_to.isoformat(),
        missing_count=len(lost),
        missing_sum_minor=sum(t.amount_minor for t in lost),
    )

    ledger.set_openings({"main": 2_000_000, "spend": 300_000, "deposit": 30_000_000})

    # Повторная загрузка выписки: те же external_id ещё раз.
    month_ago = ledger.as_of - timedelta(days=30)
    ledger.reupload = [
        t for t in ledger.txs if t.account == "main" and month_ago <= t.occurred_at <= ledger.as_of
    ]
    ledger.anomaly(
        "statement_reupload",
        "Выписка Банка А за последний месяц загружена повторно",
        count=len(ledger.reupload),
    )


# --- 5. Семья (P2) -----------------------------------------------------------


def build_family(ledger: Ledger) -> None:
    ledger.add_account(AccountSpec("ivan", "Карта Ивана", "Банк А", "debit", owner="member_1"))
    ledger.add_account(AccountSpec("maria", "Карта Марии", "Банк Б", "debit", owner="member_2"))
    ledger.incomes = [
        IncomeSpec("salary_ivan", "Зарплата Ивана", "salary", "ivan", 25, 90_000 * RUB),
        IncomeSpec("salary_maria", "Зарплата Марии", "salary", "maria", 10, 60_000 * RUB),
    ]
    ledger.obligations = [
        ObligationSpec("rent", "rent", "Аренда квартиры (общая)", "ivan", 5, 50_000 * RUB),
        ObligationSpec("car_loan", "loan", "Автокредит Ивана", "ivan", 12, 30_000 * RUB),
        ObligationSpec("kindergarten", "manual", "Детский сад (общий)", "maria", 15, 8_000 * RUB),
        ObligationSpec(
            "gym",
            "subscription",
            "Спортзал Ивана",
            "ivan",
            20,
            2_500 * RUB,
            priority="normal",
            movable=True,
        ),
        ObligationSpec(
            "course",
            "subscription",
            "Курсы Марии",
            "maria",
            8,
            3_000 * RUB,
            priority="normal",
            movable=True,
        ),
    ]
    ledger.spending = [
        SpendSpec("groceries", "maria", 0.45, 1_200 * RUB, description="Супермаркет"),
        SpendSpec("cafe", "ivan", 0.25, 600 * RUB, description="Кафе"),
        SpendSpec("transport", "ivan", 0.6, 65 * RUB, sigma=0.2, description="Метро"),
        SpendSpec("kids", "maria", 0.12, 1_500 * RUB, description="Детские товары"),
        SpendSpec("marketplace", "ivan", 0.08, 2_500 * RUB, sigma=0.6, description="Маркетплейс"),
    ]
    ledger.simulate_regular()

    shared = {"rent", "kindergarten", "groceries", "kids"}
    for tx in ledger.txs:
        owner = ledger.accounts[tx.account].owner
        tx.extra["owner"] = owner
        tx.extra["visibility"] = "shared" if tx.category in shared else "private"
    # Мария переводит Ивану половину аренды — внутрисемейный перевод.
    for year, month in iter_months(ledger.history_from, ledger.horizon_end):
        day = clamp_day(year, month, 4)
        if ledger.history_from <= day <= ledger.horizon_end:
            out, inn = ledger.transfer("maria", "ivan", at(day, 20, 0), 25_000 * RUB)
            for tx in (out, inn):
                tx.extra.update(
                    {
                        "owner": ledger.accounts[tx.account].owner,
                        "visibility": "shared",
                        "scope": "household",
                    }
                )
    # Общая покупка с личной частью: часть чека видна только владельцу.
    split_examples: list[str] = []
    for tx in ledger.txs:
        if tx.category == "groceries" and tx.amount_minor <= -1_500 * RUB:
            private = (-tx.amount_minor) // 4
            tx.extra["split"] = {
                "shared_minor": -tx.amount_minor - private,
                "private_minor": private,
            }
            split_examples.append(tx.external_id)
    ledger.anomaly(
        "family_shared_private",
        "Общая семейная покупка с приватной частью",
        external_ids=split_examples[:5],
    )
    ledger.set_openings({"ivan": 1_000_000, "maria": 500_000})


# Регулярные платежи, которых нет в календаре: их подключает только учебный аккаунт
# (generate(..., unregistered=True)), фиксированные сценарии и эталонные числа не меняются.
UNREGISTERED: dict[str, tuple[RecurringSpec, ...]] = {
    "young_specialist": (
        RecurringSpec("Фитнес-клуб", "sport", "card", 2_900 * RUB, "monthly", 10),
        RecurringSpec("Облачное хранилище", "services", "card", 149 * RUB, "monthly", 18),
    ),
    "credit_card": (
        RecurringSpec("Курсы английского", "education", "debit", 4_500 * RUB, "monthly", 12),
    ),
    "freelancer": (
        RecurringSpec("Сервис для дизайна", "software", "card", 990 * RUB, "monthly", 8),
        RecurringSpec("Аренда склада", "services", "card", 1_800 * RUB, "monthly", 20, 150 * RUB),
    ),
    "two_banks": (
        RecurringSpec("Секция для ребёнка", "education", "main", 3_500 * RUB, "monthly", 6),
        RecurringSpec("Доставка воды", "household", "spend", 450 * RUB, "weekly", 0, 30 * RUB),
    ),
}

PROFILES: dict[str, ProfileInfo] = {
    info.id: info
    for info in (
        ProfileInfo(
            "young_specialist",
            "ys",
            "Молодой специалист",
            "Зарплата двумя частями, аренда и потребкредит, одна карта. Перед зарплатой "
            "остаток подходит к резерву.",
            "primary",
            True,
            "full",
            ("unexpected_expense", "salary_delay"),
            build_young_specialist,
        ),
        ProfileInfo(
            "credit_card",
            "cc",
            "Кредитная карта и рассрочка",
            "Повседневные траты по кредитке, погашение с дебетовой карты, рассрочка 31-го числа.",
            "secondary",
            True,
            "full",
            ("refund_and_cancel", "credit_purchase_and_payment", "day_31_short_month"),
            build_credit_card,
        ),
        ProfileInfo(
            "freelancer",
            "fl",
            "Фрилансер",
            "Неравномерные поступления от клиентов, налог самозанятого, наличные.",
            "secondary",
            True,
            "full",
            ("negative_balance", "unexpected_expense", "balance_mismatch"),
            build_freelancer,
        ),
        ProfileInfo(
            "two_banks",
            "tb",
            "Два банка",
            "Зарплата в одном банке, траты в другом, переводы, возвраты, неполная выписка.",
            "secondary",
            True,
            "partial",
            (
                "own_transfer",
                "refund_and_cancel",
                "duplicate_payment",
                "partial_history",
                "statement_reupload",
            ),
            build_two_banks,
        ),
        ProfileInfo(
            "family",
            "fm",
            "Семья (после MVP)",
            "Два участника с общими и личными обязательствами.",
            "family",
            False,
            "full",
            ("family_shared_private",),
            build_family,
        ),
    )
}
