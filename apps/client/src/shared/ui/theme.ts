import { Platform, useColorScheme, type ViewStyle } from "react-native";

// Визуальный язык «Бригадира» в духе Geist: монохромная основа (чёрный, белый, нейтральные
// серые), тонкие границы вместо теней, синий — только для ссылок и графика. Цвет состояний
// несёт смысл: зелёный — «запас есть», красный — «ниже резерва», янтарный — «внимание».
export interface Palette {
  background: string;
  card: string;
  text: string;
  muted: string;
  /** Подсказка в пустом поле: заметно светлее введённого текста. */
  placeholder: string;
  /** Ореол вокруг поля в фокусе. */
  focusRing: string;
  border: string;
  /**
   * Рамка поля ввода. Темнее декоративной `border`: у пустого поля это единственное, что
   * показывает, куда печатать (WCAG 1.4.11 — не меньше 3:1 к фону).
   */
  inputBorder: string;
  /** Подложка трека шкал, разделители внутри карточек. */
  track: string;
  accent: string;
  accentSoft: string;
  accentText: string;
  /** Главное действие: инвертированная поверхность (чёрная в светлой теме, белая в тёмной). */
  primary: string;
  primaryText: string;
  danger: string;
  dangerSoft: string;
  /** Заливка кнопки необратимого действия; текст на ней белый в обеих темах. */
  dangerSolid: string;
  warning: string;
  warningBg: string;
  ok: string;
  okSoft: string;
  /** Контрастная поверхность: карточка баланса, первый экран, Plus. */
  hero: string;
  heroBorder: string;
  heroText: string;
  heroMuted: string;
  heroChip: string;
  shadow: string;
}

const light: Palette = {
  background: "#fafafa",
  card: "#ffffff",
  text: "#171717",
  muted: "#666666",
  // Контраст текста к фону — не меньше 4.5:1 (WCAG 1.4.3), подсказка в поле — тоже текст.
  placeholder: "#737373",
  focusRing: "rgba(0,0,0,0.12)",
  border: "#ebebeb",
  inputBorder: "#8f8f8f",
  track: "#f2f2f2",
  // Чуть темнее #0070f3: ссылка на голубой плашке accentSoft иначе даёт 4.1:1.
  accent: "#0062d1",
  accentSoft: "#ebf5ff",
  accentText: "#ffffff",
  primary: "#171717",
  primaryText: "#ffffff",
  danger: "#c52b30",
  dangerSoft: "#fff0f0",
  dangerSolid: "#c52b30",
  warning: "#aa4d00",
  warningBg: "#fff6e5",
  ok: "#107d32",
  okSoft: "#ebfaef",
  hero: "#0a0a0a",
  heroBorder: "#0a0a0a",
  heroText: "#ededed",
  heroMuted: "#a1a1a1",
  heroChip: "rgba(255,255,255,0.1)",
  shadow: "#000000",
};

const dark: Palette = {
  background: "#000000",
  card: "#0a0a0a",
  text: "#ededed",
  muted: "#a1a1a1",
  placeholder: "#808080",
  focusRing: "rgba(255,255,255,0.18)",
  border: "#2e2e2e",
  inputBorder: "#666666",
  track: "#1a1a1a",
  accent: "#52a8ff",
  accentSoft: "#0d1a2b",
  accentText: "#ffffff",
  primary: "#ededed",
  primaryText: "#0a0a0a",
  danger: "#ff6166",
  dangerSoft: "#2a1314",
  // Белый текст на красной кнопке — 5.2:1 (с #e5484d было 3.9:1).
  dangerSolid: "#c8373c",
  warning: "#ff990a",
  warningBg: "#2a1a05",
  ok: "#62c073",
  okSoft: "#0e2414",
  hero: "#0a0a0a",
  heroBorder: "#2e2e2e",
  heroText: "#ededed",
  heroMuted: "#a1a1a1",
  heroChip: "rgba(255,255,255,0.08)",
  shadow: "#000000",
};

export function usePalette(): Palette {
  return useColorScheme() === "dark" ? dark : light;
}

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { sm: 6, md: 8, lg: 12, xl: 16, pill: 999 } as const;

/** Начертания Geist; вес задаётся семейством, а не fontWeight (так надёжнее на Android). */
export const fonts = {
  regular: "Geist_400Regular",
  medium: "Geist_500Medium",
  bold: "Geist_600SemiBold",
  heavy: "Geist_700Bold",
  mono: "GeistMono_400Regular",
  monoMedium: "GeistMono_500Medium",
} as const;

/**
 * Еле заметная тень поверх границы — как у карточек Geist. В тёмной теме тень не видна,
 * поэтому глубину там дают только границы.
 */
export function elevation(palette: Palette, level: 1 | 2 | 3 = 1): ViewStyle {
  const blur = { 1: 2, 2: 8, 3: 24 }[level];
  const y = { 1: 1, 2: 4, 3: 12 }[level];
  const opacity = { 1: 0.04, 2: 0.06, 3: 0.12 }[level];
  if (Platform.OS === "android") return { elevation: { 1: 0, 2: 1, 3: 6 }[level] };
  return {
    shadowColor: palette.shadow,
    shadowOpacity: opacity,
    shadowRadius: blur / 2,
    shadowOffset: { width: 0, height: y },
  };
}
