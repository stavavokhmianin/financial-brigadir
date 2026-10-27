import assert from "node:assert/strict";
import { test } from "node:test";

import { QUIET_PRESETS, quietPresetOf } from "../src/features/alerts/logic.ts";

test("quietPresetOf: сохранённая пара → пресет", () => {
  assert.equal(quietPresetOf(null, null), "off");
  assert.equal(quietPresetOf("22:00:00", "08:00:00"), "night");
  assert.equal(quietPresetOf("23:00", "09:00"), "late");
  assert.equal(quietPresetOf("21:30:00", "07:00:00"), "night");
  assert.deepEqual(QUIET_PRESETS.off, [null, null]);
});
