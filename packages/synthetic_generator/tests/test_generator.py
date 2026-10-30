import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from synthetic_generator import DEFAULT_AS_OF, PROFILES, generate, list_profiles
from synthetic_generator.cli import main as cli_main
from synthetic_generator.dates import is_short_month

REQUIRED_ANOMALIES = {
    "salary_delay",
    "unexpected_expense",
    "statement_reupload",
    "refund_and_cancel",
    "own_transfer",
    "credit_purchase_and_payment",
    "day_31_short_month",
    "negative_balance",
    "partial_history",
    "duplicate_payment",
    "balance_mismatch",
    "family_shared_private",
}
TX_KEYS = {
    "transaction_id", "account_id", "occurred_at", "booked_at", "amount_minor", "currency",
    "type", "category", "status", "source", "external_id", "description",
    "transfer_group_id", "related_external_id",
}  # fmt: skip

DATASETS = {pid: generate(pid) for pid in PROFILES}


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _counts(data: dict[str, Any], tx: dict[str, Any]) -> bool:
    return tx["status"] == "posted" and tx["external_id"] not in set(
        data["truth"]["duplicate_external_ids"]
    )


def _running(data: dict[str, Any], account_id: str) -> list[tuple[datetime, int]]:
    """Истинный остаток счёта после каждой операции истории."""
    txs = [
        t
        for t in data["known"]["transactions"] + data["truth"]["missing_transactions"]
        if t["account_id"] == account_id and _counts(data, t)
    ]
    balance = data["truth"]["opening_balances"][account_id]
    points = []
    for tx in sorted(txs, key=lambda t: (_dt(t["occurred_at"]), t["external_id"])):
        balance += tx["amount_minor"]
        points.append((_dt(tx["occurred_at"]), balance))
    return points


def test_at_least_five_profile_types() -> None:
    profiles = list_profiles()
    assert len(profiles) >= 5
    assert {p["id"] for p in profiles} == set(PROFILES)
    assert [p["id"] for p in profiles if not p["mvp"]] == ["family"]


@pytest.mark.parametrize("profile_id", list(PROFILES))
def test_reproducible_for_same_seed(profile_id: str) -> None:
    first = json.dumps(generate(profile_id, seed=7), sort_keys=True)
    second = json.dumps(generate(profile_id, seed=7), sort_keys=True)
    other = json.dumps(generate(profile_id, seed=8), sort_keys=True)
    assert first == second
    assert first != other


@pytest.mark.parametrize("profile_id", list(PROFILES))
def test_known_never_leaks_future(profile_id: str) -> None:
    data = DATASETS[profile_id]
    as_of = _dt(data["as_of"])
    horizon_end = date.fromisoformat(data["horizon_end"])
    assert all(_dt(t["occurred_at"]) <= as_of for t in data["known"]["transactions"])
    hidden = data["hidden_future"]["transactions"]
    assert hidden, "скрытое будущее должно быть непустым"
    assert all(as_of < _dt(t["occurred_at"]) for t in hidden)
    assert all(_dt(t["occurred_at"]).date() <= horizon_end for t in hidden)
    for obligation in data["known"]["obligations"]:
        assert date.fromisoformat(obligation["due_date"]) > as_of.date()


@pytest.mark.parametrize("profile_id", list(PROFILES))
def test_history_length_is_6_to_12_months(profile_id: str) -> None:
    data = DATASETS[profile_id]
    first = min(_dt(t["occurred_at"]) for t in data["known"]["transactions"])
    days = (_dt(data["as_of"]) - first).days
    assert 6 * 28 <= days <= 12 * 31


@pytest.mark.parametrize("profile_id", list(PROFILES))
def test_unified_transaction_contract(profile_id: str) -> None:
    data = DATASETS[profile_id]
    for tx in data["known"]["transactions"] + data["hidden_future"]["transactions"]:
        assert TX_KEYS <= set(tx)
        assert isinstance(tx["amount_minor"], int) and tx["amount_minor"] != 0
        assert tx["currency"] == "RUB"
        assert tx["status"] in {"posted", "pending", "canceled"}
        assert _dt(tx["occurred_at"]).tzinfo is not None
        assert _dt(tx["booked_at"]) >= _dt(tx["occurred_at"])
    ids = [t["external_id"] for t in data["known"]["transactions"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("profile_id", list(PROFILES))
def test_balance_equals_opening_plus_true_history(profile_id: str) -> None:
    data = DATASETS[profile_id]
    for account in data["known"]["accounts"]:
        points = _running(data, account["account_id"])
        final = (
            points[-1][1] if points else data["truth"]["opening_balances"][account["account_id"]]
        )
        assert final == account["balance_minor"], account["account_id"]


@pytest.mark.parametrize("profile_id", list(PROFILES))
def test_transfers_and_card_payments_net_to_zero(profile_id: str) -> None:
    data = DATASETS[profile_id]
    own_accounts = {a["account_id"] for a in data["known"]["accounts"]}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tx in data["known"]["transactions"] + data["hidden_future"]["transactions"]:
        if tx["transfer_group_id"]:
            groups[tx["transfer_group_id"]].append(tx)
    for group_id, txs in groups.items():
        if len(txs) == 1:
            # вторая сторона перевода, начатого до as_of, может прийти уже после
            continue
        assert len(txs) == 2, group_id
        assert sum(t["amount_minor"] for t in txs) == 0, group_id
        assert {t["account_id"] for t in txs} <= own_accounts
        assert {t["type"] for t in txs} in ({"transfer_out", "transfer_in"}, {"credit_payment"})


@pytest.mark.parametrize("profile_id", list(PROFILES))
def test_refunds_reference_original_purchase(profile_id: str) -> None:
    data = DATASETS[profile_id]
    all_txs = data["known"]["transactions"] + data["truth"]["missing_transactions"]
    by_id = {t["external_id"]: t for t in all_txs}
    for tx in all_txs:
        if tx["type"] != "refund":
            continue
        original = by_id[tx["related_external_id"]]
        assert original["account_id"] == tx["account_id"]
        assert 0 < tx["amount_minor"] <= -original["amount_minor"]


@pytest.mark.parametrize("profile_id", [p for p in PROFILES if p != "freelancer"])
def test_no_unplanned_overdraft(profile_id: str) -> None:
    data = DATASETS[profile_id]
    for account in data["known"]["accounts"]:
        if account["type"] == "credit_card":
            continue
        assert min(b for _, b in _running(data, account["account_id"])) >= 0


def test_all_required_anomalies_are_present() -> None:
    produced: set[str] = set()
    for profile_id, info in PROFILES.items():
        types = {a["type"] for a in DATASETS[profile_id]["anomalies"]}
        assert set(info.anomalies) <= types, profile_id
        produced |= types
    assert produced >= REQUIRED_ANOMALIES


def _anomaly(profile_id: str, type_: str) -> dict[str, Any]:
    return next(a for a in DATASETS[profile_id]["anomalies"] if a["type"] == type_)


def _tx(profile_id: str, external_id: str) -> dict[str, Any]:
    data = DATASETS[profile_id]
    return next(
        t
        for t in data["known"]["transactions"] + data["hidden_future"]["transactions"]
        if t["external_id"] == external_id
    )


def test_salary_delay() -> None:
    anomaly = _anomaly("young_specialist", "salary_delay")
    [external_id] = anomaly["external_ids"]
    actual = _dt(_tx("young_specialist", external_id)["occurred_at"]).date()
    assert (actual - date.fromisoformat(anomaly["expected_date"])).days == 3


def test_day_31_payment_moves_to_last_day_of_short_month() -> None:
    data = DATASETS["credit_card"]
    installments = [t for t in data["known"]["transactions"] if t["category"] == "installment"]
    assert installments
    for tx in installments:
        day = _dt(tx["occurred_at"]).date()
        assert (day + timedelta(days=1)).day == 1, "списание должно быть в последний день месяца"
    assert any(is_short_month(_dt(t["occurred_at"]).date()) for t in installments)


def test_credit_card_debt_is_not_liquidity() -> None:
    data = DATASETS["credit_card"]
    card = next(a for a in data["known"]["accounts"] if a["type"] == "credit_card")
    assert card["is_liquid"] is False
    assert card["balance_minor"] <= 0
    purchases = [t for t in data["known"]["transactions"] if t["type"] == "credit_purchase"]
    assert {t["account_id"] for t in purchases} == {card["account_id"]}
    payment = next(o for o in data["known"]["obligations"] if o["kind"] == "credit_card")
    assert payment["amount_minor"] == -card["balance_minor"]


def test_overdraft_goes_negative_and_recovers() -> None:
    data = DATASETS["freelancer"]
    account_id = "acc_fl_card"
    balances = [b for _, b in _running(data, account_id)]
    assert min(balances) < 0
    assert balances[-1] > 0


def test_partial_history_gap() -> None:
    data = DATASETS["two_banks"]
    anomaly = _anomaly("two_banks", "partial_history")
    start = date.fromisoformat(anomaly["date_from"])
    end = date.fromisoformat(anomaly["date_to"])
    in_gap = [
        t
        for t in data["known"]["transactions"]
        if t["account_id"] == anomaly["account_id"]
        and start <= _dt(t["occurred_at"]).date() <= end
        and not t["transfer_group_id"]
    ]
    assert in_gap == []
    assert anomaly["missing_count"] == len(data["truth"]["missing_transactions"]) > 0
    account = next(a for a in data["known"]["accounts"] if a["account_id"] == anomaly["account_id"])
    assert account["is_partial"] is True


def test_duplicate_payment_has_other_booking_date() -> None:
    anomaly = _anomaly("two_banks", "duplicate_payment")
    assert anomaly["pairs"]
    for pair in anomaly["pairs"]:
        original = _tx("two_banks", pair["original"])
        duplicate = _tx("two_banks", pair["duplicate"])
        assert original["amount_minor"] == duplicate["amount_minor"]
        assert original["occurred_at"] == duplicate["occurred_at"]
        assert original["booked_at"] != duplicate["booked_at"]
        assert original["external_id"] != duplicate["external_id"]


def test_statement_reupload_repeats_known_ids() -> None:
    data = DATASETS["two_banks"]
    known_ids = {t["external_id"] for t in data["known"]["transactions"]}
    reupload = data["known"]["reupload"]
    assert reupload
    assert {t["external_id"] for t in reupload} <= known_ids


def test_manual_balance_mismatch() -> None:
    data = DATASETS["freelancer"]
    [(account_id, manual)] = data["known"]["manual_balances"].items()
    imported = next(a for a in data["known"]["accounts"] if a["account_id"] == account_id)
    assert manual != imported["balance_minor"]


def test_family_split_and_visibility() -> None:
    data = DATASETS["family"]
    txs = data["known"]["transactions"]
    assert all(t["extra"]["visibility"] in {"shared", "private"} for t in txs)
    split = [t for t in txs if "split" in t["extra"]]
    assert split
    for tx in split:
        parts = tx["extra"]["split"]
        assert parts["shared_minor"] + parts["private_minor"] == -tx["amount_minor"]
        assert parts["private_minor"] > 0


def test_golden_demo_story_young_specialist() -> None:
    """Эталон для демо 16.4: остаток, обязательства до зарплаты и её задержка."""
    data = DATASETS["young_specialist"]
    assert data["as_of"] == DEFAULT_AS_OF.isoformat()
    [card] = data["known"]["accounts"]
    assert card["balance_minor"] == 5_500_000
    before_salary = [
        (o["due_date"], o["amount_minor"])
        for o in data["known"]["obligations"]
        if o["due_date"] < "2026-10-25"
    ]
    assert before_salary == [("2026-10-21", 1_200_000), ("2026-10-23", 3_000_000)]
    salary = next(i for i in data["known"]["incomes"] if i["kind"] == "salary")
    assert (salary["date_from"], salary["date_to"]) == ("2026-10-25", "2026-10-28")
    [event] = data["hidden_future"]["events"]
    assert (event["expected_date"], event["actual_date"]) == ("2026-10-25", "2026-10-27")


def test_rejects_bad_arguments() -> None:
    with pytest.raises(KeyError):
        generate("nobody")
    with pytest.raises(ValueError):
        generate("young_specialist", months=5)
    with pytest.raises(ValueError):
        generate("young_specialist", months=13)


def test_cli_writes_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["--list"]) == 0
    assert "young_specialist" in capsys.readouterr().out
    out = tmp_path / "profile.json"
    assert cli_main(["two_banks", "--seed", "3", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["profile"]["id"] == "two_banks"
    assert data["seed"] == 3


def test_unregistered_payments_only_for_training_account() -> None:
    """Незаведённые регулярные платежи — только по флагу; без него профиль прежний."""
    plain = generate("young_specialist", seed=42)
    assert plain == generate("young_specialist", seed=42, unregistered=False)
    live = generate("young_specialist", seed=42, unregistered=True)
    titles = {t["description"] for t in live["known"]["transactions"]}
    assert {"Фитнес-клуб", "Облачное хранилище"} <= titles
    assert not {"Фитнес-клуб", "Облачное хранилище"} & {
        t["description"] for t in plain["known"]["transactions"]
    }
    # В календаре их нет: их должен найти поиск повторений.
    assert "Фитнес-клуб" not in {o["title"] for o in live["known"]["obligations"]}
    # Остаток на дату выгрузки тот же: входящий остаток подобран под цель профиля.
    assert (
        live["known"]["accounts"][0]["balance_minor"]
        == plain["known"]["accounts"][0]["balance_minor"]
    )
