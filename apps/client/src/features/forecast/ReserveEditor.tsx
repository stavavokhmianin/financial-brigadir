import { useState } from "react";
import { Modal, Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, ApiError } from "@/shared/api/client";
import { formatRub } from "@/shared/format";
import { parseRubInput } from "@/shared/input";
import { Button, Field } from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { useReducedMotion } from "@/shared/ui/motion";
import { Text } from "@/shared/ui/text";
import { elevation, radius, space, typeScale, usePalette } from "@/shared/ui/theme";

const QUICK_VALUES = [500_000, 1_000_000, 3_000_000, 5_000_000] as const;

function inputValue(minor: number): string {
  const rubles = Math.floor(minor / 100);
  const kopecks = minor % 100;
  return kopecks ? `${rubles},${String(kopecks).padStart(2, "0")}` : String(rubles);
}

function parseReserve(text: string) {
  const normalized = text.replace(/[\s  ₽]/g, "").replace(",", ".");
  if (/^0+(?:\.0{1,2})?$/.test(normalized)) {
    return { ok: true as const, value: 0 };
  }
  return parseRubInput(text);
}

export function ReserveEditor({
  token,
  reserveMinor,
  onSaved,
}: {
  token: string;
  reserveMinor: number;
  onSaved: () => void | Promise<void>;
}) {
  const palette = usePalette();
  const insets = useSafeAreaInsets();
  const reducedMotion = useReducedMotion();
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(inputValue(reserveMinor));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const show = () => {
    setAmount(inputValue(reserveMinor));
    setError(null);
    setOpen(true);
  };

  const save = async () => {
    const parsed = parseReserve(amount);
    if (!parsed.ok) {
      setError(parsed.error);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.updateRiskPreferences(token, parsed.value);
      await onSaved();
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось сохранить настройку.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Изменить неснижаемый остаток, сейчас ${formatRub(reserveMinor)}`}
        accessibilityState={{ expanded: open }}
        onPress={show}
        style={({ pressed, hovered }) => [
          styles.trigger,
          {
            backgroundColor: hovered ? palette.track : "transparent",
            borderColor: hovered ? palette.inputBorder : "transparent",
            opacity: pressed ? 0.76 : 1,
          },
        ]}
      >
        <View style={styles.triggerText}>
          <Text style={[styles.label, { color: palette.muted }]}>Неснижаемый остаток</Text>
          <Text style={[typeScale.heading, { color: palette.text }]}>
            {formatRub(reserveMinor)}
          </Text>
          <Text style={[styles.change, { color: palette.accent }]}>Изменить</Text>
        </View>
        <Icon name="arrow" color={palette.accent} size={17} />
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
            {
              paddingTop: insets.top + space.md,
              paddingBottom: insets.bottom + space.md,
            },
          ]}
        >
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Закрыть настройку"
            onPress={() => setOpen(false)}
            style={StyleSheet.absoluteFill}
          />
          <View
            accessibilityViewIsModal
            style={[
              styles.sheet,
              { backgroundColor: palette.card, borderColor: palette.border },
              elevation(palette, 3),
            ]}
          >
            <View style={styles.head}>
              <View style={styles.headText}>
                <Text accessibilityRole="header" style={[typeScale.heading, { color: palette.text }]}>
                  Неснижаемый остаток
                </Text>
                <Text style={[styles.hint, { color: palette.muted }]}>
                  Сколько денег вы хотите оставить после будущих платежей и обычных расходов.
                </Text>
              </View>
              <Pressable accessibilityRole="button" onPress={() => setOpen(false)} hitSlop={8}>
                <Text style={[styles.close, { color: palette.muted }]}>Закрыть</Text>
              </Pressable>
            </View>

            <View style={styles.body}>
              <View style={styles.quickValues}>
                {QUICK_VALUES.map((value) => {
                  const parsed = parseReserve(amount);
                  const active = parsed.ok && parsed.value === value;
                  return (
                    <Pressable
                      key={value}
                      accessibilityRole="button"
                      accessibilityState={{ selected: active }}
                      onPress={() => {
                        setAmount(inputValue(value));
                        setError(null);
                      }}
                      style={({ pressed }) => [
                        styles.quick,
                        {
                          backgroundColor: active ? palette.primary : palette.background,
                          borderColor: active ? palette.primary : palette.inputBorder,
                          opacity: pressed ? 0.78 : 1,
                        },
                      ]}
                    >
                      <Text style={{ color: active ? palette.primaryText : palette.text }}>
                        {formatRub(value)}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
              <Field
                label="Своя сумма, ₽"
                value={amount}
                onChangeText={(value) => {
                  setAmount(value);
                  setError(null);
                }}
                keyboardType="decimal-pad"
                placeholder="Например, 30 000"
                error={error}
                hint="Можно указать 0 ₽, если отдельный запас сейчас не нужен."
              />
              <Button label="Сохранить и пересчитать" loading={saving} onPress={() => void save()} />
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  trigger: {
    flex: 0.7,
    minWidth: 160,
    minHeight: 96,
    padding: space.sm,
    margin: -space.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: space.sm,
  },
  triggerText: { flex: 1, gap: space.xs },
  label: { fontSize: 14, lineHeight: 20 },
  change: { fontSize: 12, lineHeight: 16, fontWeight: "600" },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(2,16,36,0.82)",
    paddingHorizontal: space.md,
    alignItems: "center",
    justifyContent: "center",
  },
  sheet: {
    width: "100%",
    maxWidth: 520,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.xl,
    overflow: "hidden",
  },
  head: {
    padding: space.lg,
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: space.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "rgba(127,127,127,0.24)",
  },
  headText: { flex: 1, gap: space.xs },
  hint: { fontSize: 13, lineHeight: 19 },
  close: { fontSize: 14, fontWeight: "500", paddingVertical: 4 },
  body: { padding: space.lg, gap: space.lg },
  quickValues: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  quick: {
    minHeight: 42,
    paddingHorizontal: space.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
});
