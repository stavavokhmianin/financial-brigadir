// Симулятор покупки (раздел 11.3): сборка событий сценария и строки сравнения «до/после».

export type ScenarioEventInput =
  | { type: "expense"; amount_minor: number; date: string; label: string }
  | { type: "income_shift"; target_id: string; shift_days: number };

export interface SimulationInput {
  amountMinor: number | null;
  date: string;
  label: string;
  salaryId: string | null;
  delayDays: number;
}

/** События для POST /scenarios; пусто — считать нечего. */
export function buildEvents(input: SimulationInput): ScenarioEventInput[] {
  const events: ScenarioEventInput[] = [];
  if (input.amountMinor !== null && input.amountMinor > 0) {
    events.push({
      type: "expense",
      amount_minor: input.amountMinor,
      date: input.date,
      label: input.label.trim() || "Покупка",
    });
  }
  if (input.salaryId && input.delayDays !== 0) {
    events.push({ type: "income_shift", target_id: input.salaryId, shift_days: input.delayDays });
  }
  return events;
}

export interface ComparisonLike {
  risk_level_before: string;
  risk_level_after: string;
  risk_date_before?: string | null;
  risk_date_after?: string | null;
  days_below_reserve_before: number;
  days_below_reserve_after: number;
  base: { risk: { min_balance_minor: number; pessimistic_min_minor: number } };
  result: { risk: { min_balance_minor: number; pessimistic_min_minor: number } };
}

export type RowKind = "level" | "min" | "pessimistic" | "date" | "days";

export interface ComparisonRow {
  kind: RowKind;
  before: string | number | null;
  after: string | number | null;
  changed: boolean;
  worse: boolean;
}

const LEVEL_RANK: Record<string, number> = { low: 0, medium: 1, high: 2 };

export function comparisonRows(c: ComparisonLike): ComparisonRow[] {
  const minBefore = c.base.risk.min_balance_minor;
  const minAfter = c.result.risk.min_balance_minor;
  const pesBefore = c.base.risk.pessimistic_min_minor;
  const pesAfter = c.result.risk.pessimistic_min_minor;
  const dateBefore = c.risk_date_before ?? null;
  const dateAfter = c.risk_date_after ?? null;
  return [
    {
      kind: "level",
      before: c.risk_level_before,
      after: c.risk_level_after,
      changed: c.risk_level_before !== c.risk_level_after,
      worse: (LEVEL_RANK[c.risk_level_after] ?? 0) > (LEVEL_RANK[c.risk_level_before] ?? 0),
    },
    { kind: "min", before: minBefore, after: minAfter, changed: minAfter !== minBefore, worse: minAfter < minBefore },
    { kind: "pessimistic", before: pesBefore, after: pesAfter, changed: pesAfter !== pesBefore, worse: pesAfter < pesBefore },
    {
      kind: "date",
      before: dateBefore,
      after: dateAfter,
      changed: dateBefore !== dateAfter,
      // Риск появился или наступает раньше.
      worse: dateAfter !== null && (dateBefore === null || dateAfter < dateBefore),
    },
    {
      kind: "days",
      before: c.days_below_reserve_before,
      after: c.days_below_reserve_after,
      changed: c.days_below_reserve_before !== c.days_below_reserve_after,
      worse: c.days_below_reserve_after > c.days_below_reserve_before,
    },
  ];
}
