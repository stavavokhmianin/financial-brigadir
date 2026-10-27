import assert from "node:assert/strict";
import { test } from "node:test";

import { formatDateInput, parseDateInput, parseRubInput } from "../src/shared/input.ts";

test("parseRubInput: форматы суммы", () => {
  assert.deepEqual(parseRubInput("12 000,50"), { ok: true, value: 1_200_050 });
  assert.deepEqual(parseRubInput("12000.5"), { ok: true, value: 1_200_050 });
  assert.deepEqual(parseRubInput("55 000 ₽"), { ok: true, value: 5_500_000 });
  assert.deepEqual(parseRubInput("-500", true), { ok: true, value: -50_000 });
  assert.deepEqual(parseRubInput("0", true), { ok: true, value: 0 });
});

test("parseRubInput: ошибки", () => {
  for (const bad of ["", "abc", "1,234", "1.234", "-500", "0", "1e5"]) {
    assert.equal(parseRubInput(bad).ok, false, bad);
  }
  assert.equal(parseRubInput("99999999999").ok, false);
});

test("parseDateInput: русский и ISO форматы", () => {
  assert.deepEqual(parseDateInput("25.10.2026", "2026-10-19"), { ok: true, value: "2026-10-25" });
  assert.deepEqual(parseDateInput("5.11", "2026-10-19"), { ok: true, value: "2026-11-05" });
  assert.deepEqual(parseDateInput("01.02.27", "2026-10-19"), { ok: true, value: "2027-02-01" });
  assert.deepEqual(parseDateInput("2026-12-31", "2026-10-19"), { ok: true, value: "2026-12-31" });
});

test("parseDateInput: несуществующие даты отклоняются", () => {
  for (const bad of ["", "31.02.2027", "32.10.2026", "2026-13-01", "завтра"]) {
    assert.equal(parseDateInput(bad, "2026-10-19").ok, false, bad);
  }
});

test("formatDateInput", () => {
  assert.equal(formatDateInput("2026-10-25"), "25.10.2026");
});
