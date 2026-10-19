import assert from "node:assert/strict";
import { test } from "node:test";

import {
  addDays,
  formatDay,
  formatMoment,
  formatRub,
  localDate,
  plural,
} from "../src/shared/format.ts";

const NBSP = " ";

test("formatRub: копейки → рубли с неразрывными пробелами", () => {
  assert.equal(formatRub(5_500_000), `55${NBSP}000${NBSP}₽`);
  assert.equal(formatRub(-145_050), `−1${NBSP}450,50${NBSP}₽`);
  assert.equal(formatRub(7), `0,07${NBSP}₽`);
  assert.equal(formatRub(0), `0${NBSP}₽`);
  assert.equal(formatRub(123_456_789_00), `123${NBSP}456${NBSP}789${NBSP}₽`);
});

test("formatRub: дробные значения отвергаются", () => {
  assert.throws(() => formatRub(1.5), RangeError);
  assert.throws(() => formatRub(Number.NaN), RangeError);
});

test("formatDay и formatMoment", () => {
  assert.equal(formatDay("2026-10-21"), "21 октября");
  assert.equal(formatDay("2027-01-31", 2026), "31 января 2027");
  assert.equal(formatMoment("2026-10-19T07:00:00Z"), "19 октября, 10:00");
  assert.equal(formatMoment("2026-10-19T10:00:00+03:00"), "19 октября, 10:00");
  assert.throws(() => formatDay("19.10.2026"), RangeError);
});

test("localDate учитывает часовой пояс", () => {
  assert.equal(localDate("2026-10-18T22:30:00Z"), "2026-10-19");
  assert.equal(localDate("2026-10-18T20:30:00Z"), "2026-10-18");
});

test("addDays переходит через границы месяца и года", () => {
  assert.equal(addDays("2026-10-19", 30), "2026-11-18");
  assert.equal(addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(addDays("2028-02-28", 1), "2028-02-29");
});

test("plural", () => {
  const forms = ["день", "дня", "дней"] as const;
  assert.equal(plural(1, forms), "день");
  assert.equal(plural(3, forms), "дня");
  assert.equal(plural(11, forms), "дней");
  assert.equal(plural(21, forms), "день");
  assert.equal(plural(25, forms), "дней");
});
