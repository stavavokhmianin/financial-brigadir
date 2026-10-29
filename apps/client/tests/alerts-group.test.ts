import assert from "node:assert/strict";
import { test } from "node:test";

import { groupHidden, timesLabel } from "../src/features/alerts/logic.ts";

const hidden = (id: string, reason: string, risk_date: string | null, action = "suppress") => ({
  id,
  action,
  reason,
  reason_text: reason,
  risk_date,
});

test("groupHidden: одинаковые решения — одна строка со счётчиком", () => {
  const groups = groupHidden([
    hidden("a", "repeat", "2026-10-23"),
    hidden("b", "repeat", "2026-10-23"),
    hidden("c", "quiet_hours", "2026-10-23", "defer"),
    hidden("d", "repeat", "2026-10-23"),
    hidden("e", "repeat", "2026-10-26"),
  ]);
  assert.deepEqual(
    groups.map((g) => [g.first.id, g.count]),
    [
      ["a", 3],
      ["c", 1],
      ["e", 1],
    ],
  );
});

test("timesLabel: склонение «раз»", () => {
  assert.deepEqual(
    [2, 4, 5, 11, 12, 21, 22].map(timesLabel),
    ["2 раза", "4 раза", "5 раз", "11 раз", "12 раз", "21 раз", "22 раза"],
  );
});
