import Svg, { Circle, Path, Rect } from "react-native-svg";

// Собственный набор линейных иконок 24×24 (штрих 1.75): одинаковый вид на web, iOS и Android
// без шрифтов иконок.
export type IconName =
  | "chart"
  | "cart"
  | "calendar"
  | "bell"
  | "plus"
  | "upload"
  | "crown"
  | "bank"
  | "shield"
  | "arrow"
  | "check"
  | "alert"
  | "sparkle"
  | "wallet"
  | "clock"
  | "user";

const PATHS: Record<IconName, (color: string) => React.ReactNode> = {
  chart: (c) => (
    <>
      <Path d="M4 19V5" stroke={c} />
      <Path d="M4 19h16" stroke={c} />
      <Path d="M7 15l4-4 3 3 5-6" stroke={c} />
    </>
  ),
  cart: (c) => (
    <>
      <Path d="M3 4h2l2.2 10.2a1 1 0 0 0 1 .8h8.6a1 1 0 0 0 1-.8L19.5 8H6" stroke={c} />
      <Circle cx="9" cy="19" r="1.4" fill={c} />
      <Circle cx="17" cy="19" r="1.4" fill={c} />
    </>
  ),
  calendar: (c) => (
    <>
      <Rect x="4" y="5.5" width="16" height="14.5" rx="3" stroke={c} />
      <Path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" stroke={c} />
    </>
  ),
  bell: (c) => (
    <>
      <Path d="M6.5 16.5h11l-1.4-2.2V10a4.1 4.1 0 0 0-8.2 0v4.3z" stroke={c} />
      <Path d="M10 19.5a2.2 2.2 0 0 0 4 0" stroke={c} />
    </>
  ),
  plus: (c) => <Path d="M12 5v14M5 12h14" stroke={c} />,
  upload: (c) => (
    <>
      <Path d="M12 15V4M7.5 8.5 12 4l4.5 4.5" stroke={c} />
      <Path d="M5 14.5V18a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3.5" stroke={c} />
    </>
  ),
  crown: (c) => <Path d="M4.5 17.5 3.5 8l5 4 3.5-6 3.5 6 5-4-1 9.5z" stroke={c} />,
  bank: (c) => (
    <>
      <Path d="M3.5 9.5 12 4.5l8.5 5z" stroke={c} />
      <Path d="M6 10v7M10 10v7M14 10v7M18 10v7M4 19.5h16" stroke={c} />
    </>
  ),
  shield: (c) => (
    <>
      <Path d="M12 3.5 5 6.5v5c0 4.3 3 7.6 7 9 4-1.4 7-4.7 7-9v-5z" stroke={c} />
      <Path d="m9 12 2 2 4-4" stroke={c} />
    </>
  ),
  arrow: (c) => <Path d="M5 12h14M13 6l6 6-6 6" stroke={c} />,
  check: (c) => <Path d="m5 12.5 4.5 4.5L19 7.5" stroke={c} />,
  alert: (c) => (
    <>
      <Path d="M12 4 2.8 19.5h18.4z" stroke={c} />
      <Path d="M12 10v4.5" stroke={c} />
      <Circle cx="12" cy="17" r="1" fill={c} />
    </>
  ),
  sparkle: (c) => (
    <Path d="M12 3.5c.6 4.4 2.1 5.9 6.5 6.5-4.4.6-5.9 2.1-6.5 6.5-.6-4.4-2.1-5.9-6.5-6.5 4.4-.6 5.9-2.1 6.5-6.5z" stroke={c} />
  ),
  wallet: (c) => (
    <>
      <Rect x="3.5" y="6" width="17" height="13" rx="3" stroke={c} />
      <Path d="M3.5 9.5h17M15.5 14h2" stroke={c} />
    </>
  ),
  clock: (c) => (
    <>
      <Circle cx="12" cy="12" r="8" stroke={c} />
      <Path d="M12 7.5V12l3 2" stroke={c} />
    </>
  ),
  user: (c) => (
    <>
      <Circle cx="12" cy="8.5" r="3.5" stroke={c} />
      <Path d="M5 19.5c1-3.4 3.7-5 7-5s6 1.6 7 5" stroke={c} />
    </>
  ),
};

export function Icon({ name, color, size = 22 }: { name: IconName; color: string; size?: number }) {
  return (
    <Svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {PATHS[name](color)}
    </Svg>
  );
}
