import assert from "node:assert/strict";
import { test } from "node:test";

import { describeAccount, upcoming, type Occurrence } from "../src/features/dashboard/logic.ts";

const item = (date: string, title: string, amount: number): Occurrence => ({
  obligation_id: `obl_${title}`,
  date,
  title,
  amount_minor: amount,
  status: "confirmed",
  priority: "critical",
});

test("upcoming: окно, сортировка и сумма", () => {
  const calendar = [
    item("2026-10-23", "Аренда", 3_000_000),
    item("2026-11-21", "Кредит", 1_200_000),
    item("2026-10-21", "Кредит", 1_200_000),
    item("2026-10-18", "Прошлое", 100),
  ];
  const result = upcoming(calendar, "2026-10-19", "2026-11-18");
  assert.deepEqual(
    result.items.map((i) => [i.date, i.title]),
    [
      ["2026-10-21", "Кредит"],
      ["2026-10-23", "Аренда"],
    ],
  );
  assert.equal(result.totalMinor, 4_200_000);
  assert.equal(calendar[0]?.title, "Аренда", "исходный массив не меняется");
});

test("describeAccount: кредитка — долг из лимита, вклад — вне ликвидности", () => {
  assert.deepEqual(
    describeAccount({
      type: "credit_card",
      available_balance_minor: -481_400,
      credit_limit_minor: 15_000_000,
      blocked_minor: 0,
      is_liquid: false,
    }),
    { kind: "credit", debtMinor: 481_400, limitMinor: 15_000_000 },
  );
  assert.deepEqual(
    describeAccount({
      type: "deposit",
      available_balance_minor: 30_000_000,
      blocked_minor: 0,
      is_liquid: false,
    }),
    { kind: "excluded", balanceMinor: 30_000_000 },
  );
  assert.deepEqual(
    describeAccount({
      type: "debit",
      available_balance_minor: -5_000,
      blocked_minor: 1_000,
      is_liquid: true,
    }),
    { kind: "liquid", balanceMinor: -5_000, blockedMinor: 1_000 },
  );
});
