import { LinearGradient } from "expo-linear-gradient";
import { useRef, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Animated,
  Platform,
  Pressable,
  StyleSheet,
  TextInput,
  View,
  type KeyboardTypeOptions,
  type PressableStateCallbackType,
  type TextInputProps,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { AppShell } from "./shell";
import { Icon, type IconName } from "./icons";
import { Text } from "./text";
import { useReducedMotion } from "./motion";
import {
  elevation,
  fonts,
  radius,
  space,
  typeScale,
  usePalette,
} from "./theme";

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
  secureTextEntry?: boolean;
  autoComplete?: TextInputProps["autoComplete"];
  autoCapitalize?: TextInputProps["autoCapitalize"];
}
export function Field(props: FieldProps) {
  const palette = usePalette();
  const [focused, setFocused] = useState(false);
  return (
    <View style={styles.field}>
      <Text style={[styles.fieldLabel, { color: palette.text }]}>
        {props.label}
      </Text>
      <TextInput
        testID={props.testID}
        accessibilityLabel={props.label}
        value={props.value}
        onChangeText={props.onChangeText}
        placeholder={props.placeholder}
        placeholderTextColor={palette.placeholder}
        multiline={props.multiline}
        keyboardType={props.keyboardType}
        secureTextEntry={props.secureTextEntry}
        autoComplete={props.autoComplete}
        autoCapitalize={props.autoCapitalize ?? "none"}
        autoCorrect={false}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={[
          styles.input,
          props.multiline && styles.inputMultiline,
          {
            fontFamily: props.monospace ? fonts.mono : fonts.regular,
            color: palette.text,
            backgroundColor: palette.background,
            borderColor: props.error
              ? palette.danger
              : focused
                ? palette.accent
                : palette.inputBorder,
            boxShadow: focused ? `0 0 0 3px ${palette.focusRing}` : undefined,
          },
        ]}
      />
      {props.error ? (
        <Text
          accessibilityRole="alert"
          style={[styles.fieldHint, { color: palette.danger }]}
        >
          {props.error}
        </Text>
      ) : props.hint ? (
        <Text style={[styles.fieldHint, { color: palette.muted }]}>
          {props.hint}
        </Text>
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
export function Choice<T extends string>({
  label,
  options,
  value,
  onChange,
}: ChoiceProps<T>) {
  const palette = usePalette();
  return (
    <View style={styles.field}>
      {label ? (
        <Text style={[styles.fieldLabel, { color: palette.muted }]}>
          {label}
        </Text>
      ) : null}
      <View accessibilityRole="radiogroup" style={styles.chips}>
        {options.map((option) => {
          const active = option.value === value;
          return (
            <Pressable
              key={option.value}
              accessibilityRole="radio"
              accessibilityLabel={option.label}
              accessibilityState={{ checked: active }}
              aria-checked={active}
              onPress={() => onChange(option.value)}
              style={({ pressed, hovered }: PressState) => [
                styles.chip,
                {
                  backgroundColor: active
                    ? palette.primary
                    : hovered
                      ? palette.track
                      : palette.card,
                  borderColor: active ? palette.primary : palette.inputBorder,
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
export function Screen({
  children,
  wide,
  headerActions,
}: {
  children: ReactNode;
  topInset?: boolean;
  wide?: boolean;
  headerActions?: ReactNode;
}) {
  return (
    <AppShell wide={wide} headerActions={headerActions}>
      {children}
    </AppShell>
  );
}
export function Notice({ text }: { text: string }) {
  const palette = usePalette();
  return (
    <View
      accessibilityRole="alert"
      style={[
        styles.notice,
        { backgroundColor: palette.warningBg, borderColor: palette.warning },
      ]}
    >
      <Icon name="alert" color={palette.warning} size={18} />
      <Text style={[styles.noticeText, { color: palette.warning }]}>
        {text}
      </Text>
    </View>
  );
}
interface CardProps {
  title?: string;
  icon?: IconName;
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
}
export function Surface({
  children,
  style,
  elevated = false,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  elevated?: boolean;
}) {
  const palette = usePalette();
  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: elevated ? palette.surfaceElevated : palette.surface,
          borderColor: palette.border,
        },
        elevation(palette),
        style,
      ]}
    >
      {children}
    </View>
  );
}
export function Card({ title, icon, children, style }: CardProps) {
  const palette = usePalette();
  return (
    <Surface style={style}>
      {title ? (
        <View style={styles.cardHeader}>
          {icon ? <Icon name={icon} color={palette.muted} size={18} /> : null}
          <Text
            accessibilityRole="header"
            style={[styles.cardTitle, { color: palette.text }]}
          >
            {title}
          </Text>
        </View>
      ) : null}
      {children}
    </Surface>
  );
}
export function Hero({
  children,
  style,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
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
      <LinearGradient
        pointerEvents="none"
        colors={["rgba(125,160,202,0.25)", "rgba(5,38,89,0)"]}
        start={{ x: 1, y: 0 }}
        end={{ x: 0.1, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      <View
        pointerEvents="none"
        style={[styles.orbit, { right: -140, top: -190 }]}
      />
      <View
        pointerEvents="none"
        style={[styles.orbit, { right: -110, top: -160 }]}
      />
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
  variant?: "primary" | "secondary" | "inverse" | "danger";
  size?: "md" | "sm";
  icon?: IconName;
  trailingIcon?: IconName;
}
const AnimatedPressable = Animated.createAnimatedComponent(Pressable);
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
  const reduced = useReducedMotion();
  const scale = useRef(new Animated.Value(1)).current;
  const [focused, setFocused] = useState(false);
  const [hovered, setHovered] = useState(false);
  const inactive = Boolean(disabled || loading);
  const small = size === "sm";
  const [background, border, color] =
    disabled && !loading
      ? [palette.track, palette.border, palette.placeholder]
      : variant === "primary"
        ? [palette.primary, palette.primary, palette.primaryText]
        : variant === "inverse"
          ? ["#C1E8FF", "#C1E8FF", "#021024"]
          : variant === "danger"
            ? [palette.dangerSolid, palette.dangerSolid, "#ffffff"]
            : [palette.card, palette.inputBorder, palette.text];
  const press = (toValue: number) => {
    if (reduced) return;
    Animated.spring(scale, {
      toValue,
      speed: 32,
      bounciness: 3,
      useNativeDriver: Platform.OS !== "web",
    }).start();
  };
  return (
    <AnimatedPressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: inactive, busy: Boolean(loading) }}
      disabled={inactive}
      onPress={onPress}
      onPressIn={() => press(0.975)}
      onPressOut={() => press(1)}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onHoverIn={() => setHovered(true)}
      onHoverOut={() => setHovered(false)}
      style={[
        styles.button,
        small && styles.buttonSmall,
        {
          backgroundColor: background,
          borderColor: hovered && !inactive ? palette.accent : border,
          transform: [{ scale }],
          boxShadow: focused ? `0 0 0 3px ${palette.focusRing}` : undefined,
        },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={color} size="small" />
      ) : (
        <View style={styles.buttonRow}>
          {icon ? <Icon name={icon} color={color} size={18} /> : null}
          <Text
            style={[styles.buttonText, small && { fontSize: 13 }, { color }]}
          >
            {label}
          </Text>
          {trailingIcon ? (
            <Icon name={trailingIcon} color={color} size={18} />
          ) : null}
        </View>
      )}
    </AnimatedPressable>
  );
}
interface TileProps {
  label: string;
  icon: IconName;
  onPress: () => void;
  hint?: string;
  testID?: string;
}
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
          borderColor: hovered ? palette.accent : palette.border,
        },
      ]}
    >
      <Icon name={icon} color={palette.accent} size={20} />
      <Text style={[styles.tileLabel, { color: palette.text }]}>{label}</Text>
      {hint ? <Muted>{hint}</Muted> : null}
    </Pressable>
  );
}
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
  return (
    <View
      style={[
        styles.stat,
        { backgroundColor: palette.background, borderColor: palette.border },
      ]}
    >
      <Text style={[styles.statLabel, { color: palette.muted }]}>{label}</Text>
      <Text
        style={[
          styles.statValue,
          {
            color:
              tone === "danger"
                ? palette.danger
                : tone === "ok"
                  ? palette.ok
                  : palette.text,
          },
        ]}
      >
        {value}
      </Text>
    </View>
  );
}
type BadgeTone = "muted" | "warning" | "ok" | "hero";
export function Badge({
  label,
  tone = "muted",
}: {
  label: string;
  tone?: BadgeTone;
}) {
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
    <View
      accessibilityLiveRegion="polite"
      accessibilityLabel={label}
      style={{ gap: space.lg, paddingVertical: space.xl }}
    >
      <View style={styles.buttonRow}>
        <ActivityIndicator color={palette.accent} />
        <Muted>{label}</Muted>
      </View>
      <View
        importantForAccessibility="no-hide-descendants"
        accessibilityElementsHidden
        style={{ gap: space.md }}
      >
        {[100, 64, 84].map((width, index) => (
          <View
            key={index}
            style={{
              width: `${width}%`,
              height: index === 0 ? 160 : 24,
              borderRadius: radius.lg,
              backgroundColor: palette.track,
            }}
          />
        ))}
      </View>
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
export function ErrorState({
  title,
  message,
  hint,
  retryLabel,
  onRetry,
}: ErrorStateProps) {
  const palette = usePalette();
  return (
    <View
      style={[
        styles.state,
        {
          backgroundColor: palette.surface,
          borderColor: palette.border,
          borderWidth: 1,
          borderRadius: radius.lg,
        },
      ]}
      accessibilityRole="alert"
    >
      <Icon name="alert" color={palette.danger} size={24} />
      <Text style={[typeScale.heading, { color: palette.text }]}>{title}</Text>
      <Text style={[styles.stateText, { color: palette.muted }]}>
        {message}
      </Text>
      {hint ? (
        <Text style={[styles.stateText, { color: palette.muted }]}>{hint}</Text>
      ) : null}
      {onRetry ? (
        <Button
          label={retryLabel ?? "Повторить"}
          onPress={onRetry}
          variant="secondary"
        />
      ) : null}
    </View>
  );
}
export function EmptyState({
  title,
  message,
  icon = "wallet",
}: {
  title: string;
  message: string;
  icon?: IconName;
}) {
  const palette = usePalette();
  return (
    <View style={styles.state}>
      <Icon name={icon} color={palette.accent} size={24} />
      <Text style={[typeScale.heading, { color: palette.text }]}>{title}</Text>
      <Muted>{message}</Muted>
    </View>
  );
}
export function SuccessState({ message }: { message: string }) {
  const palette = usePalette();
  return (
    <View
      accessibilityRole="alert"
      style={[styles.notice, { backgroundColor: palette.okSoft }]}
    >
      <Icon name="check" color={palette.ok} size={20} />
      <Text style={[styles.noticeText, { color: palette.ok }]}>{message}</Text>
    </View>
  );
}
export function Muted({ children }: { children: ReactNode }) {
  const palette = usePalette();
  return (
    <Text style={[typeScale.body, { color: palette.muted }]}>{children}</Text>
  );
}
const styles = StyleSheet.create({
  field: { gap: 8 },
  fieldLabel: { fontSize: 13, fontWeight: "500", lineHeight: 20 },
  fieldHint: { fontSize: 13, lineHeight: 19 },
  input: {
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 15,
    minHeight: 48,
    outlineWidth: 0,
  },
  inputMultiline: { minHeight: 160, textAlignVertical: "top" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    minHeight: 44,
    justifyContent: "center",
    borderRadius: radius.md,
    borderWidth: 1,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  notice: {
    borderRadius: radius.md,
    padding: 16,
    flexDirection: "row",
    gap: 12,
    alignItems: "flex-start",
  },
  noticeText: { flex: 1, ...typeScale.body },
  card: {
    borderRadius: radius.lg,
    padding: 24,
    gap: 16,
    borderWidth: 1,
    minWidth: 0,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 4,
  },
  cardTitle: { ...typeScale.heading, flexShrink: 1 },
  hero: {
    borderRadius: radius.lg,
    borderWidth: 1,
    padding: 24,
    gap: 20,
    overflow: "hidden",
    minWidth: 0,
  },
  orbit: {
    position: "absolute",
    width: 440,
    height: 440,
    borderRadius: 220,
    borderWidth: 1,
    borderColor: "rgba(193,232,255,0.13)",
  },
  button: {
    minHeight: 48,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 18,
    paddingVertical: 10,
  },
  buttonSmall: { minHeight: 44, paddingHorizontal: 14 },
  buttonRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  buttonText: {
    fontSize: 14,
    fontWeight: "600",
    letterSpacing: -0.1,
    flexShrink: 1,
    textAlign: "center",
  },
  tile: {
    flexGrow: 1,
    flexBasis: "45%",
    minHeight: 100,
    borderRadius: radius.lg,
    padding: 20,
    gap: 12,
    borderWidth: 1,
  },
  tileLabel: { fontSize: 15, fontWeight: "500", lineHeight: 22 },
  stat: {
    flex: 1,
    minWidth: 120,
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 16,
    gap: 8,
  },
  statLabel: { fontSize: 12, lineHeight: 18, fontWeight: "500" },
  statValue: {
    fontSize: 24,
    lineHeight: 32,
    fontWeight: "600",
    letterSpacing: -0.8,
    fontVariant: ["tabular-nums"],
  },
  badge: {
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
    alignSelf: "flex-start",
    maxWidth: "100%",
  },
  badgeText: { fontSize: 11, lineHeight: 16, fontWeight: "500" },
  state: { alignItems: "center", gap: 16, padding: 24 },
  stateText: { ...typeScale.body, textAlign: "center" },
});
