// Разбор пользовательского ввода: суммы в копейки и даты в ISO. Без React — тестируется node --test.

export type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

const MAX_MINOR = 1_000_000_000_00; // 1 млрд ₽ — разумный предел для ручного ввода

/** «12 000,50» → 1200050. Отрицательные значения — только при allowNegative. */
export function parseRubInput(text: string, allowNegative = false): Parsed<number> {
  const cleaned = text.replace(/[\s  ₽]/g, "").replace(",", ".").replace("−", "-");
  if (!cleaned) return { ok: false, error: "Введите сумму" };
  const match = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(cleaned);
  if (!match) return { ok: false, error: "Сумма в формате 12 000,50" };
  const negative = match[1] === "-";
  if (negative && !allowNegative) return { ok: false, error: "Сумма должна быть положительной" };
  const minor = Number(match[2]) * 100 + Number((match[3] ?? "").padEnd(2, "0"));
  if (!Number.isSafeInteger(minor) || minor > MAX_MINOR) {
    return { ok: false, error: "Слишком большая сумма" };
  }
  if (minor === 0 && !allowNegative) return { ok: false, error: "Сумма должна быть больше нуля" };
  return { ok: true, value: negative ? -minor : minor };
}

function isoOf(year: number, month: number, day: number): string | null {
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null;
  }
  return date.toISOString().slice(0, 10);
}

/** «25.10.2026», «25.10» (год из referenceIso) или «2026-10-25» → «2026-10-25». */
export function parseDateInput(text: string, referenceIso: string): Parsed<string> {
  const value = text.trim();
  if (!value) return { ok: false, error: "Введите дату" };
  let iso: string | null = null;
  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const ruMatch = /^(\d{1,2})\.(\d{1,2})(?:\.(\d{2}|\d{4}))?$/.exec(value);
  if (isoMatch) {
    iso = isoOf(Number(isoMatch[1]), Number(isoMatch[2]), Number(isoMatch[3]));
  } else if (ruMatch) {
    const referenceYear = Number(referenceIso.slice(0, 4));
    const rawYear = ruMatch[3];
    const year = rawYear === undefined ? referenceYear : rawYear.length === 2 ? 2000 + Number(rawYear) : Number(rawYear);
    iso = isoOf(year, Number(ruMatch[2]), Number(ruMatch[1]));
  }
  if (!iso) return { ok: false, error: "Дата в формате ДД.ММ.ГГГГ" };
  return { ok: true, value: iso };
}

export function formatDateInput(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split("-");
  return `${day}.${month}.${year}`;
}
