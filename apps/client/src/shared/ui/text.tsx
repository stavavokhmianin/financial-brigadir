import { StyleSheet, Text as NativeText, type TextProps, type TextStyle } from "react-native";

import { fonts } from "./theme";

// Как в Geist: заголовки и цифры — 600, жирнее 700 не бывает.
const FAMILY: Record<string, string> = {
  "100": fonts.regular,
  "200": fonts.regular,
  "300": fonts.regular,
  "400": fonts.regular,
  normal: fonts.regular,
  "500": fonts.medium,
  "600": fonts.bold,
  "700": fonts.bold,
  bold: fonts.bold,
  "800": fonts.heavy,
  "900": fonts.heavy,
};

/**
 * Text приложения: Geist с начертанием по fontWeight. Вес переводится в семейство,
 * потому что Android не синтезирует жирность для подключённых шрифтов.
 */
export function Text({ style, ...props }: TextProps) {
  const flat: TextStyle = StyleSheet.flatten(style) ?? {};
  if (flat.fontFamily && !flat.fontFamily.startsWith("Geist")) {
    return <NativeText style={style} {...props} />;
  }
  const family = flat.fontFamily ?? FAMILY[String(flat.fontWeight ?? "400")] ?? fonts.regular;
  return <NativeText style={[style, { fontFamily: family, fontWeight: undefined }]} {...props} />;
}
