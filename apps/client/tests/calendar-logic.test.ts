import assert from "node:assert/strict";
import { test } from "node:test";

import { buildCalendar } from "../src/features/calendar/logic.ts";

const localDate = (iso: string) => iso.slice(0, 10);

test("buildCalendar: группировка по дням и стиль событий", () => {
  const days = buildCalendar(
    [
      { id: "t1", occurred_at: "2026-10-18T10:00:00Z", amount_minor: -50_000, description: "Кафе", status: "posted", type: "expense" },
      { id: "t2", occurred_at: "2026-10-18T12:00:00Z", amount_minor: -1_000, status: "canceled", type: "expense" },
    ],
    [
      { obligation_id: "o1", date: "2026-10-21", title: "Кредит", amount_minor: 1_200_000, status: "confirmed" },
      { obligation_id: "o2", date: "2026-10-21", title: "Музыка", amount_minor: 39_900, status: "inferred" },
    ],
    [
      {
        income_id: "i1",
        date_from: "2026-10-25",
        date_to: "2026-10-28",
        title: "Зарплата",
        amount_min_minor: 6_000_000,
        amount_max_minor: 6_000_000,
        confirmed: true,
      },
    ],
    localDate,
  );
  assert.deepEqual(
    days.map((d) => d.date),
    ["2026-10-18", "2026-10-21", "2026-10-25"],
  );
  const [past, payments, salary] = days;
  assert.equal(past?.items.length, 1, "отменённая операция не показывается");
  assert.equal(past?.expectedNetMinor, 0, "прошедшие операции не входят в ожидаемое");
  assert.equal(payments?.expectedNetMinor, -1_239_900);
  assert.equal(payments?.items.find((i) => i.title === "Музыка")?.confirmableId, "o2");
  assert.equal(payments?.items.find((i) => i.title === "Кредит")?.confirmableId, undefined);
  assert.equal(salary?.items[0]?.windowTo, "2026-10-28");
  assert.equal(salary?.items[0]?.amountMaxMinor, undefined);
});
