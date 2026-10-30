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
  type Transaction,
} from "@/shared/api/client";
import { FeedbackCard } from "@/features/feedback/FeedbackCard";
import { LiveBar } from "@/features/feedback/LiveBar";
import { RecurringCard } from "@/features/feedback/RecurringCard";
import { NotificationsBell } from "@/features/alerts/NotificationsBell";
import { ForecastChart } from "@/features/forecast/ForecastChart";
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
import { fonts, radius, space, usePalette } from "@/shared/ui/theme";

import { describeAccount, upcoming } from "./logic";

const WINDOW_DAYS = 30;

interface DashboardData {
  accounts: AccountsResponse;
  obligations: ObligationsResponse;
  forecast: Forecast | null;
  duplicates: number;
  live: LiveState | null;
  transactions: Transaction[];
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
      const [accounts, obligations, forecast, duplicates, transactions] = await Promise.all([
        api.listAccounts(token),
        api.listObligations(token, from, to),
        // Прогноз не должен ломать главный экран: без него показываем остальные данные.
        api.createForecast(token, {}).catch(() => null),
        api
          .listDuplicates(token)
          .then((d) => d.items.length)
          .catch(() => 0),
        api
          .listTransactions(token, addDays(from, -30), from, 5)
          .then((page) => page.items)
          .catch(() => [] as Transaction[]),
      ]);
      setData({ accounts, obligations, forecast, duplicates, live, transactions, from, to });
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
        <View style={styles.heroTop}>
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
          {token ? <NotificationsBell token={token} /> : null}
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
                <Icon name={forecastTone?.icon ?? "chart"} color={palette.card} size={18} />
              </View>
              <View style={styles.lineMain}>
                <Text style={[styles.decisionTitle, { color: forecastTone?.color }]}>
                  {ru.forecast.level[data.forecast.risk_level]}
                </Text>
                <Text style={[styles.decisionText, { color: palette.text }]}>
                  {data.forecast.risk_level === "high" && data.forecast.risk.date
                    ? `${ru.dashboard.riskOn} ${formatDay(data.forecast.risk.date, year)}. ${ru.dashboard.riskGap} ${formatRubApprox(data.forecast.risk.shortfall_minor)}.`
                    : data.forecast.risk_level === "high"
                      ? // Высокий риск по симуляции без одного дня: ниже резерва в большинстве
                        // вариантов, но в разные дни. «Резерв сохраняется» здесь было бы неправдой.
                        ru.dashboard.reserveOften
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
            </View>
            <View style={styles.inlineChart}>
              <Text style={[styles.inlineChartTitle, { color: palette.text }]}>
                {ru.forecast.chartTitle}
              </Text>
              <ForecastChart
                compact
                points={data.forecast.points}
                reserveMinor={data.forecast.reserve_minor}
              />
              <Muted>{ru.dashboard.chartHint}</Muted>
            </View>
            <Button label={ru.forecast.whatIf} icon="cart" onPress={() => router.push("/simulate")} />
          </>
        ) : (
          <Muted>{ru.forecast.error}</Muted>
        )}
      </Card>

      {isLive && token ? (
        <>
          <RecurringCard token={token} refreshKey={feedbackKey} onConfirmed={onArrived} />
          <FeedbackCard token={token} refreshKey={feedbackKey} onLabeled={onLabeled} />
        </>
      ) : null}

      <Card title={ru.dashboard.recentTitle} icon="wallet">
        <Muted>{ru.dashboard.recentHint}</Muted>
        {data.transactions.length === 0 ? (
          <Muted>{ru.dashboard.recentEmpty}</Muted>
        ) : (
          data.transactions.map((transaction) => (
            <View key={transaction.id} style={styles.activity}>
              <View style={styles.lineMain}>
                <Text style={[styles.lineTitle, { color: palette.text }]}>
                  {transaction.description ?? transaction.category ?? ru.feedback.fallbackTitle}
                </Text>
                <Muted>{formatMoment(transaction.occurred_at)}</Muted>
                {transaction.user_note ? (
                  <Text style={[styles.activityNote, { color: palette.muted }]}>
                    {`${ru.dashboard.personalNote}: ${transaction.user_note}`}
                  </Text>
                ) : null}
                {transaction.label ? (
                  <View style={styles.activityBadge}>
                    <Badge label={ru.feedback.labels[transaction.label]} tone="muted" />
                  </View>
                ) : null}
              </View>
              <Text
                style={[
                  styles.lineAmount,
                  { color: transaction.amount_minor > 0 ? palette.ok : palette.text },
                ]}
              >
                {formatRub(transaction.amount_minor)}
              </Text>
            </View>
          ))
        )}
      </Card>

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
  heroTop: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: space.md },
  balance: { gap: space.xs, paddingTop: space.sm },
  heroLabel: { fontSize: 13, fontWeight: "500" },
  amount: {
    fontSize: 44,
    fontWeight: "600",
    letterSpacing: -2,
    lineHeight: 52,
    fontVariant: ["tabular-nums"],
  },
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
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  decisionTitle: { fontSize: 16, fontWeight: "600", lineHeight: 22, letterSpacing: -0.32 },
  decisionText: { fontSize: 14, lineHeight: 20 },
  stats: { flexDirection: "row", gap: space.sm },
  inlineChart: { gap: space.sm, paddingTop: space.xs },
  inlineChartTitle: { fontSize: 14, fontWeight: "600" },
  line: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.md },
  dot: { width: 8, height: 8, borderRadius: 4 },
  lineMain: { flex: 1, gap: 2 },
  lineTitle: { fontSize: 14, fontWeight: "500" },
  lineAmount: { fontSize: 14, fontWeight: "500", textAlign: "right", fontVariant: ["tabular-nums"] },
  activity: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: space.md,
    paddingVertical: space.xs,
  },
  activityNote: { fontSize: 13, lineHeight: 18 },
  activityBadge: { alignSelf: "flex-start", paddingTop: 2 },
  total: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: space.md },
  section: {
    fontFamily: fonts.mono,
    fontSize: 12,
    letterSpacing: 0.4,
    textTransform: "uppercase",
    marginBottom: -space.sm,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: space.md, borderRadius: radius.lg },
});
