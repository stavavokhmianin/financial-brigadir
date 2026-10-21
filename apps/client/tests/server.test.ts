import assert from "node:assert/strict";
import { test } from "node:test";

import { normalizeServerUrl, pointsToDevice } from "../src/shared/server.ts";

test("normalizeServerUrl: дописывает схему и убирает лишний слэш", () => {
  assert.equal(normalizeServerUrl(" 192.168.1.5:8000/ "), "http://192.168.1.5:8000");
  assert.equal(normalizeServerUrl("HTTPS://stand.example.ru"), "https://stand.example.ru");
  assert.equal(normalizeServerUrl("http://localhost:8000"), "http://localhost:8000");
});

test("normalizeServerUrl: отвергает мусор и пути", () => {
  for (const bad of ["", "ftp://host", "http://host/api", "192.168.1.5:80000", "host name"]) {
    assert.equal(normalizeServerUrl(bad), null, bad);
  }
});

test("pointsToDevice: адрес самого телефона", () => {
  assert.equal(pointsToDevice("http://127.0.0.1:8000"), true);
  assert.equal(pointsToDevice("http://localhost:8000"), true);
  assert.equal(pointsToDevice("http://192.168.1.5:8000"), false);
});
