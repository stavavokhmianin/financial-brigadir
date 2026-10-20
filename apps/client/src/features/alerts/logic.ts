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
