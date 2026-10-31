import { Redirect, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, View, useWindowDimensions } from "react-native";

import { api, ApiError } from "@/shared/api/client";
import { addDays, formatDay, formatRub, localDate } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  LoadingState,
  Muted,
  Screen,
} from "@/shared/ui/components";
import { radius, space, typeScale, usePalette } from "@/shared/ui/theme";
import { Text } from "@/shared/ui/text";

import { buildCalendar, type CalendarDay, type CalendarItem } from "./logic";

const t = ru.calendar;
const PAST_DAYS = 7;
const FUTURE_DAYS = 30;

function statusLabel(item: CalendarItem): string {
  if (item.kind === "past")
    return item.status === "pending" ? t.pending : t.done;
  if (item.kind === "income")
    return item.status === "confirmed" ? t.incomeConfirmed : t.incomeExpected;
  return ru.status[item.status as keyof typeof ru.status] ?? item.status;
}

export function CalendarScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const desktop = width >= 960;
  const palette = usePalette();
  const { session } = useSession();
  const token = session?.access_token;
  const asOf = session?.data_quality.data_as_of ?? null;
  const today = asOf ? localDate(asOf) : new Date().toISOString().slice(0, 10);
  const [days, setDays] = useState<CalendarDay[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setError(null);
    try {
      const from = addDays(today, -PAST_DAYS);
      const to = addDays(today, FUTURE_DAYS);
      const [txs, obligations, incomes] = await Promise.all([
        api.listTransactions(token, from, today),
        api.listObligations(token, addDays(today, 1), to),
        api.listIncomes(token, addDays(today, 1), to),
      ]);
      setDays(
        buildCalendar(
          txs.items,
          obligations.calendar,
          incomes.calendar,
          (iso) => localDate(iso),
        ),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    }
  }, [token, today]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!session || !token) {
    return <Redirect href="/" />;
  }

  const decide = async (id: string, status: "confirmed" | "canceled") => {
    setBusyId(id);
    try {
      await api.updateObligation(token, id, { status });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    } finally {
      setBusyId(null);
    }
  };

  const year = Number(today.slice(0, 4));
  // Две группы вместо карточки на каждый день: так календарь читается одним списком.
  const past = days?.filter((day) => day.date <= today) ?? [];
  const future = days?.filter((day) => day.date > today) ?? [];

  return (
    <Screen wide>
      <Card title={t.title} icon="calendar">
        <Muted>{t.lead}</Muted>
        <View style={styles.legend}>
          <Badge label={t.legendPast} />
          <Badge label={t.legendConfirmed} tone="ok" />
          <Badge label={t.legendPredicted} tone="warning" />
        </View>
      </Card>
      {error ? (
        <ErrorState
          title={t.error}
          message={error}
          onRetry={() => void load()}
        />
      ) : null}
      {days === null && !error ? <LoadingState label={t.loading} /> : null}
      {days?.length === 0 ? <Muted>{t.empty}</Muted> : null}
      <View
        style={{
          flexDirection: desktop ? "row-reverse" : "column-reverse",
          gap: 24,
          alignItems: "flex-start",
        }}
      >
        <View
          style={{
            flex: desktop ? 1 : undefined,
            width: desktop ? undefined : "100%",
            minWidth: 0,
          }}
        >
          {past.length > 0 ? (
            <Card title={t.pastTitle} icon="clock">
              {past.map(renderDay)}
            </Card>
          ) : null}
        </View>
        <View
          style={{
            flex: desktop ? 1.2 : undefined,
            width: desktop ? undefined : "100%",
            minWidth: 0,
          }}
        >
          {future.length > 0 ? (
            <Card title={t.futureTitle} icon="calendar">
              {future.map(renderDay)}
            </Card>
          ) : null}
        </View>
      </View>
      <Button label={t.add} onPress={() => router.push("/add")} />
    </Screen>
  );

  /** День — подзаголовок с датой и строки событий; дни разделены тонкой линией. */
  function renderDay(day: CalendarDay, index: number) {
    const ahead = day.date > today;
    return (
      <View
        key={day.date}
        style={[
          styles.day,
          index > 0
            ? [styles.dayDivider, { borderColor: palette.border }]
            : null,
        ]}
      >
        <View
          style={[
            styles.dayHeader,
            {
              backgroundColor:
                day.date === today ? palette.accentSoft : palette.track,
            },
          ]}
        >
          <Text style={[styles.dayTitle, { color: palette.text }]}>
            {formatDay(day.date, year)}
            {day.date === today ? ` · ${t.today}` : ""}
          </Text>
          {ahead && day.expectedNetMinor !== 0 ? (
            <Text
              style={[
                styles.amount,
                {
                  color: day.expectedNetMinor < 0 ? palette.danger : palette.ok,
                },
              ]}
            >
              {formatRub(day.expectedNetMinor)}
            </Text>
          ) : null}
        </View>
        {day.items.map((item) => {
          const predicted = item.kind !== "past" && item.status !== "confirmed";
          return (
            <View
              key={item.key}
              style={[styles.item, { borderColor: palette.border }]}
            >
              <View
                style={[
                  styles.dot,
                  {
                    backgroundColor:
                      item.kind === "past"
                        ? palette.muted
                        : predicted
                          ? palette.warning
                          : palette.ok,
                  },
                ]}
              />
              <View style={styles.itemMain}>
                <Text style={[styles.itemTitle, { color: palette.text }]}>
                  {item.title}
                </Text>
                <Muted>
                  {statusLabel(item)}
                  {item.windowTo
                    ? ` · ${t.until} ${formatDay(item.windowTo, year)}`
                    : ""}
                </Muted>
                {item.confirmableId ? (
                  <View style={styles.actions}>
                    <Button
                      label={t.confirm}
                      size="sm"
                      onPress={() =>
                        void decide(item.confirmableId ?? "", "confirmed")
                      }
                      loading={busyId === item.confirmableId}
                    />
                    <Button
                      label={t.dismiss}
                      size="sm"
                      variant="secondary"
                      onPress={() =>
                        void decide(item.confirmableId ?? "", "canceled")
                      }
                      disabled={busyId === item.confirmableId}
                    />
                  </View>
                ) : null}
              </View>
              <Text style={[styles.amount, { color: palette.text }]}>
                {formatRub(item.amountMinor)}
                {item.amountMaxMinor
                  ? `…${formatRub(item.amountMaxMinor)}`
                  : ""}
              </Text>
            </View>
          );
        })}
      </View>
    );
  }
}

const styles = StyleSheet.create({
  legend: { flexDirection: "row", gap: space.sm, flexWrap: "wrap" },
  day: { gap: space.md },
  dayDivider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: space.md,
  },
  dayHeader: {
    padding: 12,
    borderRadius: radius.md,
    gap: 12,
    flexWrap: "wrap",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  dayTitle: { fontSize: 14, fontWeight: "600", letterSpacing: -0.28 },
  item: {
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    justifyContent: "space-between",
    gap: space.md,
  },
  dot: { width: 8, height: 8, borderRadius: 4, marginTop: 6 },
  itemMain: { flex: 1, gap: 2 },
  itemTitle: { fontSize: 14, fontWeight: "500" },
  amount: {
    maxWidth: "42%",
    flexShrink: 1,
    fontSize: 14,
    fontWeight: "500",
    textAlign: "right",
    fontVariant: ["tabular-nums"],
  },
  actions: {
    flexDirection: "row",
    gap: space.sm,
    marginTop: space.sm,
    flexWrap: "wrap",
  },
});
