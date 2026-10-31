import {
  createContext,
  createElement,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { Platform, type ViewStyle } from "react-native";

export const blue = {
  midnight: "#021024",
  deep: "#052659",
  steel: "#5483B3",
  soft: "#7DA0CA",
  ice: "#C1E8FF",
} as const;
export const palettes = {
  dark: {
    background: blue.midnight,
    surface: "#071B35",
    surfaceElevated: "#0C2849",
    foreground: "#F1F8FF",
    foregroundMuted: "#A5BDDA",
    border: "#244260",
    accent: blue.ice,
    accentHover: "#E1F4FF",
    primaryAction: blue.ice,
    chart: blue.ice,
    chartBand: blue.steel,
    overlay: "rgba(2,16,36,0.78)",
    shadow: "#010812",
    card: "#071B35",
    text: "#F1F8FF",
    muted: "#A5BDDA",
    placeholder: "#8EA9C9",
    focusRing: "rgba(193,232,255,0.3)",
    inputBorder: "#5483B3",
    track: "#102C4B",
    accentSoft: "#143A60",
    accentText: blue.midnight,
    primary: blue.ice,
    primaryText: blue.midnight,
    danger: "#FFADB4",
    dangerSoft: "#3B2033",
    dangerSolid: "#B52E45",
    warning: "#F4CB88",
    warningBg: "#332B22",
    ok: "#8EDAC1",
    okSoft: "#143833",
    hero: blue.deep,
    heroBorder: "#305780",
    heroText: "#F1F8FF",
    heroMuted: "#C0D5EF",
    heroChip: "rgba(193,232,255,0.12)",
  },
  light: {
    background: "#EFF5FC",
    surface: "#FFFFFF",
    surfaceElevated: "#E2EFFA",
    foreground: blue.midnight,
    foregroundMuted: "#455E7C",
    border: "#C4D6E8",
    accent: blue.deep,
    accentHover: "#14457B",
    primaryAction: blue.deep,
    chart: blue.deep,
    chartBand: blue.steel,
    overlay: "rgba(2,16,36,0.55)",
    shadow: blue.deep,
    card: "#FFFFFF",
    text: blue.midnight,
    muted: "#455E7C",
    placeholder: "#526C8B",
    focusRing: "rgba(5,38,89,0.16)",
    inputBorder: "#6484A8",
    track: "#E2EDF8",
    accentSoft: "#D9EBFA",
    accentText: "#FFFFFF",
    primary: blue.deep,
    primaryText: "#FFFFFF",
    danger: "#AF243E",
    dangerSoft: "#FCECEF",
    dangerSolid: "#AF243E",
    warning: "#815208",
    warningBg: "#FFF2DC",
    ok: "#16674E",
    okSoft: "#E3F4EE",
    hero: blue.deep,
    heroBorder: "#305780",
    heroText: "#F1F8FF",
    heroMuted: "#C0D5EF",
    heroChip: "rgba(193,232,255,0.12)",
  },
} as const;
export type Palette = { [K in keyof typeof palettes.dark]: string };
type ThemeMode = "dark" | "light";
const ThemeContext = createContext<{ mode: ThemeMode; toggle: () => void }>({
  mode: "dark",
  toggle: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(() => {
    try {
      return Platform.OS === "web" &&
        globalThis.localStorage?.getItem("brigadir.theme") === "light"
        ? "light"
        : "dark";
    } catch {
      return "dark";
    }
  });
  const toggle = () =>
    setMode((current) => {
      const next = current === "dark" ? "light" : "dark";
      try {
        if (Platform.OS === "web")
          globalThis.localStorage?.setItem("brigadir.theme", next);
      } catch {
        /* Storage can be disabled. */
      }
      return next;
    });
  return createElement(
    ThemeContext.Provider,
    { value: { mode, toggle } },
    children,
  );
}
export const useTheme = () => useContext(ThemeContext);
export function usePalette(): Palette {
  return palettes[useTheme().mode];
}

export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
  section: 64,
} as const;
export const radius = { sm: 10, md: 14, lg: 24, xl: 32, pill: 999 } as const;
export const fonts = {
  regular: "Geist_400Regular",
  medium: "Geist_500Medium",
  bold: "Geist_600SemiBold",
  heavy: "Geist_700Bold",
  mono: "GeistMono_400Regular",
  monoMedium: "GeistMono_500Medium",
} as const;
export const typeScale = {
  hero: { fontSize: 64, lineHeight: 72, letterSpacing: -3, fontWeight: "600" },
  display: {
    fontSize: 40,
    lineHeight: 48,
    letterSpacing: -1.6,
    fontWeight: "600",
  },
  title: {
    fontSize: 28,
    lineHeight: 36,
    letterSpacing: -0.9,
    fontWeight: "600",
  },
  heading: {
    fontSize: 18,
    lineHeight: 26,
    letterSpacing: -0.4,
    fontWeight: "600",
  },
  body: { fontSize: 15, lineHeight: 23 },
  caption: { fontSize: 12, lineHeight: 18, letterSpacing: 0.1 },
  eyebrow: {
    fontSize: 11,
    lineHeight: 18,
    letterSpacing: 1.6,
    fontFamily: fonts.mono,
  },
} as const;
export const motion = {
  quick: 160,
  enter: 360,
  update: 280,
  stagger: 55,
} as const;
export function elevation(palette: Palette, level: 1 | 2 | 3 = 1): ViewStyle {
  if (Platform.OS === "android") return { elevation: level * 2 };
  return { boxShadow: `0 ${level * 6}px ${level * 18}px ${palette.shadow}26` };
}
