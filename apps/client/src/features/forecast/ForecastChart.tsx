import { useState } from "react";
import { StyleSheet, View } from "react-native";
import Svg, { Circle, Defs, Line, LinearGradient, Path, Rect, Stop } from "react-native-svg";

import { formatDay, formatRub, formatRubApprox } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { Text } from "@/shared/ui/text";
import { space, usePalette } from "@/shared/ui/theme";

import { chartGeometry, chartPaths, type PointLike } from "./logic";

interface Props {
  points: readonly PointLike[];
  reserveMinor: number;
  /** Базовый прогноз для сравнения «до/после» (раздел 11.3). */
  compare?: readonly PointLike[];
  /** Компактный вариант для главного экрана. */
  compact?: boolean;
}

/**
 * Коридор p10–p90 с градиентом, сглаженная линия p50, зона ниже резерва и отметка
 * минимума. Ширина берётся из раскладки — график тянется на всю карточку.
 */
export function ForecastChart({ points, reserveMinor, compare, compact }: Props) {
  const palette = usePalette();
  const [width, setWidth] = useState(0);
  if (points.length === 0) return null;
  const height = compact ? 120 : 200;
  const geometry = chartGeometry(points, reserveMinor, height, compare);
  const paths = width > 0 ? chartPaths(geometry, width) : null;
  const first = points[0];
  const last = points[points.length - 1];
  const min = paths ? geometry.bars[paths.minIndex] : undefined;
  const minPoint = paths ? points[paths.minIndex] : undefined;
  const minX = paths ? (paths.xs[paths.minIndex] ?? 0) : 0;
  const minBelow = min?.belowReserve ?? false;
  const reserveY = Math.max(0, Math.min(height, geometry.reserveY));
  // Подпись минимума не должна вылезать за края графика.
  const labelLeft = Math.max(0, Math.min(width - 120, minX - 60));

  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={ru.forecast.chartLabel}
      style={styles.wrapper}
    >
      <View style={{ height }} onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
        {paths ? (
          <Svg width={width} height={height}>
            <Defs>
              <LinearGradient id="band" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={palette.accent} stopOpacity={0.32} />
                <Stop offset="1" stopColor={palette.accent} stopOpacity={0.06} />
              </LinearGradient>
              <LinearGradient id="danger" x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={palette.danger} stopOpacity={0.14} />
                <Stop offset="1" stopColor={palette.danger} stopOpacity={0.02} />
              </LinearGradient>
            </Defs>
            {/* Всё ниже линии резерва — зона риска. */}
            <Rect x={0} y={reserveY} width={width} height={height - reserveY} fill="url(#danger)" />
            {geometry.zeroY !== null ? (
              <Line
                x1={0}
                x2={width}
                y1={geometry.zeroY}
                y2={geometry.zeroY}
                stroke={palette.muted}
                strokeOpacity={0.4}
                strokeWidth={1}
              />
            ) : null}
            <Path d={paths.band} fill="url(#band)" />
            {paths.compare ? (
              <Path
                d={paths.compare}
                stroke={palette.muted}
                strokeWidth={2}
                strokeDasharray="4 5"
                fill="none"
              />
            ) : null}
            <Line
              x1={0}
              x2={width}
              y1={reserveY}
              y2={reserveY}
              stroke={palette.danger}
              strokeWidth={1.5}
              strokeDasharray="6 6"
            />
            <Path
              d={paths.median}
              stroke={palette.accent}
              strokeWidth={compact ? 2.5 : 3}
              strokeLinecap="round"
              fill="none"
            />
            {min ? (
              <>
                <Circle
                  cx={minX}
                  cy={min.mid}
                  r={9}
                  fill={minBelow ? palette.danger : palette.accent}
                  fillOpacity={0.18}
                />
                <Circle
                  cx={minX}
                  cy={min.mid}
                  r={4.5}
                  fill={palette.card}
                  stroke={minBelow ? palette.danger : palette.accent}
                  strokeWidth={2.5}
                />
              </>
            ) : null}
          </Svg>
        ) : null}
        {!compact && min && minPoint ? (
          <View
            pointerEvents="none"
            style={[
              styles.minLabel,
              {
                left: labelLeft,
                // Точка в нижней половине — подпись над ней, иначе под ней.
                top:
                  min.mid > height / 2
                    ? Math.max(0, min.mid - 58)
                    : Math.min(height - 44, min.mid + 14),
                backgroundColor: palette.card,
                borderColor: minBelow ? palette.danger : palette.border,
              },
            ]}
          >
            <Text style={[styles.minValue, { color: minBelow ? palette.danger : palette.text }]}>
              {formatRubApprox(minPoint.p50_minor)}
            </Text>
            <Text style={[styles.minDay, { color: palette.muted }]}>
              {ru.forecast.minimum} · {formatDay(minPoint.day)}
            </Text>
          </View>
        ) : null}
      </View>
      <View style={styles.axis}>
        <Text style={[styles.axisText, { color: palette.muted }]}>
          {first ? formatDay(first.day) : ""}
        </Text>
        <View style={[styles.reservePill, { backgroundColor: palette.dangerSoft }]}>
          <View style={[styles.reserveDash, { borderColor: palette.danger }]} />
          <Text style={[styles.axisText, { color: palette.danger, fontWeight: "700" }]}>
            {ru.forecast.reserveLine} {formatRub(reserveMinor)}
          </Text>
        </View>
        <Text style={[styles.axisText, { color: palette.muted }]}>
          {last ? formatDay(last.day) : ""}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: space.sm },
  axis: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  axisText: { fontSize: 12, fontWeight: "600" },
  reservePill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
  },
  reserveDash: { width: 14, borderTopWidth: 1.5, borderStyle: "dashed" },
  minLabel: {
    position: "absolute",
    width: 120,
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 4,
    alignItems: "center",
  },
  minValue: { fontSize: 13, fontWeight: "800" },
  minDay: { fontSize: 11, fontWeight: "600" },
});
