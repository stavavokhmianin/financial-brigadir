import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import {
  api,
  ApiError,
  type Feedback,
  type FeedbackItem,
  type LabelResult,
  type TxLabel,
} from "@/shared/api/client";
import { formatDay, formatRub, plural } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import {
  Badge,
  Card,
  ErrorState,
  Field,
  LoadingState,
  Muted,
  Stat,
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
  const palette = usePalette();
  const [data, setData] = useState<Feedback | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [applied, setApplied] = useState<Applied | null>(null);
  const [cursor, setCursor] = useState(0);
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
    setCursor(0);
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
  const safeCursor =
    visible.length === 0 ? 0 : Math.min(cursor, visible.length - 1);
  const current = visible[safeCursor] ?? null;

  useEffect(() => {
    setUserNote(current?.transaction.user_note ?? "");
  }, [current?.transaction.id, current?.transaction.user_note]);

  const skip = (id: string) => {
    setSkipped((previous) => new Set(previous).add(id));
    setCursor(0);
  };

  const move = (step: number) => {
    if (visible.length < 2) return;
    setCursor((value) => (value + step + visible.length) % visible.length);
  };

  return (
    <Card title={ru.feedback.title} icon="sparkle">
      <Muted>{ru.feedback.lead}</Muted>

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
          position={safeCursor + 1}
          total={visible.length}
          onPrevious={() => move(-1)}
          onNext={() => move(1)}
          onSkip={() => skip(current.transaction.id)}
          userNote={userNote}
          onUserNoteChange={setUserNote}
          onMark={(label) =>
            void mark(current.transaction.id, label, userNote.trim() || null)
          }
        />
      )}

      {data && (data.reducible_30d_minor > 0 || data.labeled > 0) ? (
        <View style={[styles.footer, { borderColor: palette.border }]}>
          {data.reducible_30d_minor > 0 ? (
            <>
              <Stat
                label={ru.feedback.reducible}
                value={formatRub(data.reducible_30d_minor)}
              />
              <Muted>{ru.feedback.reducibleNote}</Muted>
            </>
          ) : null}
          {data.labeled > 0 ? (
            <Muted>{`${data.labeled} ${plural(data.labeled, ru.feedback.labeled)}`}</Muted>
          ) : null}
        </View>
      ) : null}
    </Card>
  );
}

function Item({
  item,
  year,
  saving,
  disabled,
  position,
  total,
  onPrevious,
  onNext,
  onSkip,
  userNote,
  onUserNoteChange,
  onMark,
}: {
  item: FeedbackItem;
  year: number | undefined;
  saving: boolean;
  disabled: boolean;
  position: number;
  total: number;
  onPrevious: () => void;
  onNext: () => void;
  onSkip: () => void;
  userNote: string;
  onUserNoteChange: (value: string) => void;
  onMark: (label: TxLabel) => void;
}) {
  const palette = usePalette();
  const [showNote, setShowNote] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const tx = item.transaction;
  return (
    <View style={[styles.item, { borderColor: palette.border }]}>
      <View style={styles.progressRow}>
        <Muted>{`Покупка ${position} ${ru.feedback.of} ${total}`}</Muted>
        {total > 1 ? (
          <View style={styles.pager}>
            <Pressable
              accessibilityRole="button"
              onPress={onPrevious}
              hitSlop={8}
            >
              <Text style={[styles.pagerAction, { color: palette.accent }]}>
                {ru.feedback.previous}
              </Text>
            </Pressable>
            <Pressable accessibilityRole="button" onPress={onNext} hitSlop={8}>
              <Text style={[styles.pagerAction, { color: palette.accent }]}>
                {ru.feedback.next}
              </Text>
            </Pressable>
          </View>
        ) : null}
      </View>
      <View style={[styles.progressTrack, { backgroundColor: palette.track }]}>
        <View
          style={[
            styles.progressFill,
            {
              backgroundColor: palette.accent,
              width: `${Math.max(8, (position / total) * 100)}%`,
            },
          ]}
        />
      </View>
      <View
        style={[
          styles.purchase,
          { backgroundColor: palette.surface, borderColor: palette.border },
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
      </View>
      <Text style={[styles.question, { color: palette.text }]}>
        {ru.feedback.question}
      </Text>
      <Muted>{ru.feedback.questionHint}</Muted>
      {saving ? (
        <Muted>{ru.feedback.saving}</Muted>
      ) : (
        <>
          <View accessibilityRole="radiogroup" style={styles.primaryChoices}>
            {(["regular", "one_off"] as const).map((label) => (
              <Answer
                key={label}
                title={ru.feedback.labels[label]}
                transaction={tx.description ?? ""}
                checked={tx.label === label}
                disabled={disabled}
                primary
                onPress={() => onMark(label)}
              />
            ))}
          </View>
        </>
      )}
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: showMore }}
        onPress={() => setShowMore((value) => !value)}
        hitSlop={8}
      >
        <Text style={[styles.moreToggle, { color: palette.accent }]}>
          {showMore ? "Скрыть варианты" : "Другой вариант"}
        </Text>
      </Pressable>
      {showMore ? (
        <View style={styles.moreBlock}>
          <View accessibilityRole="radiogroup" style={styles.secondaryChoices}>
            {(["mandatory", "reducible"] as const).map((label) => (
              <Answer
                key={label}
                title={ru.feedback.labels[label]}
                transaction={tx.description ?? ""}
                checked={tx.label === label}
                disabled={disabled}
                onPress={() => onMark(label)}
              />
            ))}
          </View>
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
        </View>
      ) : null}
      <View style={styles.skipRow}>
        <Pressable
          accessibilityRole="button"
          disabled={disabled}
          onPress={onSkip}
          hitSlop={8}
        >
          <Text style={[styles.skip, { color: palette.muted }]}>
            {ru.feedback.skip}
          </Text>
        </Pressable>
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
    </View>
  );
}

function Answer({
  title,
  transaction,
  checked,
  disabled,
  primary = false,
  onPress,
}: {
  title: string;
  transaction: string;
  checked: boolean;
  disabled: boolean;
  primary?: boolean;
  onPress: () => void;
}) {
  const palette = usePalette();
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={`${title}: ${transaction}`}
      accessibilityState={{ checked, disabled }}
      aria-checked={checked}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed, hovered }: PressState) => [
        primary ? styles.primaryChoice : styles.secondaryChoice,
        {
          borderColor: checked ? palette.accent : palette.border,
          backgroundColor:
            checked || pressed || hovered ? palette.accentSoft : palette.card,
          opacity: disabled ? 0.5 : 1,
        },
      ]}
    >
      <Text
        style={[
          primary ? styles.primaryChoiceText : styles.secondaryChoiceText,
          { color: palette.text },
        ]}
      >
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
          {`${title}: ${ru.feedback.applied[applied.label ?? "none"]}`}
        </Text>
      </View>
      <Muted>
        {applied.label === null
          ? "Ответ отменён. Можно выбрать заново."
          : "Готово — прогноз обновлён, можно идти дальше."}
      </Muted>
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
  item: {
    gap: space.md,
  },
  progressRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space.sm,
  },
  pager: { flexDirection: "row", gap: space.md },
  pagerAction: {
    minHeight: 44,
    minWidth: 44,
    paddingVertical: 12,
    fontSize: 13,
    fontWeight: "500",
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
  secondaryChoices: { flexDirection: "row", gap: space.sm, flexWrap: "wrap" },
  secondaryChoice: {
    flexGrow: 1,
    flexBasis: "44%",
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: space.sm,
    paddingVertical: space.xs,
  },
  secondaryChoiceText: { fontSize: 13, fontWeight: "500", textAlign: "center" },
  moreToggle: {
    minHeight: 44,
    paddingVertical: 12,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
  },
  moreBlock: { gap: space.sm },
  noteToggle: {
    minHeight: 44,
    paddingVertical: 12,
    fontSize: 13,
    fontWeight: "600",
  },
  skipRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: space.md,
  },
  skip: {
    minHeight: 44,
    minWidth: 44,
    fontSize: 13,
    fontWeight: "500",
    paddingVertical: space.xs,
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
  footer: {
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: space.md,
    gap: space.xs,
  },
});
