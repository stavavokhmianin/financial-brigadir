import { Redirect, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api, ApiError } from "@/shared/api/client";
import { addDays, formatDay, formatRub, localDate } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import { Badge, Button, Card, ErrorState, LoadingState, Muted, Screen } from "@/shared/ui/components";
import { space, usePalette } from "@/shared/ui/theme";

import { buildCalendar, type CalendarDay, type CalendarItem } from "./logic";

const t = ru.calendar;
const PAST_DAYS = 7;
const FUTURE_DAYS = 30;

function statusLabel(item: CalendarItem): string {
  if (item.kind === "past") return item.status === "pending" ? t.pending : t.done;
  if (item.kind === "income") return item.status === "confirmed" ? t.incomeConfirmed : t.incomeExpected;
  return ru.status[item.status as keyof typeof ru.status] ?? item.status;
}

export function CalendarScreen() {
  const router = useRouter();
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
      setDays(buildCalendar(txs.items, obligations.calendar, incomes.calendar, (iso) => localDate(iso)));
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

  return (
    <Screen>
      <Card title={t.title}>
        <Muted>{t.lead}</Muted>
        <View style={styles.legend}>
          <Badge label={t.legendPast} />
          <Badge label={t.legendConfirmed} tone="ok" />
          <Badge label={t.legendPredicted} tone="warning" />
        </View>
      </Card>
      {error ? <ErrorState title={t.error} message={error} onRetry={() => void load()} /> : null}
      {days === null && !error ? <LoadingState label={t.loading} /> : null}
      {days?.length === 0 ? <Muted>{t.empty}</Muted> : null}
      {days?.map((day) => {
        const future = day.date > today;
        return (
          <Card key={day.date}>
            <View style={styles.dayHeader}>
              <Text style={[styles.dayTitle, { color: palette.text }]}>
                {formatDay(day.date, year)}
                {day.date === today ? ` · ${t.today}` : ""}
              </Text>
              {future && day.expectedNetMinor !== 0 ? (
                <Text style={[styles.amount, { color: day.expectedNetMinor < 0 ? palette.danger : palette.ok }]}>
                  {formatRub(day.expectedNetMinor)}
                </Text>
              ) : null}
            </View>
            {day.items.map((item) => {
              const predicted = item.kind !== "past" && item.status !== "confirmed";
              return (
                <View
                  key={item.key}
                  style={[
                    styles.item,
                    item.kind === "past"
                      ? { opacity: 0.7 }
                      : {
                          borderLeftWidth: 3,
                          borderLeftColor: predicted ? palette.warning : palette.ok,
                          paddingLeft: space.sm,
                        },
                  ]}
                >
                  <View style={styles.itemMain}>
                    <Text style={{ color: palette.text }}>{item.title}</Text>
                    <Muted>
                      {statusLabel(item)}
                      {item.windowTo ? ` · ${t.until} ${formatDay(item.windowTo, year)}` : ""}
                    </Muted>
                    {item.confirmableId ? (
                      <View style={styles.actions}>
                        <Button
                          label={t.confirm}
                          onPress={() => void decide(item.confirmableId ?? "", "confirmed")}
                          loading={busyId === item.confirmableId}
                        />
                        <Button
                          label={t.dismiss}
                          variant="secondary"
                          onPress={() => void decide(item.confirmableId ?? "", "canceled")}
                          disabled={busyId === item.confirmableId}
                        />
                      </View>
                    ) : null}
                  </View>
                  <Text style={[styles.amount, { color: palette.text }]}>
                    {formatRub(item.amountMinor)}
                    {item.amountMaxMinor ? `…${formatRub(item.amountMaxMinor)}` : ""}
                  </Text>
                </View>
              );
            })}
          </Card>
        );
      })}
      <Button label={t.add} onPress={() => router.push("/add")} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  legend: { flexDirection: "row", gap: space.sm, flexWrap: "wrap" },
  dayHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  dayTitle: { fontSize: 16, fontWeight: "600" },
  item: { flexDirection: "row", justifyContent: "space-between", gap: space.md },
  itemMain: { flex: 1, gap: 2 },
  amount: { fontWeight: "600", textAlign: "right" },
  actions: { flexDirection: "row", gap: space.sm, marginTop: space.xs, flexWrap: "wrap" },
});
