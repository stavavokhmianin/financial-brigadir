import { StyleSheet, Text, View } from "react-native";

import { formatDay, formatRub } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { space, usePalette } from "@/shared/ui/theme";

import { chartGeometry, type PointLike } from "./logic";

const HEIGHT = 180;

interface Props {
  points: readonly PointLike[];
  reserveMinor: number;
  /** Базовый прогноз для сравнения «до/после» (раздел 11.3). */
  compare?: readonly PointLike[];
}

/** Коридор p10–p90 по дням, отметка p50 и линия резерва. Без нативных зависимостей. */
export function ForecastChart({ points, reserveMinor, compare }: Props) {
  const palette = usePalette();
  if (points.length === 0) return null;
  const geometry = chartGeometry(points, reserveMinor, HEIGHT, compare);
  const first = points[0];
  const last = points[points.length - 1];
  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={ru.forecast.chartLabel}
      style={styles.wrapper}
    >
      <View style={[styles.area, { height: HEIGHT, borderColor: palette.border }]}>
        {geometry.zeroY !== null ? (
          <View style={[styles.line, { top: geometry.zeroY, backgroundColor: palette.muted }]} />
        ) : null}
        <View
          style={[styles.reserve, { top: geometry.reserveY, borderColor: palette.danger }]}
        />
        <View style={styles.bars}>
          {geometry.bars.map((bar) => (
            <View key={bar.day} style={styles.column}>
              <View
                style={[
                  styles.range,
                  {
                    top: bar.rangeTop,
                    height: bar.rangeHeight,
                    backgroundColor: bar.belowReserve ? palette.danger : palette.accent,
                    opacity: 0.25,
                  },
                ]}
              />
              {bar.compareMid !== null ? (
                <View
                  style={[styles.compare, { top: bar.compareMid - 1, backgroundColor: palette.muted }]}
                />
              ) : null}
              <View
                style={[
                  styles.mid,
                  {
                    top: bar.mid - 2,
                    backgroundColor: bar.belowReserve ? palette.danger : palette.accent,
                  },
                ]}
              />
            </View>
          ))}
        </View>
      </View>
      <View style={styles.axis}>
        <Text style={[styles.axisText, { color: palette.muted }]}>
          {first ? formatDay(first.day) : ""}
        </Text>
        <Text style={[styles.axisText, { color: palette.danger }]}>
          {ru.forecast.reserveLine} {formatRub(reserveMinor)}
        </Text>
        <Text style={[styles.axisText, { color: palette.muted }]}>
          {last ? formatDay(last.day) : ""}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { gap: space.xs },
  area: { borderBottomWidth: 1, position: "relative", overflow: "hidden" },
  bars: { ...StyleSheet.absoluteFillObject, flexDirection: "row", gap: 2 },
  column: { flex: 1, position: "relative" },
  range: { position: "absolute", left: 0, right: 0, borderRadius: 2 },
  mid: { position: "absolute", left: 0, right: 0, height: 4, borderRadius: 2 },
  compare: { position: "absolute", left: 2, right: 2, height: 2, opacity: 0.8 },
  line: { position: "absolute", left: 0, right: 0, height: 1, opacity: 0.6 },
  reserve: { position: "absolute", left: 0, right: 0, borderTopWidth: 1, borderStyle: "dashed" },
  axis: { flexDirection: "row", justifyContent: "space-between" },
  axisText: { fontSize: 12 },
});
