import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Animated, PanResponder, Pressable, StyleSheet, View } from "react-native";

import {
  api,
  ApiError,
  type Feedback,
  type FeedbackItem,
  type LabelResult,
  type TxLabel,
} from "@/shared/api/client";
import { formatDay, formatRub } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import {
  Badge,
  ErrorState,
  Field,
  LoadingState,
  Muted,
  type PressState,
} from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { radius, space, usePalette } from "@/shared/ui/theme";

interface Applied {
  id: string;
  label: TxLabel | null;
  result: LabelResult;
}

interface Props {
  token: string;
  /** Меняется, когда пришли новые операции: очередь пора перечитать. */
  refreshKey: number;
  /** Метка изменила модель: главной пора обновить прогноз. */
  onLabeled: () => void;
}

export function FeedbackCard({ token, refreshKey, onLabeled }: Props) {
  const [data, setData] = useState<Feedback | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [applied, setApplied] = useState<Applied | null>(null);
  const [skipped, setSkipped] = useState<Set<string>>(() => new Set());
  const [userNote, setUserNote] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await api.getFeedback(token));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ru.server.unknown);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  // Новые операции начинают новую лёгкую очередь; пропуски живут только в текущем просмотре.
  useEffect(() => {
    setSkipped(new Set());
  }, [refreshKey]);

  const mark = async (
    id: string,
    label: TxLabel | null,
    note?: string | null,
  ) => {
    setSaving(id);
    setSaveError(null);
    try {
      const result = await api.setTransactionLabel(token, id, label, note);
      setApplied({ id, label, result });
      onLabeled();
      await load();
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : ru.server.unknown);
    } finally {
      setSaving(null);
    }
  };

  const year = data?.items[0]?.transaction.occurred_at
    ? Number(data.items[0].transaction.occurred_at.slice(0, 4))
    : undefined;
  const visible =
    data?.items.filter((item) => !skipped.has(item.transaction.id)) ?? [];
  const current = visible[0] ?? null;

  useEffect(() => {
    setUserNote(current?.transaction.user_note ?? "");
  }, [current?.transaction.id, current?.transaction.user_note]);

  const skip = (id: string) => {
    setSkipped((previous) => new Set(previous).add(id));
  };

  return (
    <View style={styles.container}>
      {applied ? (
        <AppliedNote
          applied={applied}
          onUndo={() => void mark(applied.id, null)}
        />
      ) : null}
      {saveError ? (
        <Muted>{`${ru.feedback.saveError}: ${saveError}`}</Muted>
      ) : null}

      {error ? (
        <ErrorState
          title={ru.feedback.error}
          message={error}
          onRetry={() => void load()}
        />
      ) : data === null ? (
        <LoadingState label={ru.feedback.loading} />
      ) : current === null ? (
        <Muted>{ru.feedback.empty}</Muted>
      ) : (
        <Item
          key={current.transaction.id}
          item={current}
          year={year}
          saving={saving === current.transaction.id}
          disabled={saving !== null}
          total={visible.length}
          onSkip={() => skip(current.transaction.id)}
          userNote={userNote}
          onUserNoteChange={setUserNote}
          onMark={(label) =>
            void mark(current.transaction.id, label, userNote.trim() || null)
          }
        />
      )}
    </View>
  );
}

function Item({
  item,
  year,
  saving,
  disabled,
  total,
  onSkip,
  userNote,
  onUserNoteChange,
  onMark,
}: {
  item: FeedbackItem;
  year: number | undefined;
  saving: boolean;
  disabled: boolean;
  total: number;
  onSkip: () => void;
  userNote: string;
  onUserNoteChange: (value: string) => void;
  onMark: (label: TxLabel) => void;
}) {
  const palette = usePalette();
  const [showNote, setShowNote] = useState(false);
  const offset = useRef(new Animated.Value(0)).current;
  const tx = item.transaction;
  const choose = useCallback(
    (label: "regular" | "one_off", direction: -1 | 1) => {
      if (disabled) return;
      Animated.timing(offset, {
        toValue: direction * 420,
        duration: 180,
        useNativeDriver: true,
      }).start(() => {
        offset.setValue(0);
        onMark(label);
      });
    },
    [disabled, offset, onMark],
  );
  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, gesture) =>
          !disabled &&
          Math.abs(gesture.dx) > 12 &&
          Math.abs(gesture.dx) > Math.abs(gesture.dy),
        onPanResponderMove: (_, gesture) => offset.setValue(gesture.dx),
        onPanResponderRelease: (_, gesture) => {
          if (gesture.dx > 72) choose("regular", 1);
          else if (gesture.dx < -72) choose("one_off", -1);
          else {
            Animated.spring(offset, {
              toValue: 0,
              useNativeDriver: true,
            }).start();
          }
        },
        onPanResponderTerminate: () =>
          Animated.spring(offset, {
            toValue: 0,
            useNativeDriver: true,
          }).start(),
      }),
    [choose, disabled, offset],
  );
  return (
    <View style={styles.item}>
      <View style={styles.progressRow}>
        <Muted>{`${ru.feedback.remaining}: ${total}`}</Muted>
        <Muted>{ru.feedback.swipeHint}</Muted>
      </View>
      <View style={[styles.progressTrack, { backgroundColor: palette.track }]}>
        <View
          style={[
            styles.progressFill,
            {
              backgroundColor: palette.accent,
              width: `${Math.max(12, 100 / total)}%`,
            },
          ]}
        />
      </View>
      <Animated.View
        {...pan.panHandlers}
        style={[
          styles.purchase,
          { backgroundColor: palette.surface, borderColor: palette.border },
          {
            transform: [
              { translateX: offset },
              {
                rotate: offset.interpolate({
                  inputRange: [-220, 0, 220],
                  outputRange: ["-3deg", "0deg", "3deg"],
                  extrapolate: "clamp",
                }),
              },
            ],
          },
        ]}
      >
        <View style={styles.purchaseTop}>
          <View style={styles.itemMain}>
            <Text style={[styles.itemTitle, { color: palette.text }]}>
              {tx.description ?? tx.category ?? ru.feedback.fallbackTitle}
            </Text>
            <Muted>{formatDay(tx.occurred_at.slice(0, 10), year)}</Muted>
          </View>
          <Badge
            label={ru.feedback.reasons[item.reason]}
            tone={item.reason === "large" ? "warning" : "muted"}
          />
        </View>
        <Text style={[styles.amount, { color: palette.text }]}>
          {formatRub(Math.abs(tx.amount_minor))}
        </Text>
        <Muted>Сумма операции</Muted>
      </Animated.View>
      <Text style={[styles.question, { color: palette.text }]}>
        {ru.feedback.question}
      </Text>
      <Muted>{ru.feedback.questionHint}</Muted>
      {saving ? (
        <Muted>{ru.feedback.saving}</Muted>
      ) : (
        <>
          <View style={styles.primaryChoices}>
            {(["regular", "one_off"] as const).map((label) => (
              <Answer
                key={label}
                title={ru.feedback.labels[label]}
                transaction={tx.description ?? ""}
                disabled={disabled}
                tone={label}
                onPress={() => choose(label, label === "regular" ? 1 : -1)}
              />
            ))}
          </View>
        </>
      )}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: showNote }}
        onPress={() => setShowNote((value) => !value)}
        hitSlop={8}
      >
        <Text style={[styles.noteToggle, { color: palette.accent }]}>
          {showNote ? "Скрыть комментарий" : ru.feedback.note}
        </Text>
      </Pressable>
      {showNote ? (
        <Field
          label={ru.feedback.note}
          value={userNote}
          onChangeText={onUserNoteChange}
          placeholder={ru.feedback.notePlaceholder}
          hint={ru.feedback.noteHint}
          multiline
        />
      ) : null}
      <Pressable
        accessibilityRole="button"
        disabled={disabled}
        onPress={onSkip}
        hitSlop={8}
      >
        <Text style={[styles.skip, { color: palette.muted }]}>
          {ru.feedback.unknown}
        </Text>
      </Pressable>
    </View>
  );
}

function Answer({
  title,
  transaction,
  disabled,
  tone,
  onPress,
}: {
  title: string;
  transaction: string;
  disabled: boolean;
  tone: "regular" | "one_off";
  onPress: () => void;
}) {
  const palette = usePalette();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${title}: ${transaction}`}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed, hovered }: PressState) => [
        styles.primaryChoice,
        {
          borderColor: tone === "regular" ? palette.ok : palette.border,
          backgroundColor:
            pressed || hovered
              ? tone === "regular"
                ? palette.okSoft
                : palette.accentSoft
              : palette.card,
          opacity: disabled ? 0.5 : 1,
        },
      ]}
    >
      <Text style={[styles.primaryChoiceText, { color: palette.text }]}>
        {title}
      </Text>
    </Pressable>
  );
}

function AppliedNote({
  applied,
  onUndo,
}: {
  applied: Applied;
  onUndo: () => void;
}) {
  const palette = usePalette();
  const title =
    applied.result.transaction.description ??
    applied.result.transaction.category ??
    ru.feedback.fallbackTitle;
  return (
    <View
      accessibilityLiveRegion="polite"
      style={[styles.applied, { backgroundColor: palette.okSoft }]}
    >
      <View style={styles.appliedHead}>
        <Icon name="check" color={palette.ok} size={18} />
        <Text style={[styles.appliedTitle, { color: palette.text }]}>
          {applied.label === null
            ? `${title}: ответ отменён`
            : `${title}: ${ru.feedback.labels[applied.label].toLocaleLowerCase()}`}
        </Text>
      </View>
      {applied.label !== null ? (
        <Pressable accessibilityRole="button" onPress={onUndo} hitSlop={8}>
          <Text style={[styles.undo, { color: palette.accent }]}>
            {ru.feedback.undo}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: space.md },
  item: {
    gap: space.md,
  },
  progressRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space.sm,
  },
  progressTrack: { height: 4, borderRadius: radius.pill, overflow: "hidden" },
  progressFill: { height: 4, borderRadius: radius.pill },
  purchase: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: space.lg,
    gap: space.xs,
  },
  purchaseTop: {
    flexDirection: "row",
    gap: space.md,
    alignItems: "flex-start",
  },
  itemMain: { flex: 1, gap: 2 },
  itemTitle: { fontSize: 16, lineHeight: 22, fontWeight: "600" },
  amount: {
    fontSize: 34,
    lineHeight: 42,
    fontWeight: "600",
    letterSpacing: -1.2,
    fontVariant: ["tabular-nums"],
    paddingTop: space.sm,
  },
  question: {
    fontSize: 16,
    fontWeight: "600",
    lineHeight: 22,
    letterSpacing: -0.32,
    paddingTop: space.xs,
  },
  primaryChoices: { flexDirection: "row", gap: space.sm },
  primaryChoice: {
    flex: 1,
    minHeight: 64,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
  },
  primaryChoiceText: { fontSize: 15, fontWeight: "700", textAlign: "center" },
  noteToggle: {
    minHeight: 44,
    paddingVertical: 12,
    fontSize: 13,
    fontWeight: "600",
  },
  skip: {
    minHeight: 44,
    minWidth: 44,
    fontSize: 13,
    fontWeight: "500",
    paddingVertical: space.sm,
    textAlign: "center",
  },
  applied: { borderRadius: radius.md, padding: space.md, gap: space.xs },
  appliedHead: {
    flexDirection: "row",
    gap: space.sm,
    alignItems: "flex-start",
  },
  appliedTitle: { flex: 1, fontSize: 14, fontWeight: "700", lineHeight: 20 },
  undo: {
    minHeight: 44,
    minWidth: 44,
    fontSize: 14,
    fontWeight: "500",
    paddingTop: space.xs,
  },
});
