import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { riskScale, riskShift } from "../src/features/forecast/logic.ts";

test("riskScale: три ступени, активна текущая", () => {
  const steps = riskScale("medium");
  assert.deepEqual(
    steps.map((s) => [s.level, s.active, s.previous]),
    [
      ["low", false, false],
      ["medium", true, false],
      ["high", false, false],
    ],
  );
});

test("riskScale: отметка «было» только при изменении уровня", () => {
  assert.deepEqual(
    riskScale("high", "medium").map((s) => s.previous),
    [false, true, false],
  );
  assert.ok(riskScale("high", "high").every((s) => !s.previous));
});

test("riskShift: направление изменения уровня", () => {
  assert.equal(riskShift("medium", "high"), "up");
  assert.equal(riskShift("high", "low"), "down");
  assert.equal(riskShift("low", "low"), "same");
});

// ADR-0006: вероятности есть в API, но интерфейс их не показывает.
test("экраны не используют вероятностные поля API", () => {
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (/\.tsx?$/.test(name) && !name.endsWith(".d.ts")) files.push(path);
    }
  };
  walk(join(import.meta.dirname, "..", "src"));
  walk(join(import.meta.dirname, "..", "app"));
  const offenders = files.filter((file) =>
    /gap_probability|risk_probability/.test(readFileSync(file, "utf-8")),
  );
  assert.deepEqual(offenders, []);
});
