import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import {
  api,
  ApiError,
  type RecurringCandidate,
  type RecurringConfirm,
} from "@/shared/api/client";
import { formatDay, formatRub, formatRubApprox, plural } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { Badge, Button, Card, Muted } from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { radius, space, usePalette } from "@/shared/ui/theme";

import { effectLines, regularity } from "./logic";

const t = ru.recurring;

interface Props {
  token: string;
  /** Меняется, когда пришли новые операции: кандидатов пора перечитать. */
  refreshKey: number;
  /** Обязательство добавлено: главной пора обновить календарь и прогноз. */
  onConfirmed: () => void;
}

/** «Похоже на регулярный платёж» (FR-11): повторения, которых нет в календаре. */
export function RecurringCard({ token, refreshKey, onConfirmed }: Props) {
  const [items, setItems] = useState<RecurringCandidate[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<RecurringConfirm | null>(null);

  const load = useCallback(async () => {
    try {
      setItems((await api.listRecurring(token)).items);
    } catch {
      // Блок вспомогательный: без него главная остаётся рабочей.
      setItems([]);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const decide = async (id: string, confirm: boolean) => {
    setBusy(id);
    setError(null);
    try {
      if (confirm) {
        setDone(await api.confirmRecurring(token, id));
        onConfirmed();
      } else {
        await api.rejectRecurring(token, id);
      }
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ru.server.unknown);
    } finally {
      setBusy(null);
    }
  };

  if (items.length === 0 && !done) return null;

  return (
    <Card title={t.title} icon="calendar">
      {items.length > 0 ? <Muted>{t.lead}</Muted> : null}
      {done ? <Confirmed result={done} /> : null}
      {error ? <Muted>{`${t.error}: ${error}`}</Muted> : null}
      {items.map((item) => (
        <Candidate
          key={item.id}
          item={item}
          busy={busy === item.id}
          disabled={busy !== null}
          onDecide={(confirm) => void decide(item.id, confirm)}
        />
      ))}
    </Card>
  );
}

function Candidate({
  item,
  busy,
  disabled,
  onDecide,
}: {
  item: RecurringCandidate;
  busy: boolean;
  disabled: boolean;
  onDecide: (confirm: boolean) => void;
}) {
  const palette = usePalette();
  const when =
    item.period === "weekly"
      ? `${t.weekly} ${t.weekdays[item.anchor] ?? ""}`
      : `${t.monthly} ${item.anchor}${t.monthlySuffix}`;
  const sure = regularity(item.confidence) === "sure";
  const amount =
    item.amount_min_minor === item.amount_max_minor
      ? formatRub(item.amount_minor)
      : formatRubApprox(item.amount_minor);
  return (
    <View style={[styles.item, { borderColor: palette.border }]}>
      <View style={styles.head}>
        <View style={styles.main}>
          <Text style={[styles.title, { color: palette.text }]}>{item.title}</Text>
          <Muted>{when}</Muted>
        </View>
        <View style={styles.side}>
          <Text style={[styles.amount, { color: palette.text }]}>{amount}</Text>
          <Badge label={sure ? t.sure : t.likely} tone={sure ? "ok" : "muted"} />
        </View>
      </View>
      <Muted>
        {`${t.seen} ${item.occurrences} ${plural(item.occurrences, t.times)}. ${t.next} ${formatDay(item.next_date)}.`}
      </Muted>
      <Button
        label={t.confirm}
        icon="plus"
        loading={busy}
        disabled={disabled}
        onPress={() => onDecide(true)}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${t.reject}: ${item.title}`}
        disabled={disabled}
        hitSlop={8}
        onPress={() => onDecide(false)}
        style={styles.rejectRow}
      >
        <Text style={[styles.reject, { color: palette.accent, opacity: disabled ? 0.5 : 1 }]}>
          {t.reject}
        </Text>
      </Pressable>
    </View>
  );
}

function Confirmed({ result }: { result: RecurringConfirm }) {
  const palette = usePalette();
  const lines = effectLines(result.effect, formatRubApprox);
  return (
    <View accessibilityLiveRegion="polite" style={[styles.done, { backgroundColor: palette.okSoft }]}>
      <View style={styles.doneHead}>
        <Icon name="check" color={palette.ok} size={18} />
        <Text style={[styles.doneTitle, { color: palette.text }]}>
          {`${result.obligation.title} — ${t.added} ${formatDay(result.obligation.due_date)}.`}
        </Text>
      </View>
      <Muted>{t.addedNote}</Muted>
      {lines.length === 0 ? <Muted>{t.unchanged}</Muted> : <Muted>{t.effect}</Muted>}
      {lines.map((line) => (
        <Text key={line.kind} style={[styles.line, { color: palette.text }]}>
          {line.kind === "risk"
            ? `${ru.feedback.risk}: ${ru.feedback.levels[line.from]} → ${ru.feedback.levels[line.to]}`
            : `${ru.feedback[line.kind]}: ${line.from} → ${line.to}`}
        </Text>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  item: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space.md, gap: space.sm },
  head: { flexDirection: "row", gap: space.md, alignItems: "flex-start" },
  main: { flex: 1, gap: 2 },
  side: { alignItems: "flex-end", gap: space.xs },
  title: { fontSize: 15, fontWeight: "700" },
  amount: { fontSize: 15, fontWeight: "800" },
  done: { borderRadius: radius.md, padding: space.md, gap: space.xs },
  doneHead: { flexDirection: "row", gap: space.sm, alignItems: "flex-start" },
  doneTitle: { flex: 1, fontSize: 14, fontWeight: "700", lineHeight: 20 },
  line: { fontSize: 14, lineHeight: 20 },
  rejectRow: { alignSelf: "center", paddingVertical: space.xs },
  reject: { fontSize: 14, fontWeight: "700" },
});
