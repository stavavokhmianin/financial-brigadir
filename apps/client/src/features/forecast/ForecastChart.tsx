import { useId, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Svg, {
  Circle,
  Defs,
  Line,
  LinearGradient,
  Path,
  Rect,
  Stop,
} from "react-native-svg";
import { formatDay, formatRub } from "@/shared/format";
import { Text } from "@/shared/ui/text";
import { Reveal } from "@/shared/ui/motion";
import { fonts, radius, space, usePalette } from "@/shared/ui/theme";
import { chartGeometry, chartPaths, type PointLike } from "./logic";

interface Props {
  points: readonly PointLike[];
  reserveMinor: number;
  compare?: readonly PointLike[];
  compact?: boolean;
}
export function ForecastChart({
  points,
  reserveMinor,
  compare,
  compact,
}: Props) {
  const palette = usePalette();
  const [width, setWidth] = useState(0);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  if (!points.length) return null;
  const height = compact ? 160 : 240;
  const geometry = chartGeometry(points, reserveMinor, height, compare);
  const paths = width > 0 ? chartPaths(geometry, width) : null;
  const selectedIndex = points.findIndex((p) => p.day === selectedDay);
  const index = selectedIndex >= 0 ? selectedIndex : (paths?.minIndex ?? 0);
  const selected = points[index]!;
  const selectedBar = geometry.bars[index]!;
  const reserveY = Math.max(0, Math.min(height, geometry.reserveY));
  const select = (next: number) =>
    setSelectedDay(points[Math.max(0, Math.min(points.length - 1, next))]!.day);
  const ticks = [0, 0.5, 1];
  const axisLabel = (minor: number) =>
    Math.abs(minor) >= 100000
      ? Math.round(minor / 100000) + " тыс."
      : formatRub(Math.round(minor / 100) * 100);
  const revision = points
    .map((p) =>
      [p.day, p.p10_minor, p.p50_minor, p.p90_minor, reserveMinor].join(":"),
    )
    .join("|");
  return (
    <View style={styles.wrapper}>
      <View style={styles.plotRow}>
        <View accessible={false} style={{ width: 56, height }}>
          {ticks.map((fraction) => (
            <Text
              key={fraction}
              style={[
                styles.tick,
                {
                  top: fraction * (height - 14),
                  color: palette.muted,
                },
              ]}
            >
              {axisLabel(
                geometry.maxValue -
                  fraction * (geometry.maxValue - geometry.minValue),
              )}
            </Text>
          ))}
        </View>
        <View
          style={{ flex: 1, minWidth: 0 }}
          onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
        >
          <Reveal revision={revision}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="График прогноза. Нажмите для выбора даты; для точного выбора используйте кнопки под графиком."
              onPress={(event) => {
                if (width > 0)
                  select(
                    Math.round(
                      (event.nativeEvent.locationX / width) *
                        (points.length - 1),
                    ),
                  );
              }}
              style={{ height }}
            >
              {paths ? (
                <Svg width={width} height={height}>
                  <Defs>
                    <LinearGradient
                      id={id + "band"}
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <Stop
                        offset="0"
                        stopColor={palette.chartBand}
                        stopOpacity={0.38}
                      />
                      <Stop
                        offset="1"
                        stopColor={palette.chartBand}
                        stopOpacity={0.04}
                      />
                    </LinearGradient>
                    <LinearGradient
                      id={id + "risk"}
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <Stop
                        offset="0"
                        stopColor={palette.danger}
                        stopOpacity={0.09}
                      />
                      <Stop
                        offset="1"
                        stopColor={palette.danger}
                        stopOpacity={0.015}
                      />
                    </LinearGradient>
                  </Defs>
                  <Rect
                    x={0}
                    y={reserveY}
                    width={width}
                    height={height - reserveY}
                    fill={`url(#${id}risk)`}
                  />
                  {ticks.map((fraction) => (
                    <Line
                      key={fraction}
                      x1={0}
                      x2={width}
                      y1={fraction * height}
                      y2={fraction * height}
                      stroke={palette.border}
                      strokeDasharray="3 5"
                    />
                  ))}
                  {geometry.zeroY !== null ? (
                    <Line
                      x1={0}
                      x2={width}
                      y1={geometry.zeroY}
                      y2={geometry.zeroY}
                      stroke={palette.muted}
                      strokeOpacity={0.4}
                    />
                  ) : null}
                  <Path d={paths.band} fill={`url(#${id}band)`} />
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
                    strokeWidth={1}
                    strokeDasharray="5 5"
                  />
                  <Path
                    d={paths.median}
                    stroke={palette.chart}
                    strokeWidth={2.5}
                    strokeLinecap="round"
                    fill="none"
                  />
                  {geometry.bars.map((bar, i) =>
                    bar.belowReserve &&
                    (!geometry.bars[i - 1]?.belowReserve ||
                      i === paths.minIndex) ? (
                      <Circle
                        key={bar.day}
                        cx={paths.xs[i]}
                        cy={bar.mid}
                        r={4}
                        fill={palette.danger}
                        stroke={palette.card}
                        strokeWidth={2}
                      />
                    ) : null,
                  )}
                  <Line
                    x1={paths.xs[index]}
                    x2={paths.xs[index]}
                    y1={0}
                    y2={height}
                    stroke={palette.muted}
                    strokeOpacity={0.5}
                    strokeDasharray="3 4"
                  />
                  <Circle
                    cx={paths.xs[index]}
                    cy={selectedBar.mid}
                    r={9}
                    fill={palette.chart}
                    fillOpacity={0.12}
                  />
                  <Circle
                    cx={paths.xs[index]}
                    cy={selectedBar.mid}
                    r={4.5}
                    fill={palette.card}
                    stroke={
                      selectedBar.belowReserve ? palette.danger : palette.chart
                    }
                    strokeWidth={2}
                  />
                </Svg>
              ) : null}
            </Pressable>
          </Reveal>
        </View>
      </View>
      <View style={styles.axis}>
        <Text style={[styles.caption, { color: palette.muted }]}>
          {formatDay(points[0]!.day)}
        </Text>
        <Text style={[styles.caption, { color: palette.muted }]}>
          {formatDay(points[points.length - 1]!.day)}
        </Text>
      </View>
      {compact ? null : (
        <View
          style={[
            styles.details,
            {
              borderColor: palette.border,
              backgroundColor: palette.background,
            },
          ]}
        >
          <View style={styles.dateNavigation}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Предыдущая дата прогноза"
              accessibilityState={{ disabled: index === 0 }}
              disabled={index === 0}
              onPress={() => select(index - 1)}
              style={[
                styles.arrow,
                {
                  borderColor: palette.inputBorder,
                  opacity: index === 0 ? 0.4 : 1,
                },
              ]}
            >
              <Text style={{ color: palette.text }}>←</Text>
            </Pressable>
            <Text
              style={[
                styles.caption,
                { color: palette.text, flex: 1, textAlign: "center" },
              ]}
            >
              {formatDay(selected.day)}
            </Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Следующая дата прогноза"
              accessibilityState={{ disabled: index === points.length - 1 }}
              disabled={index === points.length - 1}
              onPress={() => select(index + 1)}
              style={[
                styles.arrow,
                {
                  borderColor: palette.inputBorder,
                  opacity: index === points.length - 1 ? 0.4 : 1,
                },
              ]}
            >
              <Text style={{ color: palette.text }}>→</Text>
            </Pressable>
          </View>
          <View accessibilityLiveRegion="polite" style={styles.readout}>
            <Text
              style={[
                styles.value,
                {
                  color: selectedBar.belowReserve
                    ? palette.danger
                    : palette.text,
                },
              ]}
            >
              {formatRub(selected.p50_minor)}
            </Text>
            <Text style={[styles.caption, { color: palette.muted }]}>
              p50 · основной сценарий
            </Text>
            <Text style={[styles.caption, { color: palette.muted }]}>
              p10–p90: {formatRub(selected.p10_minor)} …{" "}
              {formatRub(selected.p90_minor)}
            </Text>
            <Text style={[styles.caption, { color: palette.danger }]}>
              — Резерв {formatRub(reserveMinor)}
            </Text>
          </View>
        </View>
      )}
    </View>
  );
}
const styles = StyleSheet.create({
  wrapper: { gap: space.md },
  plotRow: { flexDirection: "row" },
  tick: {
    position: "absolute",
    right: 8,
    fontFamily: fonts.mono,
    fontSize: 10,
  },
  axis: {
    marginLeft: 56,
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
  },
  caption: { fontSize: 11, lineHeight: 17, fontVariant: ["tabular-nums"] },
  details: { borderRadius: radius.md, borderWidth: 1, padding: 12, gap: 8 },
  dateNavigation: { flexDirection: "row", alignItems: "center", gap: 8 },
  arrow: {
    minWidth: 44,
    height: 44,
    borderWidth: 1,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  readout: { gap: 4 },
  value: {
    fontSize: 24,
    lineHeight: 32,
    letterSpacing: -0.8,
    fontWeight: "600",
    fontVariant: ["tabular-nums"],
  },
});
