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

export interface ScenarioDateRange {
  min: string;
  max: string;
}

function shiftIsoDate(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year ?? 0, (month ?? 1) - 1, (day ?? 1) + days))
    .toISOString()
    .slice(0, 10);
}

/** Покупка должна попадать в фактически отображаемые дни прогноза. */
export function scenarioDateRange(today: string, horizonDays: number): ScenarioDateRange {
  return { min: shiftIsoDate(today, 1), max: shiftIsoDate(today, horizonDays) };
}

export function isScenarioDateAllowed(date: string, today: string, horizonDays: number): boolean {
  const range = scenarioDateRange(today, horizonDays);
  return date >= range.min && date <= range.max;
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

export interface ScenarioVerdictLike {
  risk_level_after: string;
  worsened: boolean;
  result: {
    risk: {
      date?: string | null;
      shortfall_minor: number;
      explanation: string;
    };
  };
}

export type ScenarioVerdictKind = "fits" | "tight" | "shortfall";

export interface ScenarioVerdict {
  kind: ScenarioVerdictKind;
  date: string | null;
  shortfallMinor: number;
  explanation: string;
}

/**
 * Один пользовательский вердикт вместо нескольких технических карточек риска.
 * Текст и форматирование остаются в UI, чтобы расчётная логика не зависела от языка.
 */
export function scenarioVerdict(scenario: ScenarioVerdictLike): ScenarioVerdict {
  const level = scenario.risk_level_after;
  const kind: ScenarioVerdictKind =
    level === "high" ? "shortfall" : level === "medium" || scenario.worsened ? "tight" : "fits";
  return {
    kind,
    date: scenario.result.risk.date ?? null,
    shortfallMinor: Math.max(0, scenario.result.risk.shortfall_minor),
    explanation: scenario.result.risk.explanation,
  };
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
