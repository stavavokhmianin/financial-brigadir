import assert from "node:assert/strict";
import { test } from "node:test";

import { chartGeometry, keyDays, riskTone } from "../src/features/forecast/logic.ts";

const point = (day: string, p10: number, p50: number, p90: number, inflow = 0, outflow = 0) => ({
  day,
  p10_minor: p10,
  p50_minor: p50,
  p90_minor: p90,
  inflow_minor: inflow,
  outflow_minor: outflow,
});

test("chartGeometry: общая шкала, резерв, ноль и ниже резерва", () => {
  const points = [point("2026-10-20", 900, 1000, 1100), point("2026-10-21", -200, 100, 300)];
  const geometry = chartGeometry(points, 500, 100);
  const [first, second] = geometry.bars;
  assert.ok(first && second);
  assert.ok(first.rangeTop < second.rangeTop, "больший остаток выше на графике");
  assert.ok(first.mid >= first.rangeTop && first.mid <= first.rangeTop + first.rangeHeight);
  assert.equal(first.belowReserve, false);
  assert.equal(second.belowReserve, true);
  assert.ok(geometry.zeroY !== null && geometry.zeroY > geometry.reserveY);
  assert.ok(geometry.minValue < -200 && geometry.maxValue > 1100);
});

test("chartGeometry: плоский прогноз не делит на ноль", () => {
  const geometry = chartGeometry([point("2026-10-20", 500, 500, 500)], 500, 100);
  assert.ok(Number.isFinite(geometry.reserveY));
  assert.equal(geometry.zeroY, null);
  assert.ok((geometry.bars[0]?.rangeHeight ?? 0) >= 2);
});

test("chartGeometry: слой «до» на общей шкале", () => {
  const after = [point("2026-10-20", 100, 200, 300)];
  const before = [point("2026-10-20", 1000, 1200, 1300)];
  const geometry = chartGeometry(after, 0, 100, before);
  const [bar] = geometry.bars;
  assert.ok(bar && bar.compareMid !== null && bar.compareMid < bar.mid, "«до» выше на графике");
  assert.ok(geometry.maxValue > 1200, "шкала учитывает оба сценария");
  assert.equal(chartGeometry(after, 0, 100).bars[0]?.compareMid, null);
});

test("riskTone", () => {
  assert.equal(riskTone("high"), "danger");
  assert.equal(riskTone("medium"), "warning");
  assert.equal(riskTone("low"), "ok");
});

test("keyDays: события, дата риска и минимум", () => {
  const points = [
    point("2026-10-20", 0, 0, 0),
    point("2026-10-21", 0, 0, 0, 0, 1_200_000),
    point("2026-10-22", 0, 0, 0),
    point("2026-10-24", 0, 0, 0),
    point("2026-10-25", 0, 0, 0, 6_000_000, 0),
  ];
  const days = keyDays(points, "2026-10-22", "2026-10-24").map((p) => p.day);
  assert.deepEqual(days, ["2026-10-21", "2026-10-22", "2026-10-24", "2026-10-25"]);
});
