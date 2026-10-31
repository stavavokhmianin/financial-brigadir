import { useRouter } from "expo-router";
import { useState, type ReactNode } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, View } from "react-native";

import { ru } from "@/shared/i18n/ru";
import { Muted } from "@/shared/ui/components";
import { Icon, type IconName } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { elevation, radius, space, usePalette } from "@/shared/ui/theme";

interface Props {
  isDemo: boolean;
  liveControl?: ReactNode;
  qualityNotes: string[];
  duplicates: number;
}

/** Служебные действия живут в одной панели и не конкурируют с финансовым содержанием. */
export function DashboardMenu({ isDemo, liveControl, qualityNotes, duplicates }: Props) {
  const router = useRouter();
  const palette = usePalette();
  const [open, setOpen] = useState(false);

  const go = (path: "/calendar" | "/add" | "/import" | "/alerts" | "/plans" | "/bank" | "/privacy" | "/duplicates") => {
    setOpen(false);
    router.push(path);
  };

  const actions: { label: string; icon: IconName; path: Parameters<typeof go>[0] }[] = [
    { label: ru.dashboard.calendar, icon: "calendar", path: "/calendar" },
    { label: ru.dashboard.add, icon: "plus", path: "/add" },
    { label: ru.dashboard.importCsv, icon: "upload", path: "/import" },
    { label: ru.alerts.settingsTitle, icon: "bell", path: "/alerts" },
    { label: ru.dashboard.plans, icon: "crown", path: "/plans" },
    ...(isDemo
      ? [{ label: ru.dashboard.bankMock, icon: "bank" as const, path: "/bank" as const }]
      : []),
    { label: ru.dashboard.privacy, icon: "shield", path: "/privacy" },
  ];

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={ru.dashboard.menu}
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen(true)}
        style={({ pressed }) => [
          styles.trigger,
          {
            backgroundColor: palette.heroChip,
            borderColor: "rgba(255,255,255,0.14)",
            opacity: pressed ? 0.76 : 1,
          },
        ]}
      >
        <Icon name="user" color={palette.heroText} size={18} />
      </Pressable>

      <Modal transparent visible={open} animationType="fade" onRequestClose={() => setOpen(false)}>
        <View style={styles.overlay}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={ru.alerts.close}
            onPress={() => setOpen(false)}
            style={StyleSheet.absoluteFill}
          />
          <View
            accessibilityViewIsModal
            style={[
              styles.panel,
              { backgroundColor: palette.card, borderColor: palette.border },
              elevation(palette, 3),
            ]}
          >
            <View style={styles.head}>
              <Text accessibilityRole="header" style={[styles.title, { color: palette.text }]}>
                {ru.dashboard.menuTitle}
              </Text>
              <Pressable accessibilityRole="button" onPress={() => setOpen(false)} hitSlop={8}>
                <Text style={[styles.close, { color: palette.muted }]}>{ru.alerts.close}</Text>
              </Pressable>
            </View>
            <ScrollView contentContainerStyle={styles.content}>
              {liveControl}
              {qualityNotes.length > 0 || duplicates > 0 ? (
                <View style={[styles.quality, { backgroundColor: palette.warningBg }]}> 
                  <Text style={[styles.qualityTitle, { color: palette.warning }]}>
                    {ru.dashboard.dataQuality}
                  </Text>
                  {qualityNotes.map((note) => <Muted key={note}>{note}</Muted>)}
                  {duplicates > 0 ? (
                    <Pressable accessibilityRole="button" onPress={() => go("/duplicates")}>
                      <Text style={[styles.qualityLink, { color: palette.accent }]}>
                        {`${ru.duplicates.dashboardTitle}: ${duplicates}`}
                      </Text>
                    </Pressable>
                  ) : null}
                </View>
              ) : null}
              <View style={styles.actions}>
                {actions.map((action) => (
                  <Pressable
                    key={action.path}
                    accessibilityRole="button"
                    onPress={() => go(action.path)}
                    style={({ pressed, hovered }) => [
                      styles.action,
                      {
                        borderColor: palette.border,
                        backgroundColor: pressed || hovered ? palette.track : palette.card,
                      },
                    ]}
                  >
                    <Icon name={action.icon} color={palette.muted} size={18} />
                    <Text style={[styles.actionText, { color: palette.text }]}>{action.label}</Text>
                    <Icon name="arrow" color={palette.muted} size={16} />
                  </Pressable>
                ))}
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  trigger: {
    width: 38,
    height: 38,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: "center",
    justifyContent: "center",
  },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.42)",
    padding: space.lg,
    alignItems: "flex-end",
    justifyContent: "flex-start",
  },
  panel: {
    width: "100%",
    maxWidth: 440,
    maxHeight: "90%",
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    overflow: "hidden",
  },
  head: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: space.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "rgba(127,127,127,0.24)",
  },
  title: { fontSize: 17, fontWeight: "600", letterSpacing: -0.3 },
  close: { fontSize: 14, fontWeight: "500" },
  content: { padding: space.lg, gap: space.lg },
  quality: { borderRadius: radius.md, padding: space.md, gap: space.xs },
  qualityTitle: { fontSize: 13, fontWeight: "600" },
  qualityLink: { fontSize: 13, fontWeight: "500", paddingTop: space.xs },
  actions: { gap: 0 },
  action: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingHorizontal: space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  actionText: { flex: 1, fontSize: 14, fontWeight: "500" },
});
