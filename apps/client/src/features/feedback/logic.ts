// Чистая логика блока «Помогите уточнить прогноз»: без React, проверяется node --test.

export type TxLabel = "mandatory" | "regular" | "reducible" | "one_off";
export type RiskLevel = "low" | "medium" | "high";

export interface Glance {
  risk_level: RiskLevel;
  min_balance_minor: number;
  pessimistic_min_minor: number;
}

export interface EffectLike {
  before: Glance;
  after: Glance;
}

export type EffectLine =
  | { kind: "risk"; from: RiskLevel; to: RiskLevel }
  | { kind: "minimum" | "pessimistic"; from: string; to: string; up: boolean };

/**
 * Что изменилось в прогнозе после метки. Суммы сравниваются уже округлёнными:
 * разница, которая не видна в «≈ 5 000 ₽», пользователю не показывается.
 */
export function effectLines(effect: EffectLike, approx: (minor: number) => string): EffectLine[] {
  const { before, after } = effect;
  const lines: EffectLine[] = [];
  if (before.risk_level !== after.risk_level) {
    lines.push({ kind: "risk", from: before.risk_level, to: after.risk_level });
  }
  const pairs = [
    ["minimum", before.min_balance_minor, after.min_balance_minor],
    ["pessimistic", before.pessimistic_min_minor, after.pessimistic_min_minor],
  ] as const;
  for (const [kind, from, to] of pairs) {
    const shownFrom = approx(from);
    const shownTo = approx(to);
    if (shownFrom !== shownTo) {
      lines.push({ kind, from: shownFrom, to: shownTo, up: to > from });
    }
  }
  return lines;
}

/** Новые операции с прошлого опроса — повод обновить главный экран. */
export function arrived(previousTotal: number | null, total: number): number {
  return previousTotal === null ? 0 : Math.max(0, total - previousTotal);
}

/**
 * Наступили другие учебные сутки (в часовом поясе пользователя, Москва — +180 минут).
 * Даже без новых операций у прогноза сменилось «сегодня» — главную пора обновить.
 */
export function dayChanged(previousIso: string, nextIso: string, utcOffsetMinutes = 180): boolean {
  const day = (iso: string) => Math.floor((Date.parse(iso) / 60_000 + utcOffsetMinutes) / 1_440);
  return day(previousIso) !== day(nextIso);
}

/** Регулярность кандидата словами (ADR-0006: без процентов). */
export function regularity(confidence: number): "sure" | "likely" {
  return confidence >= 0.85 ? "sure" : "likely";
}
