import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { space, usePalette } from "./theme";

export function Screen({ children }: { children: ReactNode }) {
  const palette = usePalette();
  return (
    <ScrollView
      style={{ backgroundColor: palette.background }}
      contentContainerStyle={styles.screen}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.column}>{children}</View>
    </ScrollView>
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  const palette = usePalette();
  return (
    <View style={[styles.card, { backgroundColor: palette.card, borderColor: palette.border }]}>
      {title ? (
        <Text accessibilityRole="header" style={[styles.cardTitle, { color: palette.text }]}>
          {title}
        </Text>
      ) : null}
      {children}
    </View>
  );
}

interface ButtonProps {
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "primary" | "secondary";
}

export function Button({ label, onPress, loading, disabled, variant = "primary" }: ButtonProps) {
  const palette = usePalette();
  const primary = variant === "primary";
  const inactive = Boolean(disabled || loading);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy: Boolean(loading) }}
      disabled={inactive}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        {
          backgroundColor: primary ? palette.accent : "transparent",
          borderColor: palette.accent,
          opacity: inactive ? 0.6 : pressed ? 0.85 : 1,
        },
      ]}
    >
      {loading ? (
        <ActivityIndicator color={primary ? palette.accentText : palette.accent} />
      ) : (
        <Text style={[styles.buttonText, { color: primary ? palette.accentText : palette.accent }]}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

export function Badge({ label, tone = "muted" }: { label: string; tone?: "muted" | "warning" | "ok" }) {
  const palette = usePalette();
  const color = tone === "warning" ? palette.warning : tone === "ok" ? palette.ok : palette.muted;
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

export function LoadingState({ label }: { label: string }) {
  const palette = usePalette();
  return (
    <View style={styles.state} accessibilityLiveRegion="polite">
      <ActivityIndicator color={palette.accent} />
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
      <Text style={[styles.errorTitle, { color: palette.danger }]}>{title}</Text>
      <Text style={[styles.stateText, { color: palette.text }]}>{message}</Text>
      {hint ? <Text style={[styles.stateText, { color: palette.muted }]}>{hint}</Text> : null}
      {onRetry ? <Button label={retryLabel ?? "Повторить"} onPress={onRetry} variant="secondary" /> : null}
    </View>
  );
}

export function Muted({ children }: { children: ReactNode }) {
  const palette = usePalette();
  return <Text style={[styles.muted, { color: palette.muted }]}>{children}</Text>;
}

const styles = StyleSheet.create({
  screen: { padding: space.lg, alignItems: "center" },
  column: { width: "100%", maxWidth: 720, gap: space.lg },
  card: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 14, padding: space.lg, gap: space.md },
  cardTitle: { fontSize: 17, fontWeight: "600" },
  button: {
    minHeight: 48,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: space.lg,
  },
  buttonText: { fontSize: 16, fontWeight: "600" },
  badge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
    alignSelf: "flex-start",
  },
  badgeText: { fontSize: 12, fontWeight: "600" },
  state: { alignItems: "center", gap: space.md, paddingVertical: space.xl },
  stateText: { fontSize: 15, textAlign: "center" },
  errorTitle: { fontSize: 17, fontWeight: "600" },
  muted: { fontSize: 14, lineHeight: 20 },
});
