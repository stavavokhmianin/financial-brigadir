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

/** Качественная шкала риска (ADR-0006): проценты в интерфейсе не показываются. */
export const RISK_LEVELS = ["low", "medium", "high"] as const;
export type RiskLevel = (typeof RISK_LEVELS)[number];

export interface ScaleStep {
  level: RiskLevel;
  active: boolean;
  /** Уровень до сценария — для отметки «было» в симуляторе. */
  previous: boolean;
}

export function riskScale(level: string, previous?: string | null): ScaleStep[] {
  return RISK_LEVELS.map((step) => ({
    level: step,
    active: step === level,
    previous: previous != null && previous !== level && step === previous,
  }));
}

/** Направление изменения уровня: выше, ниже или без изменений. */
export function riskShift(before: string, after: string): "up" | "down" | "same" {
  const rank = (level: string) => RISK_LEVELS.indexOf(level as RiskLevel);
  const delta = rank(after) - rank(before);
  return delta > 0 ? "up" : delta < 0 ? "down" : "same";
}

export interface ChartPaths {
  /** Коридор p10–p90: верх по p90 слева направо, низ по p10 обратно. */
  band: string;
  /** Базовый прогноз p50 — сглаженная кривая. */
  median: string;
  /** Прогноз «до» сценария, если передан compare. */
  compare: string | null;
  xs: number[];
  /** Индекс дня с минимальным p50 — для отметки на графике. */
  minIndex: number;
}

const point = (x: number, y: number) => `${x.toFixed(1)},${y.toFixed(1)}`;

const sign = (v: number) => (v < 0 ? -1 : 1);

/** Наклон в средней точке (Fritsch–Carlson, как curveMonotoneX в d3): без выбросов. */
function slope3(x0: number, y0: number, x1: number, y1: number, x2: number, y2: number): number {
  const h0 = x1 - x0;
  const h1 = x2 - x1;
  const s0 = h0 ? (y1 - y0) / h0 : 0;
  const s1 = h1 ? (y2 - y1) / h1 : 0;
  const p = h0 + h1 ? (s0 * h1 + s1 * h0) / (h0 + h1) : 0;
  return (sign(s0) + sign(s1)) * Math.min(Math.abs(s0), Math.abs(s1), 0.5 * Math.abs(p)) || 0;
}

/**
 * Монотонная кубическая кривая через все точки. В отличие от Catmull-Rom она не
 * «проскакивает» за соседние значения: график не рисует остаток ниже реального минимума.
 */
export function smoothPath(xs: readonly number[], ys: readonly number[]): string {
  const n = xs.length;
  if (n === 0) return "";
  const x = (i: number) => xs[i] ?? 0;
  const y = (i: number) => ys[i] ?? 0;
  let d = `M${point(x(0), y(0))}`;
  if (n === 1) return d;
  const t: number[] = [];
  for (let i = 1; i < n - 1; i += 1) t[i] = slope3(x(i - 1), y(i - 1), x(i), y(i), x(i + 1), y(i + 1));
  const edge = (i0: number, i1: number, inner: number) => {
    const h = x(i1) - x(i0);
    return h ? (3 * (y(i1) - y(i0))) / h / 2 - inner / 2 : inner;
  };
  t[0] = n > 2 ? edge(0, 1, t[1] ?? 0) : (y(1) - y(0)) / (x(1) - x(0) || 1);
  t[n - 1] = n > 2 ? edge(n - 2, n - 1, t[n - 2] ?? 0) : (t[0] ?? 0);
  for (let i = 0; i < n - 1; i += 1) {
    const dx = (x(i + 1) - x(i)) / 3;
    const c1 = point(x(i) + dx, y(i) + dx * (t[i] ?? 0));
    const c2 = point(x(i + 1) - dx, y(i + 1) - dx * (t[i + 1] ?? 0));
    d += ` C${c1} ${c2} ${point(x(i + 1), y(i + 1))}`;
  }
  return d;
}

/** Пути SVG по геометрии графика при заданной ширине. */
export function chartPaths(geometry: ChartGeometry, width: number): ChartPaths {
  const n = geometry.bars.length;
  const xs = geometry.bars.map((_, i) => (n === 1 ? width / 2 : (i / (n - 1)) * width));
  const top = geometry.bars.map((b) => b.rangeTop);
  const bottom = geometry.bars.map((b) => b.rangeTop + b.rangeHeight);
  const band =
    n === 0
      ? ""
      : `${smoothPath(xs, top)} L${point(xs[n - 1] ?? 0, bottom[n - 1] ?? 0)}` +
        smoothPath([...xs].reverse(), [...bottom].reverse()).replace(/^M[^ C]+/, "") +
        " Z";
  const compareYs = geometry.bars.map((b) => b.compareMid);
  const compare = compareYs.every((y): y is number => y !== null)
    ? smoothPath(xs, compareYs)
    : null;
  let minIndex = 0;
  geometry.bars.forEach((b, i) => {
    if (b.mid > (geometry.bars[minIndex]?.mid ?? -Infinity)) minIndex = i;
  });
  return {
    band,
    median: smoothPath(
      xs,
      geometry.bars.map((b) => b.mid),
    ),
    compare: n > 0 ? compare : null,
    xs,
    minIndex,
  };
}
