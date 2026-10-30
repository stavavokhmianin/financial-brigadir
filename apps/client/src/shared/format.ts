// Форматирование без Intl: одинаковый результат в Hermes, браузере и Node.

const NBSP = " ";
const MINUS = "−";

const MONTHS_GENITIVE = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

/** Целые копейки → «−1 450,50 ₽». Копейки скрываются, если их нет. */
export function formatRub(minor: number): string {
  if (!Number.isSafeInteger(minor)) {
    throw new RangeError("сумма должна быть целым числом копеек");
  }
  const sign = minor < 0 ? MINUS : "";
  const abs = Math.abs(minor);
  const units = Math.floor(abs / 100);
  const kopecks = abs % 100;
  const grouped = String(units).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  const fraction = kopecks === 0 ? "" : `,${String(kopecks).padStart(2, "0")}`;
  return `${sign}${grouped}${fraction}${NBSP}₽`;
}

/**
 * Прогнозная сумма — оценка, а не банковский остаток до копейки.
 * Округляем тем грубее, чем больше сумма, и явно ставим знак приблизительности.
 */
export function formatRubApprox(minor: number): string {
  if (!Number.isSafeInteger(minor)) {
    throw new RangeError("сумма должна быть целым числом копеек");
  }
  const abs = Math.abs(minor);
  const step =
    abs < 10_000
      ? 1_000 // до 100 ₽ — десятки рублей
      : abs < 100_000
        ? 10_000 // до 1 000 ₽ — сотни рублей
        : abs < 1_000_000
          ? 50_000 // до 10 000 ₽ — 500 ₽
          : abs < 10_000_000
            ? 100_000 // до 100 000 ₽ — тысячи рублей
            : 500_000; // крупные суммы — 5 000 ₽
  return `≈ ${formatRub(Math.round(minor / step) * step)}`;
}

function parseIsoDate(iso: string): { year: number; month: number; day: number } {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) {
    throw new RangeError(`ожидалась дата ISO: ${iso}`);
  }
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

/** «2026-10-21» → «21 октября»; год добавляется, если он отличается от referenceYear. */
export function formatDay(iso: string, referenceYear?: number): string {
  const { year, month, day } = parseIsoDate(iso);
  const name = MONTHS_GENITIVE[month - 1] ?? "";
  const suffix = referenceYear !== undefined && referenceYear !== year ? ` ${year}` : "";
  return `${day} ${name}${suffix}`;
}

/** Момент времени ISO в часовом поясе со смещением (Москва — +180 минут). */
export function formatMoment(iso: string, utcOffsetMinutes = 180): string {
  const timestamp = Date.parse(iso);
  if (Number.isNaN(timestamp)) {
    throw new RangeError(`ожидалось время ISO: ${iso}`);
  }
  const local = new Date(timestamp + utcOffsetMinutes * 60_000);
  const date = `${local.getUTCFullYear()}-${String(local.getUTCMonth() + 1).padStart(2, "0")}-${String(local.getUTCDate()).padStart(2, "0")}`;
  const time = `${String(local.getUTCHours()).padStart(2, "0")}:${String(local.getUTCMinutes()).padStart(2, "0")}`;
  return `${formatDay(date)}, ${time}`;
}

/** Календарная дата (YYYY-MM-DD) момента в часовом поясе пользователя. */
export function localDate(iso: string, utcOffsetMinutes = 180): string {
  const local = new Date(Date.parse(iso) + utcOffsetMinutes * 60_000);
  return local.toISOString().slice(0, 10);
}

export function addDays(isoDate: string, days: number): string {
  const { year, month, day } = parseIsoDate(isoDate);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

/** Русское склонение: plural(5, ["день", "дня", "дней"]) → «дней». */
export function plural(n: number, forms: readonly [string, string, string]): string {
  const abs = Math.abs(n) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return forms[2];
  if (last > 1 && last < 5) return forms[1];
  if (last === 1) return forms[0];
  return forms[2];
}
