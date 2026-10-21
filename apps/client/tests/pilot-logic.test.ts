import assert from "node:assert/strict";
import { test } from "node:test";

import { canSubmit, normalizeCode } from "../src/features/pilot/logic.ts";

test("normalizeCode: регистр, пробелы и дефисы не важны", () => {
  assert.equal(normalizeCode(" abcd-efgh jkmn-pqrs "), "ABCDEFGHJKMNPQRS");
});

test("canSubmit: нужен полный код и принятые условия", () => {
  assert.equal(canSubmit("ABCD-EFGH-JKMN-PQRS", true), true);
  assert.equal(canSubmit("ABCD-EFGH-JKMN-PQRS", false), false);
  assert.equal(canSubmit("ABCD-EFGH", true), false);
});
