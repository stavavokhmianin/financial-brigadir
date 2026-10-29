import { Platform, useColorScheme, type ViewStyle } from "react-native";

// Визуальный язык «Бригадира»: глубокий индиго-фиолетовый бренд, мятный — «запас есть»,
// коралловый — «ниже резерва», янтарный — «внимание». Цифры — крупные и спокойные.
export interface Palette {
  background: string;
  card: string;
  text: string;
  muted: string;
  border: string;
  /** Подложка трека шкал, разделители внутри карточек. */
  track: string;
  accent: string;
  accentSoft: string;
  accentText: string;
  danger: string;
  dangerSoft: string;
  warning: string;
  warningBg: string;
  ok: string;
  okSoft: string;
  /** Градиент фирменных поверхностей: карточка баланса, главная кнопка, логотип. */
  brand: readonly [string, string];
  heroText: string;
  heroMuted: string;
  heroChip: string;
  shadow: string;
}

const light: Palette = {
  background: "#f2f4fa",
  card: "#ffffff",
  text: "#0e1324",
  muted: "#5d6884",
  border: "#e3e7f1",
  track: "#eceff7",
  accent: "#4f46e5",
  accentSoft: "#eef0ff",
  accentText: "#ffffff",
  danger: "#dc3545",
  dangerSoft: "#fdecee",
  warning: "#a35f00",
  warningBg: "#fff4dd",
  ok: "#0f9a74",
  okSoft: "#e2f6ef",
  brand: ["#3f33e0", "#8b5cf6"],
  heroText: "#ffffff",
  heroMuted: "rgba(255,255,255,0.74)",
  heroChip: "rgba(255,255,255,0.18)",
  shadow: "#1d2150",
};

const dark: Palette = {
  background: "#080a12",
  card: "#121626",
  text: "#eef1fa",
  muted: "#9aa4c0",
  border: "#232a41",
  track: "#1b2135",
  accent: "#7d7aff",
  accentSoft: "#1d1f45",
  accentText: "#ffffff",
  danger: "#ff6b6b",
  dangerSoft: "#2b1519",
  warning: "#f5b544",
  warningBg: "#2a2011",
  ok: "#3dd6a3",
  okSoft: "#0e2a22",
  brand: ["#3127c4", "#7b4cf0"],
  heroText: "#ffffff",
  heroMuted: "rgba(255,255,255,0.72)",
  heroChip: "rgba(255,255,255,0.16)",
  shadow: "#000000",
};

export function usePalette(): Palette {
  return useColorScheme() === "dark" ? dark : light;
}

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { sm: 10, md: 14, lg: 20, xl: 28, pill: 999 } as const;

/** Начертания Manrope; вес задаётся семейством, а не fontWeight (так надёжнее на Android). */
export const fonts = {
  regular: "Manrope_500Medium",
  medium: "Manrope_600SemiBold",
  bold: "Manrope_700Bold",
  heavy: "Manrope_800ExtraBold",
} as const;

/** Мягкая тень карточки: на web — boxShadow, на iOS — shadow*, на Android — elevation. */
export function elevation(palette: Palette, level: 1 | 2 | 3 = 1): ViewStyle {
  const blur = { 1: 18, 2: 28, 3: 40 }[level];
  const y = { 1: 6, 2: 12, 3: 18 }[level];
  const opacity = { 1: 0.07, 2: 0.12, 3: 0.2 }[level];
  if (Platform.OS === "android") return { elevation: { 1: 2, 2: 6, 3: 10 }[level] };
  return {
    shadowColor: palette.shadow,
    shadowOpacity: opacity,
    shadowRadius: blur / 2,
    shadowOffset: { width: 0, height: y },
  };
}
