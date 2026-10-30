import { StyleSheet, View } from "react-native";
import Svg, { Line, Rect } from "react-native-svg";

import { usePalette } from "./theme";

/**
 * Знак «Бригадира» — столбики остатка и пунктир резерва на монохромной плашке.
 * onHero — светлая плашка для размещения на контрастной поверхности.
 */
export function Logo({ size = 40, onHero = false }: { size?: number; onHero?: boolean }) {
  const palette = usePalette();
  const [tile, bars] = onHero ? [palette.heroText, palette.hero] : [palette.primary, palette.primaryText];
  return (
    <View style={[styles.center, { width: size, height: size, borderRadius: size * 0.25, backgroundColor: tile }]}>
      <Svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24">
        <Rect x="3" y="6" width="4.2" height="13" rx="1" fill={bars} />
        <Rect x="9.9" y="11" width="4.2" height="8" rx="1" fill={bars} />
        <Rect x="16.8" y="3.5" width="4.2" height="15.5" rx="1" fill={bars} />
        <Line
          x1="1.5"
          x2="22.5"
          y1="14.5"
          y2="14.5"
          stroke={palette.accent}
          strokeWidth={1.8}
          strokeDasharray="2.2 2"
          strokeLinecap="round"
        />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center" },
});
