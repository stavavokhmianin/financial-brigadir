import { LinearGradient } from "expo-linear-gradient";
import { StyleSheet, View } from "react-native";
import Svg, { Line, Rect } from "react-native-svg";

import { usePalette } from "./theme";

/**
 * Знак «Бригадира» — как на иконке приложения: столбики остатка и пунктир резерва.
 * onHero — белая плашка для размещения на градиенте.
 */
export function Logo({ size = 44, onHero = false }: { size?: number; onHero?: boolean }) {
  const palette = usePalette();
  const bars = onHero ? palette.brand[0] : "#ffffff";
  const mark = (
    <Svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24">
      <Rect x="3" y="6" width="4.2" height="13" rx="1.6" fill={bars} />
      <Rect x="9.9" y="11" width="4.2" height="8" rx="1.6" fill={bars} />
      <Rect x="16.8" y="3.5" width="4.2" height="15.5" rx="1.6" fill={bars} />
      <Line
        x1="1.5"
        x2="22.5"
        y1="14.5"
        y2="14.5"
        stroke="#ffd666"
        strokeWidth={1.8}
        strokeDasharray="2.2 2"
        strokeLinecap="round"
      />
    </Svg>
  );
  const shape = { width: size, height: size, borderRadius: size * 0.3 };
  if (onHero) {
    return <View style={[styles.center, shape, { backgroundColor: "#ffffff" }]}>{mark}</View>;
  }
  return (
    <LinearGradient
      colors={[...palette.brand]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={[styles.center, shape]}
    >
      {mark}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center" },
});
