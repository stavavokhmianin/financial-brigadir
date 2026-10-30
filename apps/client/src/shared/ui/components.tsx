import { LinearGradient } from "expo-linear-gradient";
import { useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  type KeyboardTypeOptions,
  type PressableStateCallbackType,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon, type IconName } from "./icons";
import { Text } from "./text";
import { elevation, fonts, radius, space, usePalette } from "./theme";

/** react-native-web сообщает о наведении мыши; в типах React Native этого поля нет. */
export type PressState = PressableStateCallbackType & { hovered?: boolean };

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
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.field}>
      <Text style={[styles.fieldLabel, { color: palette.muted }]}>{props.label}</Text>
      <TextInput
        testID={props.testID}
        accessibilityLabel={props.label}
        value={props.value}
        onChangeText={props.onChangeText}
        placeholder={props.placeholder}
        placeholderTextColor={palette.placeholder}
        multiline={props.multiline}
        keyboardType={props.keyboardType}
        autoCapitalize="none"
        autoCorrect={false}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={[
          styles.input,
          props.multiline ? styles.inputMultiline : null,
          props.monospace ? styles.mono : { fontFamily: fonts.regular },
          {
            color: palette.text,
            borderColor: props.error ? palette.danger : focused ? palette.muted : palette.border,
            backgroundColor: palette.card,
          },
          // Кольцо фокуса, как у полей Geist: мягкий полупрозрачный ореол.
          focused
            ? { boxShadow: `0 0 0 3px ${props.error ? palette.dangerSoft : palette.focusRing}` }
            : null,
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
              style={({ pressed, hovered }: PressState) => [
                styles.chip,
                {
                  backgroundColor: active
                    ? palette.primary
                    : hovered
                      ? palette.track
                      : palette.card,
                  borderColor: active ? palette.primary : palette.border,
                  opacity: pressed ? 0.8 : 1,
                },
              ]}
            >
              <Text
                style={{
                  color: active ? palette.primaryText : palette.text,
                  fontSize: 14,
                  fontWeight: "500",
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
        { paddingBottom: space.xxl + bottom },
        topInset ? { paddingTop: space.xl + top } : null,
      ]}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.column}>{children}</View>
    </ScrollView>
  );
}

/** Заметная строка-пояснение над содержимым экрана (не ошибка запроса). */
export function Notice({ text }: { text: string }) {
  const palette = usePalette();
  return (
    <View
      accessibilityRole="alert"
      style={[styles.notice, { backgroundColor: palette.warningBg, borderColor: palette.warning }]}
    >
      <Icon name="alert" color={palette.warning} size={16} />
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
          {icon ? <Icon name={icon} color={palette.muted} size={16} /> : null}
          <Text accessibilityRole="header" style={[styles.cardTitle, { color: palette.text }]}>
            {title}
          </Text>
        </View>
      ) : null}
      {children}
    </View>
  );
}

/** Контрастная поверхность: баланс, приветствие, Plus. */
export function Hero({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const palette = usePalette();
  return (
    <View
      style={[
        styles.hero,
        { backgroundColor: palette.hero, borderColor: palette.heroBorder },
        elevation(palette, 2),
        style,
      ]}
    >
      {/* Едва заметный блик сверху и сетка — фирменная фактура поверхности. */}
      <LinearGradient
        pointerEvents="none"
        colors={["rgba(255,255,255,0.07)", "rgba(255,255,255,0)"]}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
        style={styles.heroShine}
      />
      <View pointerEvents="none" style={styles.heroGrid}>
        {[0, 1, 2, 3, 4].map((i) => (
          <View key={i} style={[styles.heroGridColumn, i < 4 ? styles.heroGridLine : null]} />
        ))}
      </View>
      {children}
    </View>
  );
}

interface ButtonProps {
  testID?: string;
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  /** inverse — светлая кнопка на контрастной поверхности (Hero); danger — необратимое действие. */
  variant?: "primary" | "secondary" | "inverse" | "danger";
  /** sm — компактная кнопка для действий внутри строки списка. */
  size?: "md" | "sm";
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
  size = "md",
}: ButtonProps) {
  const palette = usePalette();
  const inactive = Boolean(disabled || loading);
  const small = size === "sm";
  // Недоступная кнопка — нейтральная серая плашка, а не полупрозрачная заливка варианта.
  const muted = Boolean(disabled) && !loading;
  const [background, border, color] = muted
    ? [palette.track, palette.border, palette.placeholder]
    : variant === "primary"
      ? [palette.primary, palette.primary, palette.primaryText]
      : variant === "inverse"
        ? [palette.heroText, palette.heroText, palette.hero]
        : variant === "danger"
          ? [palette.dangerSolid, palette.dangerSolid, "#ffffff"]
          : [palette.card, palette.border, palette.text];
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: inactive, busy: Boolean(loading) }}
      disabled={inactive}
      onPress={onPress}
      // Компактная кнопка остаётся удобной для пальца: зона нажатия больше рамки.
      hitSlop={small ? 6 : undefined}
      style={({ pressed, hovered }: PressState) => {
        // Наведение: второстепенная кнопка темнеет до трека, залитые — чуть светлеют.
        const outlined = !muted && variant === "secondary";
        const hover = hovered && !inactive;
        return [
          styles.button,
          small ? styles.buttonSmall : null,
          {
            backgroundColor: hover && outlined ? palette.track : background,
            borderColor: border,
          },
          { opacity: loading ? 0.7 : pressed ? 0.82 : hover && !outlined ? 0.88 : 1 },
        ];
      }}
    >
      {loading ? (
        <ActivityIndicator color={color} size="small" />
      ) : (
        <View style={styles.buttonRow}>
          {icon ? <Icon name={icon} color={color} size={small ? 14 : 16} /> : null}
          <Text style={[styles.buttonText, small ? styles.buttonTextSmall : null, { color }]}>
            {label}
          </Text>
          {trailingIcon ? <Icon name={trailingIcon} color={color} size={small ? 14 : 16} /> : null}
        </View>
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
      style={({ pressed, hovered }: PressState) => [
        styles.tile,
        {
          backgroundColor: pressed ? palette.track : palette.card,
          // Как карточки Vercel: при наведении рамка темнеет, фон не меняется.
          borderColor: hovered ? palette.muted : palette.border,
        },
      ]}
    >
      <View style={[styles.tileIcon, { borderColor: palette.border }]}>
        <Icon name={icon} color={palette.text} size={16} />
      </View>
      <Text
        android_hyphenationFrequency="none"
        style={[styles.tileLabel, { color: palette.text }]}
      >
        {label}
      </Text>
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
    <View style={[styles.stat, { borderColor: palette.border }]}>
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
      <ActivityIndicator color={palette.muted} />
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
      <View style={[styles.stateIcon, { borderColor: palette.border, backgroundColor: palette.card }]}>
        <Icon name="alert" color={palette.danger} size={18} />
      </View>
      <Text style={[styles.errorTitle, { color: palette.text }]}>{title}</Text>
      <Text style={[styles.stateText, { color: palette.muted }]}>{message}</Text>
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
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: space.md,
    paddingVertical: space.sm + 2,
    flexDirection: "row",
    gap: space.sm,
    alignItems: "flex-start",
  },
  noticeText: { flex: 1, fontSize: 14, lineHeight: 20, fontWeight: "500" },
  screen: { padding: space.lg, alignItems: "center" },
  column: { width: "100%", maxWidth: 720, gap: space.lg },
  card: {
    borderRadius: radius.lg,
    padding: space.lg + 4,
    gap: space.md,
    borderWidth: 1,
  },
  cardHeader: { flexDirection: "row", alignItems: "center", gap: space.sm },
  cardTitle: { fontSize: 16, fontWeight: "600", letterSpacing: -0.32, flexShrink: 1 },
  hero: {
    borderRadius: radius.lg,
    borderWidth: 1,
    padding: space.xl,
    gap: space.md,
    overflow: "hidden",
  },
  heroShine: { position: "absolute", left: 0, right: 0, top: 0, height: 160 },
  heroGrid: { ...StyleSheet.absoluteFillObject, flexDirection: "row" },
  heroGridColumn: { flex: 1 },
  heroGridLine: {
    borderRightWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.05)",
  },
  button: {
    minHeight: 44,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: space.lg,
  },
  buttonSmall: { minHeight: 32, borderRadius: radius.sm, paddingHorizontal: space.md },
  buttonRow: { flexDirection: "row", alignItems: "center", gap: space.sm },
  buttonText: { fontSize: 15, fontWeight: "500", letterSpacing: -0.1 },
  buttonTextSmall: { fontSize: 13 },
  tile: {
    flexGrow: 1,
    flexBasis: "45%",
    minHeight: 104,
    borderRadius: radius.lg,
    padding: space.lg,
    gap: space.sm,
    borderWidth: 1,
  },
  tileIcon: {
    width: 32,
    height: 32,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.xs,
  },
  tileLabel: { fontSize: 14, fontWeight: "500", lineHeight: 19, letterSpacing: -0.1 },
  tileHint: { fontSize: 12, lineHeight: 16 },
  stat: { flex: 1, borderRadius: radius.md, borderWidth: 1, padding: space.md, gap: 4 },
  statLabel: { fontSize: 12, fontWeight: "500" },
  statValue: {
    fontSize: 20,
    fontWeight: "600",
    letterSpacing: -0.6,
    fontVariant: ["tabular-nums"],
  },
  badge: {
    borderRadius: radius.pill,
    paddingHorizontal: space.sm + 2,
    paddingVertical: 3,
    alignSelf: "flex-start",
  },
  badgeText: { fontSize: 12, fontWeight: "500" },
  state: { alignItems: "center", gap: space.md, paddingVertical: space.xl },
  stateIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  stateText: { fontSize: 14, textAlign: "center", lineHeight: 20 },
  errorTitle: { fontSize: 16, fontWeight: "600", letterSpacing: -0.32 },
  retry: { alignSelf: "stretch" },
  muted: { fontSize: 14, lineHeight: 21 },
  field: { gap: space.sm - 2 },
  fieldLabel: { fontSize: 13, fontWeight: "500" },
  fieldHint: { fontSize: 13, lineHeight: 18 },
  input: {
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.sm + 2,
    fontSize: 15,
    minHeight: 44,
    // Свою рамку и кольцо фокуса рисуем сами — системная обводка браузера не нужна.
    outlineWidth: 0,
  },
  inputMultiline: { minHeight: 160, textAlignVertical: "top" },
  mono: { fontFamily: fonts.mono, fontSize: 13 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  chip: {
    borderRadius: radius.pill,
    borderWidth: 1,
    paddingHorizontal: space.md + 2,
    paddingVertical: 7,
  },
});
