import assert from "node:assert/strict";
import { test } from "node:test";

import {
  arrived,
  dayChanged,
  effectLines,
  regularity,
  type Glance,
} from "../src/features/feedback/logic.ts";
import { formatRubApprox } from "../src/shared/format.ts";

const glance = (risk: Glance["risk_level"], min: number, bad: number): Glance => ({
  risk_level: risk,
  min_balance_minor: min,
  pessimistic_min_minor: bad,
});

test("метка, которая ничего не меняет на экране, не даёт строк", () => {
  // 52 340 ₽ и 52 410 ₽ округляются одинаково — разницы пользователь не увидит.
  const lines = effectLines(
    { before: glance("low", 5_234_000, 3_000_000), after: glance("low", 5_241_000, 3_000_000) },
    formatRubApprox,
  );
  assert.deepEqual(lines, []);
});

test("видны смена риска и сдвиги минимумов в обоих сценариях", () => {
  const lines = effectLines(
    { before: glance("medium", 650_000, 180_000), after: glance("low", 820_000, 560_000) },
    formatRubApprox,
  );
  assert.deepEqual(lines, [
    { kind: "risk", from: "medium", to: "low" },
    { kind: "minimum", from: formatRubApprox(650_000), to: formatRubApprox(820_000), up: true },
    {
      kind: "pessimistic",
      from: formatRubApprox(180_000),
      to: formatRubApprox(560_000),
      up: true,
    },
  ]);
});

test("снижение прогноза помечено как движение вниз", () => {
  const [line] = effectLines(
    { before: glance("low", 900_000, 600_000), after: glance("low", 700_000, 600_000) },
    formatRubApprox,
  );
  assert.equal(line?.kind, "minimum");
  assert.equal(line && "up" in line ? line.up : null, false);
});

test("новые операции считаются только после первого опроса", () => {
  assert.equal(arrived(null, 12), 0);
  assert.equal(arrived(12, 15), 3);
  assert.equal(arrived(15, 15), 0);
});

test("смена учебных суток считается по московскому времени", () => {
  // 20:59 UTC — ещё 23:59 по Москве, 21:01 UTC — уже следующие сутки.
  assert.equal(dayChanged("2026-10-19T07:00:00Z", "2026-10-19T20:59:00Z"), false);
  assert.equal(dayChanged("2026-10-19T20:59:00Z", "2026-10-19T21:01:00Z"), true);
  assert.equal(dayChanged("2026-10-19T07:00:00Z", "2026-10-20T07:10:00Z"), true);
});

test("регулярность словами, без процентов", () => {
  assert.equal(regularity(1), "sure");
  assert.equal(regularity(0.85), "sure");
  assert.equal(regularity(0.7), "likely");
});
