import { Redirect, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import {
  api,
  ApiError,
  type AccountsResponse,
  type ObligationsResponse,
} from "@/shared/api/client";
import { addDays, formatDay, formatMoment, formatRub, localDate } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import { Badge, Button, Card, ErrorState, LoadingState, Muted, Screen } from "@/shared/ui/components";
import { space, usePalette } from "@/shared/ui/theme";

import { describeAccount, upcoming } from "./logic";

const WINDOW_DAYS = 30;

interface DashboardData {
  accounts: AccountsResponse;
  obligations: ObligationsResponse;
  from: string;
  to: string;
}

export function DashboardScreen() {
  const router = useRouter();
  const palette = usePalette();
  const { session, setSession } = useSession();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const token = session?.access_token;
  const asOf = session?.data_quality.data_as_of ?? null;

  const load = useCallback(async () => {
    if (!token) return;
    setError(null);
    setData(null);
    try {
      const from = asOf ? localDate(asOf) : new Date().toISOString().slice(0, 10);
      const to = addDays(from, WINDOW_DAYS);
      const [accounts, obligations] = await Promise.all([
        api.listAccounts(token),
        api.listObligations(token, from, to),
      ]);
      setData({ accounts, obligations, from, to });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    }
  }, [token, asOf]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!session) {
    return <Redirect href="/" />;
  }

  const switchProfile = () => {
    setSession(null);
    router.replace("/");
  };

  if (error) {
    return (
      <Screen>
        <ErrorState title={ru.dashboard.loadError} message={error} onRetry={() => void load()} />
        <Button label={ru.dashboard.switchProfile} onPress={switchProfile} variant="secondary" />
      </Screen>
    );
  }
  if (!data) {
    return (
      <Screen>
        <LoadingState label={ru.dashboard.loading} />
      </Screen>
    );
  }

  const quality = data.accounts.data_quality;
  const next = upcoming(data.obligations.calendar, data.from, data.to);
  const year = Number(data.from.slice(0, 4));

  return (
    <Screen>
      <Card>
        <View style={styles.row}>
          <Badge label={session.profile.title} />
          {quality.is_demo ? <Badge label={ru.dashboard.demoBadge} tone="warning" /> : null}
          <Badge
            label={ru.dashboard.coverage[quality.coverage]}
            tone={quality.coverage === "full" ? "ok" : "warning"}
          />
        </View>
        <Muted>{ru.dashboard.liquid}</Muted>
        <Text
          accessibilityRole="summary"
          style={[styles.amount, { color: palette.text }]}
        >
          {formatRub(data.accounts.liquid_balance_minor)}
        </Text>
        {quality.data_as_of ? (
          <Muted>
            {ru.dashboard.dataAsOf} {formatMoment(quality.data_as_of)}
          </Muted>
        ) : null}
      </Card>

      {quality.notes.length > 0 ? (
        <View style={[styles.notes, { backgroundColor: palette.warningBg }]}>
          <Text style={[styles.notesTitle, { color: palette.warning }]}>
            {ru.dashboard.notesTitle}
          </Text>
          {quality.notes.map((note) => (
            <Text key={note} style={[styles.note, { color: palette.text }]}>
              • {note}
            </Text>
          ))}
        </View>
      ) : null}

      <Card title={ru.dashboard.upcomingTitle}>
        {next.items.length === 0 ? (
          <Muted>{ru.dashboard.upcomingEmpty}</Muted>
        ) : (
          <>
            {next.items.map((item) => (
              <View key={`${item.obligation_id}-${item.date}`} style={styles.line}>
                <View style={styles.lineMain}>
                  <Text style={[styles.lineTitle, { color: palette.text }]}>{item.title}</Text>
                  <Muted>
                    {formatDay(item.date, year)} ·{" "}
                    {ru.status[item.status as keyof typeof ru.status] ?? item.status}
                  </Muted>
                </View>
                <Text style={[styles.lineAmount, { color: palette.text }]}>
                  {formatRub(-item.amount_minor)}
                </Text>
              </View>
            ))}
            <View style={[styles.line, styles.total, { borderColor: palette.border }]}>
              <Text style={[styles.lineTitle, { color: palette.text }]}>
                {ru.dashboard.upcomingTotal} ({formatDay(data.to, year)})
              </Text>
              <Text style={[styles.lineAmount, { color: palette.text }]}>
                {formatRub(-next.totalMinor)}
              </Text>
            </View>
          </>
        )}
      </Card>

      <Card title={ru.dashboard.forecastTitle}>
        <Muted>{ru.dashboard.forecastSoon}</Muted>
      </Card>

      <Card title={ru.dashboard.accountsTitle}>
        {data.accounts.items.map((account) => {
          const line = describeAccount(account);
          return (
            <View key={account.id} style={styles.line}>
              <View style={styles.lineMain}>
                <Text style={[styles.lineTitle, { color: palette.text }]}>{account.name}</Text>
                <Muted>
                  {ru.accountType[account.type]}
                  {account.bank_name ? ` · ${account.bank_name}` : ""}
                  {line.kind === "excluded" ? ` · ${ru.dashboard.notLiquid}` : ""}
                  {line.kind === "liquid" && line.blockedMinor > 0
                    ? ` · ${ru.dashboard.blocked} ${formatRub(line.blockedMinor)}`
                    : ""}
                </Muted>
              </View>
              <Text style={[styles.lineAmount, { color: palette.text }]}>
                {line.kind === "credit"
                  ? `${ru.dashboard.debt} ${formatRub(line.debtMinor)}${
                      line.limitMinor !== null
                        ? ` / ${ru.dashboard.limit} ${formatRub(line.limitMinor)}`
                        : ""
                    }`
                  : formatRub(line.balanceMinor)}
              </Text>
            </View>
          );
        })}
      </Card>

      <Button label={ru.dashboard.switchProfile} onPress={switchProfile} variant="secondary" />
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: space.sm, flexWrap: "wrap" },
  amount: { fontSize: 34, fontWeight: "700" },
  notes: { borderRadius: 12, padding: space.lg, gap: space.xs },
  notesTitle: { fontSize: 15, fontWeight: "600" },
  note: { fontSize: 14, lineHeight: 20 },
  line: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.md },
  lineMain: { flex: 1, gap: 2 },
  lineTitle: { fontSize: 15, fontWeight: "500" },
  lineAmount: { fontSize: 15, fontWeight: "600", textAlign: "right" },
  total: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space.md },
});
