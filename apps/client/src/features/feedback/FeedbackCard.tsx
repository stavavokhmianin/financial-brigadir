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
import { formatDay, formatRub, formatRubApprox, plural } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { Badge, Card, ErrorState, LoadingState, Muted, Stat } from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { radius, space, usePalette } from "@/shared/ui/theme";

import { effectLines } from "./logic";

const LABELS: TxLabel[] = ["regular", "mandatory", "reducible", "one_off"];

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

  const mark = async (id: string, label: TxLabel | null) => {
    setSaving(id);
    setSaveError(null);
    try {
      const result = await api.setTransactionLabel(token, id, label);
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
  const visible = data?.items.filter((item) => !skipped.has(item.transaction.id)) ?? [];
  const safeCursor = visible.length === 0 ? 0 : Math.min(cursor, visible.length - 1);
  const current = visible[safeCursor] ?? null;

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

      {applied ? <AppliedNote applied={applied} onUndo={() => void mark(applied.id, null)} /> : null}
      {saveError ? <Muted>{`${ru.feedback.saveError}: ${saveError}`}</Muted> : null}

      {error ? (
        <ErrorState title={ru.feedback.error} message={error} onRetry={() => void load()} />
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
          onMark={(label) => void mark(current.transaction.id, label)}
        />
      )}

      {data && (data.reducible_30d_minor > 0 || data.labeled > 0) ? (
        <View style={[styles.footer, { borderColor: palette.border }]}>
          {data.reducible_30d_minor > 0 ? (
            <>
              <Stat label={ru.feedback.reducible} value={formatRub(data.reducible_30d_minor)} />
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
  onMark: (label: TxLabel) => void;
}) {
  const palette = usePalette();
  const tx = item.transaction;
  return (
    <View style={[styles.item, { borderColor: palette.border }]}>
      <View style={styles.progressRow}>
        <Muted>{`${position} ${ru.feedback.of} ${total} · ${ru.feedback.optional}`}</Muted>
        {total > 1 ? (
          <View style={styles.pager}>
            <Pressable accessibilityRole="button" onPress={onPrevious} hitSlop={8}>
              <Text style={[styles.pagerAction, { color: palette.accent }]}>{ru.feedback.previous}</Text>
            </Pressable>
            <Pressable accessibilityRole="button" onPress={onNext} hitSlop={8}>
              <Text style={[styles.pagerAction, { color: palette.accent }]}>{ru.feedback.next}</Text>
            </Pressable>
          </View>
        ) : null}
      </View>
      <View style={styles.itemHead}>
        <View style={styles.itemMain}>
          <Text style={[styles.itemTitle, { color: palette.text }]}>
            {tx.description ?? tx.category ?? "—"}
          </Text>
          <Muted>{formatDay(tx.occurred_at.slice(0, 10), year)}</Muted>
        </View>
        <View style={styles.itemSide}>
          <Text style={[styles.amount, { color: palette.text }]}>{formatRub(tx.amount_minor)}</Text>
          <Badge
            label={ru.feedback.reasons[item.reason]}
            tone={item.reason === "large" ? "warning" : "muted"}
          />
        </View>
      </View>
      <Text style={[styles.question, { color: palette.text }]}>{ru.feedback.question}</Text>
      <Muted>{ru.feedback.questionHint}</Muted>
      {saving ? (
        <Muted>{ru.feedback.saving}</Muted>
      ) : (
        <View accessibilityRole="radiogroup" style={styles.chips}>
          {LABELS.map((label) => (
            <Pressable
              key={label}
              accessibilityRole="radio"
              accessibilityLabel={`${ru.feedback.labels[label]}: ${tx.description ?? ""}`}
              accessibilityState={{ checked: tx.label === label, disabled }}
              disabled={disabled}
              onPress={() => onMark(label)}
              style={({ pressed }) => [
                styles.chip,
                {
                  borderColor: palette.border,
                  backgroundColor: pressed ? palette.accentSoft : palette.card,
                  opacity: disabled ? 0.5 : 1,
                },
              ]}
            >
              <Text style={[styles.chipText, { color: palette.text }]}>
                {ru.feedback.labels[label]}
              </Text>
            </Pressable>
          ))}
        </View>
      )}
      <View style={styles.skipRow}>
        <Pressable accessibilityRole="button" disabled={disabled} onPress={onSkip} hitSlop={8}>
          <Text style={[styles.skip, { color: palette.muted }]}>{ru.feedback.skip}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" disabled={disabled} onPress={onSkip} hitSlop={8}>
          <Text style={[styles.skip, { color: palette.muted }]}>{ru.feedback.unknown}</Text>
        </Pressable>
      </View>
    </View>
  );
}

function AppliedNote({ applied, onUndo }: { applied: Applied; onUndo: () => void }) {
  const palette = usePalette();
  const lines = effectLines(applied.result.effect, formatRubApprox);
  const title =
    applied.result.transaction.description ??
    applied.result.transaction.category ??
    ru.feedback.fallbackTitle;
  return (
    <View accessibilityLiveRegion="polite" style={[styles.applied, { backgroundColor: palette.okSoft }]}>
      <View style={styles.appliedHead}>
        <Icon name="check" color={palette.ok} size={18} />
        <Text style={[styles.appliedTitle, { color: palette.text }]}>
          {`${title}: ${ru.feedback.applied[applied.label ?? "none"]}`}
        </Text>
      </View>
      {lines.length === 0 ? (
        <Muted>{ru.feedback.unchanged}</Muted>
      ) : (
        <Muted>{ru.feedback.labelEffect}</Muted>
      )}
      {lines.length === 0
        ? null
        : lines.map((line) =>
          line.kind === "risk" ? (
            <Text key="risk" style={[styles.appliedLine, { color: palette.text }]}>
              {`${ru.feedback.risk}: ${ru.feedback.levels[line.from]} → ${ru.feedback.levels[line.to]}`}
            </Text>
          ) : (
            <Text key={line.kind} style={[styles.appliedLine, { color: palette.text }]}>
              {`${ru.feedback[line.kind]}: ${line.from} → ${line.to}`}
            </Text>
          ),
        )}
      {applied.label !== null ? (
        <Pressable accessibilityRole="button" onPress={onUndo} hitSlop={8}>
          <Text style={[styles.undo, { color: palette.accent }]}>{ru.feedback.undo}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  item: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space.md, gap: space.sm },
  progressRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.sm },
  pager: { flexDirection: "row", gap: space.md },
  pagerAction: { fontSize: 13, fontWeight: "700" },
  itemHead: { flexDirection: "row", gap: space.md, alignItems: "flex-start" },
  itemMain: { flex: 1, gap: 2 },
  itemSide: { alignItems: "flex-end", gap: space.xs },
  itemTitle: { fontSize: 15, fontWeight: "700" },
  amount: { fontSize: 15, fontWeight: "800" },
  question: { fontSize: 16, fontWeight: "800", lineHeight: 22, paddingTop: space.xs },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  chip: {
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: 6,
  },
  chipText: { fontSize: 13, fontWeight: "700" },
  skipRow: { flexDirection: "row", justifyContent: "space-between", gap: space.md },
  skip: { fontSize: 13, fontWeight: "700", paddingVertical: space.xs },
  applied: { borderRadius: radius.md, padding: space.md, gap: space.xs },
  appliedHead: { flexDirection: "row", gap: space.sm, alignItems: "flex-start" },
  appliedTitle: { flex: 1, fontSize: 14, fontWeight: "700", lineHeight: 20 },
  appliedLine: { fontSize: 14, lineHeight: 20 },
  undo: { fontSize: 14, fontWeight: "700", paddingTop: space.xs },
  footer: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space.md, gap: space.xs },
});
