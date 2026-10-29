// Пресеты тихих часов: сервер хранит пару времени, клиент предлагает понятные варианты.

export type QuietPreset = "off" | "night" | "late";

export const QUIET_PRESETS: Record<QuietPreset, [string | null, string | null]> = {
  off: [null, null],
  night: ["22:00:00", "08:00:00"],
  late: ["23:00:00", "09:00:00"],
};

const short = (value: string | null): string | null => (value ? value.slice(0, 5) : null);

/** Какой пресет соответствует сохранённой паре; нестандартная пара считается «ночью». */
export function quietPresetOf(start: string | null, end: string | null): QuietPreset {
  if (!start || !end) return "off";
  for (const preset of ["night", "late"] as const) {
    const [presetStart, presetEnd] = QUIET_PRESETS[preset];
    if (short(start) === short(presetStart) && short(end) === short(presetEnd)) return preset;
  }
  return "night";
}

export interface HiddenLike {
  id: string;
  action: string;
  reason: string;
  reason_text: string;
  risk_date?: string | null;
}

export interface HiddenGroup<T extends HiddenLike> {
  first: T;
  count: number;
}

/**
 * Одинаковые скрытые решения (то же действие, причина и дата риска) — одной строкой
 * со счётчиком: каждый пересчёт прогноза добавляет решение, и список превращался в повтор.
 * Порядок — по первому появлению.
 */
export function groupHidden<T extends HiddenLike>(items: readonly T[]): HiddenGroup<T>[] {
  const groups = new Map<string, HiddenGroup<T>>();
  for (const item of items) {
    const key = `${item.action}|${item.reason}|${item.risk_date ?? ""}`;
    const group = groups.get(key);
    if (group) group.count += 1;
    else groups.set(key, { first: item, count: 1 });
  }
  return [...groups.values()];
}

/** «2 раза», «5 раз», «12 раз», «22 раза». */
export function timesLabel(count: number): string {
  const tail = count % 10;
  const teen = count % 100 >= 12 && count % 100 <= 14;
  return `${count} ${tail >= 2 && tail <= 4 && !teen ? "раза" : "раз"}`;
}
