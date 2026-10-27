import { useColorScheme } from "react-native";

export interface Palette {
  background: string;
  card: string;
  text: string;
  muted: string;
  border: string;
  accent: string;
  accentText: string;
  danger: string;
  warning: string;
  warningBg: string;
  ok: string;
}

const light: Palette = {
  background: "#f4f5f7",
  card: "#ffffff",
  text: "#14171f",
  muted: "#5c6370",
  border: "#dde1e7",
  accent: "#1f5eff",
  accentText: "#ffffff",
  danger: "#c62828",
  warning: "#8a5a00",
  warningBg: "#fff4dc",
  ok: "#1b7f3b",
};

const dark: Palette = {
  background: "#0f1115",
  card: "#181b22",
  text: "#eef0f4",
  muted: "#9aa3b2",
  border: "#2a2f3a",
  accent: "#6d94ff",
  accentText: "#0f1115",
  danger: "#ff7b72",
  warning: "#f0c060",
  warningBg: "#2e2614",
  ok: "#5fd38a",
};

export function usePalette(): Palette {
  return useColorScheme() === "dark" ? dark : light;
}

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const;
