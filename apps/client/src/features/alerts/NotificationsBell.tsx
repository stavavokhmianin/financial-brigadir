import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, StyleSheet, View } from "react-native";

import { api, type AlertItem } from "@/shared/api/client";
import { formatMoment } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { Badge, Muted } from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { elevation, radius, space, usePalette } from "@/shared/ui/theme";

interface Props {
  token: string;
}

/**
 * Уведомления живут в панели поверх главной, а не в самостоятельном разделе.
 * Пока сервер не хранит read_at, счётчик показывает активные отправленные события.
 */
export function NotificationsBell({ token }: Props) {
  const palette = usePalette();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AlertItem[] | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await api.listAlerts(token);
      setItems(response.items.filter((item) => item.action === "send"));
    } catch {
      setItems([]);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const count = items?.length ?? 0;

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${ru.alerts.bell}${count > 0 ? `: ${count}` : ""}`}
        accessibilityState={{ expanded: open }}
        onPress={() => {
          setOpen(true);
          void load();
        }}
        style={({ pressed }) => [
          styles.bell,
          { backgroundColor: palette.heroChip, opacity: pressed ? 0.76 : 1 },
        ]}
      >
        <Icon name="bell" color={palette.heroText} size={20} />
        {count > 0 ? (
          <View style={[styles.counter, { backgroundColor: palette.danger }]}> 
            <Text style={styles.counterText}>{count > 9 ? "9+" : count}</Text>
          </View>
        ) : null}
      </Pressable>

      <Modal
        animationType="fade"
        onRequestClose={() => setOpen(false)}
        transparent
        visible={open}
      >
        <View style={styles.overlay}>
          <Pressable
            accessibilityLabel={ru.alerts.close}
            accessibilityRole="button"
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
            <View style={styles.panelHead}>
              <View style={styles.panelTitle}>
                <Icon name="bell" color={palette.accent} size={20} />
                <Text accessibilityRole="header" style={[styles.title, { color: palette.text }]}>
                  {ru.alerts.panelTitle}
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                onPress={() => setOpen(false)}
                hitSlop={8}
              >
                <Text style={[styles.close, { color: palette.accent }]}>{ru.alerts.close}</Text>
              </Pressable>
            </View>

            {items === null ? (
              <ActivityIndicator color={palette.accent} />
            ) : items.length === 0 ? (
              <Muted>{ru.alerts.empty}</Muted>
            ) : (
              items.slice(0, 5).map((item) => (
                <View key={item.id} style={[styles.item, { borderColor: palette.border }]}> 
                  <View style={styles.itemHead}>
                    <Badge
                      label={item.priority === "critical" ? ru.alerts.critical : ru.alerts.normal}
                      tone={item.priority === "critical" ? "warning" : "muted"}
                    />
                    <Muted>{formatMoment(item.created_at)}</Muted>
                  </View>
                  <Text style={[styles.message, { color: palette.text }]}>
                    {item.message ?? item.reason_text}
                  </Text>
                </View>
              ))
            )}
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  bell: {
    width: 42,
    height: 42,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  counter: {
    position: "absolute",
    right: -3,
    top: -3,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 4,
    alignItems: "center",
    justifyContent: "center",
  },
  counterText: { color: "#ffffff", fontSize: 10, fontWeight: "800" },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.42)",
    padding: space.lg,
    alignItems: "flex-end",
    justifyContent: "flex-start",
  },
  panel: {
    width: "100%",
    maxWidth: 420,
    maxHeight: "82%",
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: space.lg,
    gap: space.md,
  },
  panelHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  panelTitle: { flexDirection: "row", alignItems: "center", gap: space.sm },
  title: { fontSize: 18, fontWeight: "800" },
  close: { fontSize: 14, fontWeight: "700" },
  item: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space.md, gap: space.sm },
  itemHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.sm },
  message: { fontSize: 14, lineHeight: 21 },
});
