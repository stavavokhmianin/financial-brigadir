// Календарь (раздел 11.2): прошедшие и ожидаемые события разным стилем.

export type CalendarKind = "past" | "obligation" | "income";

export interface CalendarItem {
  key: string;
  kind: CalendarKind;
  title: string;
  /** Знак: поступление > 0, списание < 0. Для дохода с диапазоном — нижняя граница. */
  amountMinor: number;
  amountMaxMinor?: number;
  status: string;
  /** id обязательства, которое можно подтвердить или отклонить. */
  confirmableId?: string;
  windowTo?: string;
}

export interface CalendarDay {
  date: string;
  items: CalendarItem[];
  expectedNetMinor: number;
}

export interface PastTx {
  id: string;
  occurred_at: string;
  amount_minor: number;
  description?: string | null;
  category?: string | null;
  status: string;
  type: string;
}

export interface ObligationEntry {
  obligation_id: string;
  date: string;
  title: string;
  amount_minor: number;
  status: string;
}

export interface IncomeEntry {
  income_id: string;
  date_from: string;
  date_to: string;
  title: string;
  amount_min_minor: number;
  amount_max_minor: number;
  confirmed: boolean;
}

const KIND_ORDER: Record<CalendarKind, number> = { past: 0, income: 1, obligation: 2 };

export function buildCalendar(
  past: readonly PastTx[],
  obligations: readonly ObligationEntry[],
  incomes: readonly IncomeEntry[],
  localDateOf: (iso: string) => string,
): CalendarDay[] {
  const days = new Map<string, CalendarItem[]>();
  const push = (date: string, item: CalendarItem) => {
    const list = days.get(date) ?? [];
    list.push(item);
    days.set(date, list);
  };
  for (const tx of past) {
    if (tx.status === "canceled") continue;
    push(localDateOf(tx.occurred_at), {
      key: `tx-${tx.id}`,
      kind: "past",
      title: tx.description || tx.category || tx.type,
      amountMinor: tx.amount_minor,
      status: tx.status,
    });
  }
  for (const o of obligations) {
    push(o.date, {
      key: `obl-${o.obligation_id}-${o.date}`,
      kind: "obligation",
      title: o.title,
      amountMinor: -o.amount_minor,
      status: o.status,
      confirmableId: o.status === "inferred" ? o.obligation_id : undefined,
    });
  }
  for (const i of incomes) {
    push(i.date_from, {
      key: `inc-${i.income_id}-${i.date_from}`,
      kind: "income",
      title: i.title,
      amountMinor: i.amount_min_minor,
      amountMaxMinor: i.amount_max_minor !== i.amount_min_minor ? i.amount_max_minor : undefined,
      status: i.confirmed ? "confirmed" : "expected",
      windowTo: i.date_to !== i.date_from ? i.date_to : undefined,
    });
  }
  return [...days.entries()]
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([date, items]) => ({
      date,
      items: items.sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind]),
      expectedNetMinor: items
        .filter((item) => item.kind !== "past")
        .reduce((sum, item) => sum + item.amountMinor, 0),
    }));
}
