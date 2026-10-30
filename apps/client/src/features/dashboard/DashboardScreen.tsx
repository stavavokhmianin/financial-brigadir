import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, View } from "react-native";

import {
  api,
  ApiError,
  type AccountsResponse,
  type Forecast,
  type LiveState,
  type ObligationsResponse,
} from "@/shared/api/client";
import { FeedbackCard } from "@/features/feedback/FeedbackCard";
import { LiveBar } from "@/features/feedback/LiveBar";
import {
  addDays,
  formatDay,
  formatMoment,
  formatRub,
  formatRubApprox,
  localDate,
} from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import {
  ActionTile,
  Badge,
  Button,
  Card,
  ErrorState,
  Hero,
  LoadingState,
  Muted,
  Notice,
  Screen,
  Stat,
} from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { radius, space, usePalette } from "@/shared/ui/theme";

import { describeAccount, upcoming } from "./logic";

const WINDOW_DAYS = 30;

interface DashboardData {
  accounts: AccountsResponse;
  obligations: ObligationsResponse;
  forecast: Forecast | null;
  duplicates: number;
  live: LiveState | null;
  from: string;
  to: string;
}

export function DashboardScreen() {
  const router = useRouter();
  const palette = usePalette();
  const { session } = useSession();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedbackKey, setFeedbackKey] = useState(0);
  const token = session?.access_token;
  const asOf = session?.data_quality.data_as_of ?? null;
  const isLive = Boolean(session && "live" in session && session.live);

  /** ``quiet`` — обновление поверх показанных данных, без экрана загрузки. */
  const load = useCallback(async (quiet = false) => {
    if (!token) return;
    setError(null);
    if (!quiet) setData(null);
    try {
      // У учебного аккаунта «сегодня» идёт вперёд: окно считаем от виртуального времени.
      const live = isLive ? await api.getLiveState(token) : null;
      const moment = live?.virtual_now ?? asOf;
      const from = moment ? localDate(moment) : new Date().toISOString().slice(0, 10);
      const to = addDays(from, WINDOW_DAYS);
      const [accounts, obligations, forecast, duplicates] = await Promise.all([
        api.listAccounts(token),
        api.listObligations(token, from, to),
        // Прогноз не должен ломать главный экран: без него показываем остальные данные.
        api.createForecast(token, {}).catch(() => null),
        api
          .listDuplicates(token)
          .then((d) => d.items.length)
          .catch(() => 0),
      ]);
      setData({ accounts, obligations, forecast, duplicates, live, from, to });
    } catch (err) {
      if (!quiet) setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    }
  }, [token, asOf, isLive]);

  const onArrived = useCallback(() => {
    setFeedbackKey((key) => key + 1);
    void load(true);
  }, [load]);
  const onLabeled = useCallback(() => void load(true), [load]);

  // Перезагрузка при возврате на экран: данные могли измениться в календаре или импорте.
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  if (!session) {
    return <Redirect href="/" />;
  }

  if (error) {
    return (
      <Screen>
        <ErrorState title={ru.dashboard.loadError} message={error} onRetry={() => void load()} />
        <Button label={ru.dashboard.privacy} onPress={() => router.push("/privacy")} variant="secondary" />
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
  const forecastTone = data.forecast
    ? data.forecast.risk_level === "high"
      ? { color: palette.danger, soft: palette.dangerSoft, icon: "alert" as const }
      : data.forecast.risk_level === "medium"
        ? { color: palette.warning, soft: palette.warningBg, icon: "alert" as const }
        : { color: palette.ok, soft: palette.okSoft, icon: "check" as const }
    : null;

  return (
    <Screen>
      <Hero>
        <View style={styles.row}>
          {/* Учебный аккаунт не показывает основу синтетики как персонажа (ADR-0007). */}
          {isLive ? (
            <Badge label={ru.live.badge} tone="hero" />
          ) : (
            <>
              <Badge label={"profile" in session ? session.profile.title : ru.pilot.badge} tone="hero" />
              {quality.is_demo ? <Badge label={ru.dashboard.demoBadge} tone="hero" /> : null}
            </>
          )}
          <Badge label={ru.dashboard.coverage[quality.coverage]} tone="hero" />
        </View>
        <View style={styles.balance}>
          <Text style={[styles.heroLabel, { color: palette.heroMuted }]}>{ru.dashboard.liquid}</Text>
          <Text accessibilityRole="summary" style={[styles.amount, { color: palette.heroText }]}>
            {formatRub(data.accounts.liquid_balance_minor)}
          </Text>
          {quality.data_as_of ? (
            <View style={styles.freshness}>
              <Icon name="clock" color={palette.heroMuted} size={15} />
              <Text style={[styles.heroLabel, { color: palette.heroMuted }]}>
                {ru.dashboard.dataAsOf} {formatMoment(quality.data_as_of)}
              </Text>
            </View>
          ) : null}
        </View>
      </Hero>

      {data.live && token ? (
        <LiveBar key={token} token={token} latest={data.live} onArrived={onArrived} />
      ) : null}

      {quality.notes.length > 0 ? (
        <Notice text={`${ru.dashboard.notesTitle}: ${quality.notes.join(" ")}`} />
      ) : null}

      {data.duplicates > 0 ? (
        <Card title={ru.duplicates.dashboardTitle} icon="alert">
          <Muted>
            {ru.duplicates.title}: {data.duplicates}
          </Muted>
          <Button label={ru.duplicates.open} onPress={() => router.push("/duplicates")} />
        </Card>
      ) : null}

      <Card title={ru.dashboard.decisionTitle} icon="sparkle">
        {data.accounts.items.length === 0 ? (
          // Пустой профиль участника пилота: прогноз из нуля рублей только напугает.
          <>
            <Muted>{ru.dashboard.noAccounts}</Muted>
            <Button label={ru.dashboard.addFirst} onPress={() => router.push("/add")} />
          </>
        ) : data.forecast ? (
          <>
            <View
              accessibilityRole="summary"
              style={[styles.decision, { backgroundColor: forecastTone?.soft }]}
            >
              <View style={[styles.decisionIcon, { backgroundColor: forecastTone?.color }]}>
                <Icon name={forecastTone?.icon ?? "chart"} color="#ffffff" size={20} />
              </View>
              <View style={styles.lineMain}>
                <Text style={[styles.decisionTitle, { color: forecastTone?.color }]}>
                  {ru.forecast.level[data.forecast.risk_level]}
                </Text>
                <Text style={[styles.decisionText, { color: palette.text }]}>
                  {data.forecast.risk_level === "high" && data.forecast.risk.date
                    ? `${ru.dashboard.riskOn} ${formatDay(data.forecast.risk.date, year)}. ${ru.dashboard.riskGap} ${formatRubApprox(data.forecast.risk.shortfall_minor)}.`
                    : data.forecast.risk_level === "medium"
                      ? ru.dashboard.reserveTight
                      : ru.dashboard.reserveKeeps}
                </Text>
              </View>
            </View>
            <View style={styles.stats}>
              <Stat
                label={`${ru.forecast.minimum} · ${formatDay(data.forecast.risk.min_balance_date, year)}`}
                value={formatRubApprox(data.forecast.risk.min_balance_minor)}
                tone={
                  data.forecast.risk.min_balance_minor < data.forecast.reserve_minor
                    ? "danger"
                    : "default"
                }
              />
              {data.forecast.safe_to_spend.available ? (
                <Stat
                  label={ru.dashboard.safeShort}
                  value={formatRubApprox(data.forecast.safe_to_spend.base_minor)}
                  tone="ok"
                />
              ) : null}
            </View>
            {data.forecast.safe_to_spend.available ? (
              <Muted>
                {ru.forecast.safeToday} {formatDay(data.forecast.safe_to_spend.date, year)}: до{" "}
                {formatRubApprox(data.forecast.safe_to_spend.base_minor)}
              </Muted>
            ) : null}
            <Button label={ru.forecast.whatIf} icon="cart" onPress={() => router.push("/simulate")} />
            <Button
              label={ru.forecast.open}
              icon="chart"
              variant="secondary"
              onPress={() => router.push("/forecast")}
            />
          </>
        ) : (
          <Muted>{ru.forecast.error}</Muted>
        )}
      </Card>

      {isLive && token ? (
        <FeedbackCard token={token} refreshKey={feedbackKey} onLabeled={onLabeled} />
      ) : null}

      <Card title={ru.dashboard.upcomingTitle} icon="calendar">
        {next.items.length === 0 ? (
          <Muted>{ru.dashboard.upcomingEmpty}</Muted>
        ) : (
          <>
            {next.items.map((item) => (
              <View key={`${item.obligation_id}-${item.date}`} style={styles.line}>
                <View
                  style={[
                    styles.dot,
                    {
                      backgroundColor:
                        item.status === "confirmed" ? palette.accent : palette.warning,
                    },
                  ]}
                />
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

      <Card title={ru.dashboard.accountsTitle} icon="wallet">
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

      <Text style={[styles.section, { color: palette.muted }]}>{ru.dashboard.actionsTitle}</Text>
      <View style={styles.grid}>
        <ActionTile icon="calendar" label={ru.dashboard.calendar} onPress={() => router.push("/calendar")} />
        <ActionTile icon="bell" label={ru.dashboard.alerts} onPress={() => router.push("/alerts")} />
        <ActionTile icon="plus" label={ru.dashboard.add} onPress={() => router.push("/add")} />
        <ActionTile icon="upload" label={ru.dashboard.importCsv} onPress={() => router.push("/import")} />
        <ActionTile icon="crown" label={ru.dashboard.plans} onPress={() => router.push("/plans")} />
        {session.user.is_demo ? (
          <ActionTile icon="bank" label={ru.dashboard.bankMock} onPress={() => router.push("/bank")} />
        ) : null}
      </View>
      {/* Последний элемент экрана: на него опирается Android-сценарий. */}
      <Button
        label={ru.dashboard.privacy}
        icon="shield"
        onPress={() => router.push("/privacy")}
        variant="secondary"
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: space.sm, flexWrap: "wrap" },
  balance: { gap: space.xs, paddingTop: space.sm },
  heroLabel: { fontSize: 14, fontWeight: "600" },
  amount: { fontSize: 44, fontWeight: "800", letterSpacing: -1.2, lineHeight: 52 },
  freshness: { flexDirection: "row", alignItems: "center", gap: 6 },
  decision: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: space.md,
    borderRadius: radius.md,
    padding: space.md,
  },
  decisionIcon: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  decisionTitle: { fontSize: 17, fontWeight: "800", lineHeight: 22 },
  decisionText: { fontSize: 14, lineHeight: 20 },
  stats: { flexDirection: "row", gap: space.sm },
  line: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.md },
  dot: { width: 8, height: 8, borderRadius: 4 },
  lineMain: { flex: 1, gap: 2 },
  lineTitle: { fontSize: 15, fontWeight: "700" },
  lineAmount: { fontSize: 15, fontWeight: "800", textAlign: "right" },
  total: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space.md },
  section: {
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: -space.sm,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space.md, borderRadius: radius.lg },
});
