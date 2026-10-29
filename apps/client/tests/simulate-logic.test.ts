import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildEvents,
  comparisonRows,
  isScenarioDateAllowed,
  scenarioDateRange,
} from "../src/features/simulate/logic.ts";

test("buildEvents: покупка, задержка зарплаты и их комбинация", () => {
  const base = { amountMinor: null, date: "2026-10-20", label: "", salaryId: "inc_1", delayDays: 0 };
  assert.deepEqual(buildEvents(base), []);
  assert.deepEqual(buildEvents({ ...base, amountMinor: 1_200_000 }), [
    { type: "expense", amount_minor: 1_200_000, date: "2026-10-20", label: "Покупка" },
  ]);
  assert.deepEqual(buildEvents({ ...base, delayDays: 2 }), [
    { type: "income_shift", target_id: "inc_1", shift_days: 2 },
  ]);
  const both = buildEvents({ ...base, amountMinor: 100, label: " Телефон ", delayDays: 5 });
  assert.equal(both.length, 2);
  assert.equal(both[0]?.type === "expense" && both[0].label, "Телефон");
  assert.deepEqual(buildEvents({ ...base, salaryId: null, delayDays: 2 }), []);
});

test("comparisonRows: что изменилось и стало ли хуже", () => {
  const rows = comparisonRows({
    risk_level_before: "medium",
    risk_level_after: "high",
    risk_date_before: "2026-10-23",
    risk_date_after: "2026-10-21",
    days_below_reserve_before: 0,
    days_below_reserve_after: 3,
    base: { risk: { min_balance_minor: 652_965, pessimistic_min_minor: -526_340 } },
    result: { risk: { min_balance_minor: -547_035, pessimistic_min_minor: -1_726_340 } },
  });
  const byKind = Object.fromEntries(rows.map((r) => [r.kind, r]));
  assert.equal(byKind.level?.worse, true);
  assert.equal(byKind.min?.after, -547_035);
  assert.equal(byKind.date?.worse, true, "риск наступает раньше");
  assert.equal(byKind.days?.changed, true);

  const same = comparisonRows({
    risk_level_before: "low",
    risk_level_after: "low",
    risk_date_before: null,
    risk_date_after: null,
    days_below_reserve_before: 0,
    days_below_reserve_after: 0,
    base: { risk: { min_balance_minor: 10, pessimistic_min_minor: 5 } },
    result: { risk: { min_balance_minor: 10, pessimistic_min_minor: 5 } },
  });
  assert.ok(same.every((r) => !r.changed && !r.worse));
});

test("scenarioDateRange: сценарий ограничен отображаемым горизонтом", () => {
  assert.deepEqual(scenarioDateRange("2026-10-19", 30), {
    min: "2026-10-20",
    max: "2026-11-18",
  });
  assert.equal(isScenarioDateAllowed("2026-10-19", "2026-10-19", 30), false);
  assert.equal(isScenarioDateAllowed("2026-10-20", "2026-10-19", 30), true);
  assert.equal(isScenarioDateAllowed("2026-11-18", "2026-10-19", 30), true);
  assert.equal(isScenarioDateAllowed("2026-11-19", "2026-10-19", 30), false);
});
