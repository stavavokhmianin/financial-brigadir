import { LinearGradient } from "expo-linear-gradient";
import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  type KeyboardTypeOptions,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon, type IconName } from "./icons";
import { Text } from "./text";
import { elevation, fonts, radius, space, usePalette } from "./theme";

interface FieldProps {
  testID?: string;
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  error?: string | null;
  hint?: string;
  multiline?: boolean;
  keyboardType?: KeyboardTypeOptions;
  monospace?: boolean;
}

export function Field(props: FieldProps) {
  const palette = usePalette();
  return (
    <View style={styles.field}>
      <Text style={[styles.fieldLabel, { color: palette.muted }]}>{props.label}</Text>
      <TextInput
        testID={props.testID}
        accessibilityLabel={props.label}
        value={props.value}
        onChangeText={props.onChangeText}
        placeholder={props.placeholder}
        placeholderTextColor={palette.muted}
        multiline={props.multiline}
        keyboardType={props.keyboardType}
        autoCapitalize="none"
        autoCorrect={false}
        style={[
          styles.input,
          props.multiline ? styles.inputMultiline : null,
          props.monospace ? styles.mono : { fontFamily: fonts.medium },
          {
            color: palette.text,
            borderColor: props.error ? palette.danger : palette.border,
            backgroundColor: palette.background,
          },
        ]}
      />
      {props.error ? (
        <Text style={[styles.fieldHint, { color: palette.danger }]}>{props.error}</Text>
      ) : props.hint ? (
        <Text style={[styles.fieldHint, { color: palette.muted }]}>{props.hint}</Text>
      ) : null}
    </View>
  );
}

interface ChoiceOption<T extends string> {
  value: T;
  label: string;
}

interface ChoiceProps<T extends string> {
  label?: string;
  options: readonly ChoiceOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
}

/** Выбор одного варианта «пилюлями» (радиогруппа). */
export function Choice<T extends string>({ label, options, value, onChange }: ChoiceProps<T>) {
  const palette = usePalette();
  return (
    <View style={styles.field}>
      {label ? <Text style={[styles.fieldLabel, { color: palette.muted }]}>{label}</Text> : null}
      <View accessibilityRole="radiogroup" style={styles.chips}>
        {options.map((option) => {
          const active = option.value === value;
          return (
            <Pressable
              key={option.value}
              accessibilityRole="radio"
              accessibilityLabel={option.label}
              accessibilityState={{ checked: active }}
              onPress={() => onChange(option.value)}
              style={({ pressed }) => [
                styles.chip,
                {
                  backgroundColor: active ? palette.accent : palette.track,
                  transform: [{ scale: pressed ? 0.97 : 1 }],
                },
                active ? elevation(palette, 1) : null,
              ]}
            >
              <Text
                style={{
                  color: active ? palette.accentText : palette.text,
                  fontSize: 14,
                  fontWeight: active ? "700" : "600",
                }}
              >
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

/** «#rrggbb» → «rgba(r,g,b,a)»: так прозрачность градиента понимают и web, и натив. */
const withAlpha = (hex: string, alpha: number) => {
  if (!hex.startsWith("#") || hex.length !== 7) return hex;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${alpha})`;
};

export function Screen({ children, topInset }: { children: ReactNode; topInset?: boolean }) {
  const palette = usePalette();
  // Android 15+ и SDK 54 рисуют edge-to-edge: без отступа последняя кнопка уходит
  // под системную панель навигации. topInset — для экранов без шапки (старт).
  const { bottom, top } = useSafeAreaInsets();
  return (
    <ScrollView
      style={{ backgroundColor: palette.background }}
      contentContainerStyle={[
        styles.screen,
        { paddingBottom: space.xl + bottom },
        topInset ? { paddingTop: space.lg + top } : null,
      ]}
      keyboardShouldPersistTaps="handled"
    >
      {/* Мягкое фирменное свечение сверху экрана. */}
      <LinearGradient
        pointerEvents="none"
        colors={[
          withAlpha(palette.brand[1], 0.18),
          withAlpha(palette.brand[1], 0.06),
          withAlpha(palette.brand[1], 0),
        ]}
        locations={[0, 0.55, 1]}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
        style={styles.glow}
      />
      <View style={styles.column}>{children}</View>
    </ScrollView>
  );
}

/** Заметная строка-пояснение над содержимым экрана (не ошибка запроса). */
export function Notice({ text }: { text: string }) {
  const palette = usePalette();
  return (
    <View accessibilityRole="alert" style={[styles.notice, { backgroundColor: palette.warningBg }]}>
      <Icon name="alert" color={palette.warning} size={20} />
      <Text style={[styles.noticeText, { color: palette.warning }]}>{text}</Text>
    </View>
  );
}

interface CardProps {
  title?: string;
  icon?: IconName;
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
}

export function Card({ title, icon, children, style }: CardProps) {
  const palette = usePalette();
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: palette.card, borderColor: palette.border },
        elevation(palette, 1),
        style,
      ]}
    >
      {title ? (
        <View style={styles.cardHeader}>
          {icon ? (
            <View style={[styles.cardIcon, { backgroundColor: palette.accentSoft }]}>
              <Icon name={icon} color={palette.accent} size={18} />
            </View>
          ) : null}
          <Text accessibilityRole="header" style={[styles.cardTitle, { color: palette.text }]}>
            {title}
          </Text>
        </View>
      ) : null}
      {children}
    </View>
  );
}

/** Фирменная градиентная поверхность: баланс, приветствие, итог сценария. */
export function Hero({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const palette = usePalette();
  return (
    <LinearGradient
      colors={[...palette.brand]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={[styles.hero, elevation(palette, 3), style]}
    >
      <View pointerEvents="none" style={[styles.orb, styles.orbBig]} />
      <View pointerEvents="none" style={[styles.orb, styles.orbSmall]} />
      {children}
    </LinearGradient>
  );
}

interface ButtonProps {
  testID?: string;
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "primary" | "secondary";
  icon?: IconName;
  /** Иконка после текста — для «дальше»-действий. */
  trailingIcon?: IconName;
}

export function Button({
  label,
  onPress,
  loading,
  disabled,
  testID,
  icon,
  trailingIcon,
  variant = "primary",
}: ButtonProps) {
  const palette = usePalette();
  const primary = variant === "primary";
  const inactive = Boolean(disabled || loading);
  const color = primary ? palette.accentText : palette.accent;
  const content = loading ? (
    <ActivityIndicator color={color} />
  ) : (
    <View style={styles.buttonRow}>
      {icon ? <Icon name={icon} color={color} size={20} /> : null}
      <Text style={[styles.buttonText, { color }]}>{label}</Text>
      {trailingIcon ? <Icon name={trailingIcon} color={color} size={20} /> : null}
    </View>
  );
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: inactive, busy: Boolean(loading) }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [
        styles.buttonShell,
        primary && !inactive ? elevation(palette, 2) : null,
        { opacity: inactive ? 0.5 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] },
      ]}
    >
      {primary ? (
        <LinearGradient
          colors={[...palette.brand]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={styles.button}
        >
          {content}
        </LinearGradient>
      ) : (
        <View style={[styles.button, { backgroundColor: palette.accentSoft }]}>{content}</View>
      )}
    </Pressable>
  );
}

interface TileProps {
  label: string;
  icon: IconName;
  onPress: () => void;
  hint?: string;
  testID?: string;
}

/** Плитка быстрого действия на главной. */
export function ActionTile({ label, icon, onPress, hint, testID }: TileProps) {
  const palette = usePalette();
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [
        styles.tile,
        { backgroundColor: palette.card, borderColor: palette.border },
        elevation(palette, 1),
        { transform: [{ scale: pressed ? 0.97 : 1 }] },
      ]}
    >
      <View style={[styles.tileIcon, { backgroundColor: palette.accentSoft }]}>
        <Icon name={icon} color={palette.accent} size={20} />
      </View>
      <Text style={[styles.tileLabel, { color: palette.text }]}>{label}</Text>
      {hint ? <Text style={[styles.tileHint, { color: palette.muted }]}>{hint}</Text> : null}
    </Pressable>
  );
}

/** Показатель: подпись сверху, крупное значение снизу. */
export function Stat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "danger" | "ok";
}) {
  const palette = usePalette();
  const color = tone === "danger" ? palette.danger : tone === "ok" ? palette.ok : palette.text;
  return (
    <View style={[styles.stat, { backgroundColor: palette.background }]}>
      <Text style={[styles.statLabel, { color: palette.muted }]}>{label}</Text>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
    </View>
  );
}

type BadgeTone = "muted" | "warning" | "ok" | "hero";

export function Badge({ label, tone = "muted" }: { label: string; tone?: BadgeTone }) {
  const palette = usePalette();
  const [bg, fg] =
    tone === "warning"
      ? [palette.warningBg, palette.warning]
      : tone === "ok"
        ? [palette.okSoft, palette.ok]
        : tone === "hero"
          ? [palette.heroChip, palette.heroText]
          : [palette.track, palette.muted];
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[styles.badgeText, { color: fg }]}>{label}</Text>
    </View>
  );
}

export function LoadingState({ label }: { label: string }) {
  const palette = usePalette();
  return (
    <View style={styles.state} accessibilityLiveRegion="polite">
      <View style={[styles.stateIcon, { backgroundColor: palette.accentSoft }]}>
        <ActivityIndicator color={palette.accent} />
      </View>
      <Text style={[styles.stateText, { color: palette.muted }]}>{label}</Text>
    </View>
  );
}

interface ErrorStateProps {
  title: string;
  message: string;
  hint?: string;
  retryLabel?: string;
  onRetry?: () => void;
}

export function ErrorState({ title, message, hint, retryLabel, onRetry }: ErrorStateProps) {
  const palette = usePalette();
  return (
    <View style={styles.state} accessibilityRole="alert">
      <View style={[styles.stateIcon, { backgroundColor: palette.dangerSoft }]}>
        <Icon name="alert" color={palette.danger} />
      </View>
      <Text style={[styles.errorTitle, { color: palette.danger }]}>{title}</Text>
      <Text style={[styles.stateText, { color: palette.text }]}>{message}</Text>
      {hint ? <Text style={[styles.stateText, { color: palette.muted }]}>{hint}</Text> : null}
      {onRetry ? (
        <View style={styles.retry}>
          <Button label={retryLabel ?? "Повторить"} onPress={onRetry} variant="secondary" />
        </View>
      ) : null}
    </View>
  );
}

export function Muted({ children }: { children: ReactNode }) {
  const palette = usePalette();
  return <Text style={[styles.muted, { color: palette.muted }]}>{children}</Text>;
}

const styles = StyleSheet.create({
  notice: {
    borderRadius: radius.md,
    padding: space.md,
    flexDirection: "row",
    gap: space.sm,
    alignItems: "flex-start",
  },
  noticeText: { flex: 1, fontSize: 15, lineHeight: 21, fontWeight: "600" },
  screen: { padding: space.lg, alignItems: "center" },
  glow: { position: "absolute", left: 0, right: 0, top: 0, height: 460 },
  column: { width: "100%", maxWidth: 720, gap: space.lg },
  card: {
    borderRadius: radius.lg,
    padding: space.lg + 4,
    gap: space.md,
    borderWidth: StyleSheet.hairlineWidth,
  },
  cardHeader: { flexDirection: "row", alignItems: "center", gap: space.sm + 2 },
  cardIcon: { width: 32, height: 32, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  cardTitle: { fontSize: 18, fontWeight: "700", letterSpacing: -0.2, flexShrink: 1 },
  hero: { borderRadius: radius.xl, padding: space.xl, gap: space.md, overflow: "hidden" },
  orb: { position: "absolute", borderRadius: 999, backgroundColor: "rgba(255,255,255,0.09)" },
  orbBig: { width: 260, height: 260, top: -120, right: -80 },
  orbSmall: { width: 140, height: 140, bottom: -70, left: -40 },
  buttonShell: { borderRadius: radius.md },
  button: {
    minHeight: 52,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: space.lg,
  },
  buttonRow: { flexDirection: "row", alignItems: "center", gap: space.sm },
  buttonText: { fontSize: 16, fontWeight: "700", letterSpacing: 0.1 },
  tile: {
    flexGrow: 1,
    flexBasis: "45%",
    minHeight: 112,
    borderRadius: radius.lg,
    padding: space.lg,
    gap: space.sm,
    borderWidth: StyleSheet.hairlineWidth,
  },
  tileIcon: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  tileLabel: { fontSize: 15, fontWeight: "700", lineHeight: 20 },
  tileHint: { fontSize: 12, lineHeight: 16 },
  stat: { flex: 1, borderRadius: radius.md, padding: space.md, gap: 2 },
  statLabel: { fontSize: 12, fontWeight: "600" },
  statValue: { fontSize: 18, fontWeight: "800", letterSpacing: -0.3 },
  badge: {
    borderRadius: radius.pill,
    paddingHorizontal: space.md - 2,
    paddingVertical: 4,
    alignSelf: "flex-start",
  },
  badgeText: { fontSize: 12, fontWeight: "700" },
  state: { alignItems: "center", gap: space.md, paddingVertical: space.xl },
  stateIcon: { width: 52, height: 52, borderRadius: 18, alignItems: "center", justifyContent: "center" },
  stateText: { fontSize: 15, textAlign: "center", lineHeight: 21 },
  errorTitle: { fontSize: 18, fontWeight: "700" },
  retry: { alignSelf: "stretch" },
  muted: { fontSize: 14, lineHeight: 21 },
  field: { gap: space.sm - 2 },
  fieldLabel: { fontSize: 13, fontWeight: "700", letterSpacing: 0.2 },
  fieldHint: { fontSize: 13, lineHeight: 18 },
  input: {
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: space.md + 2,
    paddingVertical: space.sm + 2,
    fontSize: 16,
    minHeight: 52,
  },
  inputMultiline: { minHeight: 160, textAlignVertical: "top" },
  mono: { fontFamily: "monospace", fontSize: 13 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  chip: { borderRadius: radius.pill, paddingHorizontal: space.md + 2, paddingVertical: 9 },
});
