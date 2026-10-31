import { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Icon } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { useReducedMotion } from "@/shared/ui/motion";
import { elevation, radius, space, typeScale, usePalette } from "@/shared/ui/theme";

import { FeedbackCard } from "./FeedbackCard";
import { RecurringCard } from "./RecurringCard";

export function SpendingReview({
  token,
  refreshKey,
  hasRecurring,
  onRecurringChange,
  onChanged,
}: {
  token: string;
  refreshKey: number;
  hasRecurring: boolean | null;
  onRecurringChange: (value: boolean) => void;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const palette = usePalette();
  const insets = useSafeAreaInsets();
  const reducedMotion = useReducedMotion();

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Уточнить траты"
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen(true)}
        style={({ pressed, hovered }) => [
          styles.launch,
          {
            backgroundColor: hovered ? palette.accentSoft : palette.card,
            borderColor: palette.inputBorder,
            opacity: pressed ? 0.78 : 1,
          },
        ]}
      >
        <View style={[styles.launchIcon, { backgroundColor: palette.accentSoft }]}>
          <Icon name="sparkle" color={palette.accent} size={20} />
        </View>
        <View style={styles.launchText}>
          <Text style={[styles.launchTitle, { color: palette.text }]}>Уточнить траты</Text>
          <Text style={[styles.launchHint, { color: palette.muted }]}>
            Несколько быстрых ответов сделают прогноз личнее
          </Text>
        </View>
        <Icon name="arrow" color={palette.accent} size={18} />
      </Pressable>

      <Modal
        animationType={reducedMotion ? "none" : "fade"}
        transparent
        visible={open}
        onRequestClose={() => setOpen(false)}
      >
        <View
          style={[
            styles.overlay,
            { paddingTop: insets.top + space.md, paddingBottom: insets.bottom + space.md },
          ]}
        >
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Закрыть уточнение трат"
            onPress={() => setOpen(false)}
            style={StyleSheet.absoluteFill}
          />
          <View
            accessibilityViewIsModal
            style={[
              styles.sheet,
              { backgroundColor: palette.background, borderColor: palette.border },
              elevation(palette, 3),
            ]}
          >
            <View style={styles.head}>
              <View style={styles.headTitle}>
                <Icon name="sparkle" color={palette.accent} size={18} />
                <View style={{ flex: 1 }}>
                  <Text accessibilityRole="header" style={[typeScale.heading, { color: palette.text }]}>
                    Уточнить траты
                  </Text>
                  <Text style={[styles.headHint, { color: palette.muted }]}>Без правильных ответов и оценок</Text>
                </View>
              </View>
              <Pressable accessibilityRole="button" onPress={() => setOpen(false)} hitSlop={8}>
                <Text style={[styles.close, { color: palette.muted }]}>Закрыть</Text>
              </Pressable>
            </View>
            <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
              <RecurringCard
                token={token}
                refreshKey={refreshKey}
                onConfirmed={onChanged}
                onAvailabilityChange={onRecurringChange}
              />
              {hasRecurring === false ? (
                <FeedbackCard token={token} refreshKey={refreshKey} onLabeled={onChanged} />
              ) : null}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  launch: {
    minHeight: 82,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.md,
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
  },
  launchIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  launchText: { flex: 1, gap: 3 },
  launchTitle: { fontSize: 15, lineHeight: 20, fontWeight: "700" },
  launchHint: { fontSize: 12, lineHeight: 17 },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(2,16,36,0.82)",
    paddingHorizontal: space.md,
    alignItems: "center",
    justifyContent: "center",
  },
  sheet: {
    width: "100%",
    maxWidth: 620,
    maxHeight: "94%",
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.xl,
    padding: space.lg,
    gap: space.md,
  },
  head: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: space.md },
  headTitle: { flex: 1, flexDirection: "row", alignItems: "center", gap: space.sm },
  headHint: { fontSize: 12, lineHeight: 17, paddingTop: 2 },
  close: { minHeight: 44, paddingVertical: 11, fontSize: 13, fontWeight: "500" },
  content: { gap: space.md, paddingBottom: space.md },
});
