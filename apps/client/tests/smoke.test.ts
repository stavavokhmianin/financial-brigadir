import { test } from "node:test";
import assert from "node:assert/strict";

test("node test runner работает с TypeScript", () => {
  const value: number = 1;
  assert.equal(value, 1);
});
