import { useEffect, useRef, useState } from "react";
import { Animated, Easing, type StyleProp, type TextStyle } from "react-native";
import { formatRub, formatRubApprox } from "@/shared/format";
import { Text } from "./text";
import { motion } from "./theme";
import { useReducedMotion } from "./motion";

/** Only the visual number interpolates; assistive technology always reads the actual amount. */
export function Money({
  minor,
  style,
  approximate = false,
}: {
  minor: number;
  style?: StyleProp<TextStyle>;
  approximate?: boolean;
}) {
  const reduced = useReducedMotion();
  const value = useRef(new Animated.Value(minor)).current;
  const [display, setDisplay] = useState(minor);
  useEffect(() => {
    if (reduced) {
      value.setValue(minor);
      setDisplay(minor);
      return;
    }
    const listener = value.addListener(({ value: next }) =>
      setDisplay(Math.round(next)),
    );
    const animation = Animated.timing(value, {
      toValue: minor,
      duration: motion.update,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    });
    animation.start();
    return () => {
      animation.stop();
      value.removeListener(listener);
    };
  }, [minor, reduced, value]);
  const format = approximate ? formatRubApprox : formatRub;
  return (
    <Text
      accessibilityLabel={format(minor)}
      style={[{ fontVariant: ["tabular-nums"], flexShrink: 1 }, style]}
    >
      {format(display)}
    </Text>
  );
}
