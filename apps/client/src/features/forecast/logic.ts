// Геометрия графика и представление риска — чистые функции, проверяются node --test.

export interface PointLike {
  day: string;
  p10_minor: number;
  p50_minor: number;
  p90_minor: number;
}

export interface Bar {
  day: string;
  /** Координаты от верха области графика, px. */
  rangeTop: number;
  rangeHeight: number;
  mid: number;
  /** Отметка базового прогноза «до» сценария (если передан compare). */
  compareMid: number | null;
  belowReserve: boolean;
}

export interface ChartGeometry {
  bars: Bar[];
  reserveY: number;
  zeroY: number | null;
  minValue: number;
  maxValue: number;
}

/** Ось Y общая для коридора p10–p90, резерва и нуля; запас 5 % сверху и снизу. */
export function chartGeometry(
  points: readonly PointLike[],
  reserveMinor: number,
  height: number,
  compare: readonly PointLike[] = [],
): ChartGeometry {
  const values = points
    .flatMap((p) => [p.p10_minor, p.p90_minor])
    .concat(compare.map((p) => p.p50_minor))
    .concat(reserveMinor);
  const compareByDay = new Map(compare.map((p) => [p.day, p.p50_minor]));
  let minValue = Math.min(...values);
  let maxValue = Math.max(...values);
  if (minValue === maxValue) {
    minValue -= 1;
    maxValue += 1;
  }
  const pad = (maxValue - minValue) * 0.05;
  minValue -= pad;
  maxValue += pad;
  const toY = (value: number) => ((maxValue - value) / (maxValue - minValue)) * height;
  const bars = points.map((p) => {
    const top = toY(p.p90_minor);
    const bottom = toY(p.p10_minor);
    return {
      day: p.day,
      rangeTop: top,
      rangeHeight: Math.max(2, bottom - top),
      mid: toY(p.p50_minor),
      compareMid: compareByDay.has(p.day) ? toY(compareByDay.get(p.day) ?? 0) : null,
      belowReserve: p.p50_minor < reserveMinor,
    };
  });
  return {
    bars,
    reserveY: toY(reserveMinor),
    zeroY: minValue < 0 && maxValue > 0 ? toY(0) : null,
    minValue,
    maxValue,
  };
}

export type Tone = "ok" | "warning" | "danger";

export function riskTone(level: string): Tone {
  if (level === "high") return "danger";
  if (level === "medium") return "warning";
  return "ok";
}

/** Дни для списка «ключевые даты»: дни с событиями, дата риска и минимум. */
export function keyDays<T extends PointLike & { inflow_minor: number; outflow_minor: number }>(
  points: readonly T[],
  riskDate: string | null,
  minDate: string,
  limit = 8,
): T[] {
  const picked = points.filter(
    (p) => p.inflow_minor > 0 || p.outflow_minor > 0 || p.day === riskDate || p.day === minDate,
  );
  return picked.slice(0, limit);
}
