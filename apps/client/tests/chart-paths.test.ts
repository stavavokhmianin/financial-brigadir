import assert from "node:assert/strict";
import { test } from "node:test";

import { chartGeometry, chartPaths, smoothPath } from "../src/features/forecast/logic.ts";

const p = (day: string, p10: number, p50: number, p90: number) => ({
  day,
  p10_minor: p10,
  p50_minor: p50,
  p90_minor: p90,
});

test("smoothPath: проходит через крайние точки кубическими кривыми", () => {
  const d = smoothPath([0, 50, 100], [10, 40, 20]);
  assert.ok(d.startsWith("M0.0,10.0"));
  assert.equal((d.match(/C/g) ?? []).length, 2);
  assert.ok(d.endsWith("100.0,20.0"));
});

test("chartPaths: коридор замкнут, минимум — самый низкий p50, ширина соблюдена", () => {
  const points = [p("2026-10-20", 800, 1000, 1200), p("2026-10-21", 100, 300, 500), p("2026-10-22", 700, 900, 1100)];
  const paths = chartPaths(chartGeometry(points, 500, 100), 300);
  assert.deepEqual(paths.xs, [0, 150, 300]);
  assert.equal(paths.minIndex, 1);
  assert.ok(paths.band.startsWith("M0.0,") && paths.band.endsWith(" Z"));
  assert.equal(paths.compare, null);
});

test("chartPaths: линия сравнения, когда передан прогноз «до»", () => {
  const points = [p("2026-10-20", 800, 1000, 1200), p("2026-10-21", 600, 800, 1000)];
  const compare = [p("2026-10-20", 0, 1100, 0), p("2026-10-21", 0, 1000, 0)];
  const paths = chartPaths(chartGeometry(points, 500, 100, compare), 200);
  assert.ok(paths.compare?.startsWith("M0.0,"));
});
