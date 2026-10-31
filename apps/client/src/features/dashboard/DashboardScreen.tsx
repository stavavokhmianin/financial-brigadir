import { Redirect, useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, View, useWindowDimensions } from "react-native";

import {
  api,
  ApiError,
  type AccountsResponse,
  type Forecast,
  type LiveState,
  type ObligationsResponse,
  type Transaction,
} from "@/shared/api/client";
import { LiveBar } from "@/features/feedback/LiveBar";
import { SpendingReview } from "@/features/feedback/SpendingReview";
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
  Badge,
  Button,
  Card,
  ErrorState,
  Hero,
  LoadingState,
  Muted,
  Screen,
} from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { Money } from "@/shared/ui/money";
import { Reveal } from "@/shared/ui/motion";
import { ChartLegend } from "@/features/forecast/ForecastScreen";
import { radius, space, typeScale, usePalette } from "@/shared/ui/theme";

import { describeAccount, upcoming } from "./logic";
import { DashboardMenu } from "./DashboardMenu";

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
  const { width } = useWindowDimensions();
  const desktop = width >= 960;
  const palette = usePalette();
  const { session } = useSession();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedbackKey, setFeedbackKey] = useState(0);
  const [hasRecurring, setHasRecurring] = useState<boolean | null>(null);
  const token = session?.access_token;
  const asOf = session?.data_quality.data_as_of ?? null;
  const isLive = Boolean(session && "live" in session && session.live);

  /** ``quiet`` — обновление поверх показанных данных, без экрана загрузки. */
  const load = useCallback(
    async (quiet = false) => {
      if (!token) return;
      setError(null);
      if (!quiet) setData(null);
      try {
        // У учебного аккаунта «сегодня» идёт вперёд: окно считаем от виртуального времени.
        const live = isLive ? await api.getLiveState(token) : null;
        const moment = live?.virtual_now ?? asOf;
        const from = moment
          ? localDate(moment)
          : new Date().toISOString().slice(0, 10);
        const to = addDays(from, WINDOW_DAYS);
        const [accounts, obligations, forecast, duplicates, transactions] =
          await Promise.all([
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
        setData({
          accounts,
          obligations,
          forecast,
          duplicates,
          live,
          transactions,
          from,
          to,
        });
      } catch (err) {
        if (!quiet)
          setError(
            err instanceof ApiError ? err.message : "Неизвестная ошибка.",
          );
      }
    },
    [token, asOf, isLive],
  );

  const onArrived = useCallback(() => {
    setFeedbackKey((key) => key + 1);
    void load(true);
  }, [load]);
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
        <ErrorState
          title={ru.dashboard.loadError}
          message={error}
          onRetry={() => void load()}
        />
        <Button
          label={ru.dashboard.privacy}
          onPress={() => router.push("/privacy")}
          variant="secondary"
        />
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
      ? {
          color: palette.danger,
          soft: palette.dangerSoft,
          icon: "alert" as const,
        }
      : data.forecast.risk_level === "medium"
        ? {
            color: palette.warning,
            soft: palette.warningBg,
            icon: "alert" as const,
          }
        : { color: palette.ok, soft: palette.okSoft, icon: "check" as const }
    : null;

  return (
    <Screen wide>
      <View style={[styles.overviewGrid, desktop && styles.horizontal]}>
        <Hero
          style={{
            flex: desktop ? 1.55 : undefined,
            padding: desktop ? 32 : 20,
            gap: desktop ? 20 : 12,
          }}
        >
          <View style={styles.heroTop}>
            <View style={styles.heroBadges}>
              {/* Учебный аккаунт не показывает основу синтетики как персонажа (ADR-0007). */}
              {isLive ? (
                <Badge
                  label={session.user.display_name ?? ru.live.badge}
                  tone="hero"
                />
              ) : (
                <>
                  <Badge
                    label={
                      "profile" in session
                        ? session.profile.title
                        : ru.pilot.badge
                    }
                    tone="hero"
                  />
                  {quality.is_demo ? (
                    <Badge label={ru.dashboard.demoBadge} tone="hero" />
                  ) : null}
                </>
              )}
              {desktop ? (
                <Badge
                  label={ru.dashboard.coverage[quality.coverage]}
                  tone="hero"
                />
              ) : null}
            </View>
            <View style={styles.heroActions}>
              {token ? <NotificationsBell token={token} /> : null}
              <DashboardMenu
                isDemo={session.user.is_demo}
                qualityNotes={quality.notes}
                duplicates={data.duplicates}
                liveControl={
                  data.live && token ? (
                    <LiveBar
                      key={token}
                      token={token}
                      latest={data.live}
                      onArrived={onArrived}
                    />
                  ) : undefined
                }
              />
            </View>
          </View>

          <View style={[styles.balance, !desktop && { gap: 8, paddingTop: 4 }]}>
            <Text style={[typeScale.eyebrow, { color: palette.heroMuted }]}>
              {ru.dashboard.liquid}
            </Text>
            <Money
              minor={data.accounts.liquid_balance_minor}
              style={[
                desktop ? typeScale.hero : typeScale.display,
                { color: palette.heroText },
              ]}
            />
            {desktop ? (
              <Text style={[styles.heroLabel, { color: palette.heroMuted }]}>
                Деньги, которыми вы располагаете сейчас
              </Text>
            ) : null}
          </View>
          <View
            style={[
              styles.balanceBottom,
              { borderColor: palette.heroBorder },
              desktop && {
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
              },
              !desktop && { gap: 12, marginTop: 0 },
            ]}
          >
            {quality.data_as_of ? (
              <View style={styles.freshness}>
                <Icon name="clock" color={palette.heroMuted} size={14} />
                <Text style={[styles.heroLabel, { color: palette.heroMuted }]}>
                  {formatMoment(quality.data_as_of)}
                </Text>
              </View>
            ) : null}
            <Button
              label="Добавить операцию"
              icon="plus"
              variant="inverse"
              onPress={() => router.push("/add")}
            />
          </View>
        </Hero>
        <Card
          style={{
            flex: desktop ? 1 : undefined,
            backgroundColor: palette.accentSoft,
            gap: desktop ? 16 : 10,
            padding: desktop ? 24 : 20,
          }}
        >
          <View style={styles.sectionHeading}>
            <Icon name="shield" color={palette.accent} size={20} />
            <Text style={[typeScale.eyebrow, { color: palette.accent }]}>
              МОЖНО ПОТРАТИТЬ
            </Text>
          </View>
          {data.forecast?.safe_to_spend.available &&
          data.accounts.items.length > 0 ? (
            <>
              <Money
                minor={data.forecast.safe_to_spend.base_minor}
                approximate
                style={[
                  desktop ? typeScale.display : typeScale.title,
                  { color: palette.text },
                ]}
              />
              <Text style={[typeScale.caption, { color: palette.muted }]}>
                На {formatDay(data.forecast.safe_to_spend.date, year)} ·
                основной сценарий
              </Text>
              <View
                style={[
                  styles.safeDetail,
                  { borderColor: palette.border },
                  !desktop && {
                    paddingVertical: 0,
                    flexDirection: "row",
                    alignItems: "center",
                    flexWrap: "wrap",
                  },
                ]}
              >
                <Text style={[styles.heroLabel, { color: palette.muted }]}>
                  Осторожная оценка
                </Text>
                <Money
                  minor={data.forecast.safe_to_spend.conservative_minor}
                  approximate
                  style={[typeScale.heading, { color: palette.text }]}
                />
              </View>
              {desktop ? (
                <Text style={[typeScale.caption, { color: palette.muted }]}>
                  Модельная оценка с учётом резерва, а не гарантия остатка.
                </Text>
              ) : null}
            </>
          ) : (
            <Muted>
              {data.accounts.items.length === 0
                ? ru.dashboard.noAccounts
                : "Пока недостаточно данных для оценки доступной суммы."}
            </Muted>
          )}
          {!desktop ? (
            <View
              style={{
                gap: 8,
                borderTopWidth: 1,
                borderColor: palette.inputBorder,
                paddingTop: 10,
              }}
            >
              {data.forecast && data.accounts.items.length > 0 ? (
                <View
                  style={[
                    styles.decision,
                    { backgroundColor: forecastTone?.soft, padding: 10 },
                  ]}
                >
                  <Icon
                    name={forecastTone?.icon ?? "shield"}
                    color={forecastTone?.color ?? palette.accent}
                    size={16}
                  />
                  <Text
                    style={{
                      color: forecastTone?.color,
                      fontSize: 13,
                      fontWeight: "600",
                      flexShrink: 1,
                    }}
                  >
                    {ru.forecast.level[data.forecast.risk_level]}
                  </Text>
                </View>
              ) : null}
              {next.items[0] ? (
                <Text style={[typeScale.caption, { color: palette.text }]}>
                  Ближайший платёж · {formatDay(next.items[0].date, year)}
                  {"\n"}
                  {next.items[0].title} ·{" "}
                  {formatRub(-next.items[0].amount_minor)}
                </Text>
              ) : (
                <Text style={[typeScale.caption, { color: palette.muted }]}>
                  {ru.dashboard.upcomingEmpty}
                </Text>
              )}
            </View>
          ) : null}
          <Button
            label={ru.forecast.whatIf}
            trailingIcon="arrow"
            variant="secondary"
            onPress={() =>
              router.push(data.accounts.items.length ? "/simulate" : "/add")
            }
          />
        </Card>
      </View>

      {isLive && token ? (
        <SpendingReview
          token={token}
          refreshKey={feedbackKey}
          hasRecurring={hasRecurring}
          onRecurringChange={setHasRecurring}
          onChanged={onArrived}
        />
      ) : null}

      <Reveal delay={55}>
        <View style={[styles.overviewGrid, desktop && styles.horizontal]}>
          <Card
            title="Прогноз денежных потоков"
            icon="chart"
            style={{ flex: desktop ? 1.55 : undefined }}
          >
            {data.forecast && data.accounts.items.length > 0 ? (
              <>
                <View style={styles.sectionHeading}>
                  <Badge
                    label={String(data.forecast.horizon_days) + " дней вперёд"}
                  />
                  <Text style={[typeScale.caption, { color: palette.muted }]}>
                    Диапазон сценариев p10–p90
                  </Text>
                </View>
                <ForecastChart
                  points={data.forecast.points}
                  reserveMinor={data.forecast.reserve_minor}
                />
                <ChartLegend />
              </>
            ) : (
              <Muted>
                {data.accounts.items.length === 0
                  ? ru.dashboard.noAccounts
                  : ru.forecast.error}
              </Muted>
            )}
          </Card>
          <Card
            title="Запас прочности"
            icon="shield"
            style={{ flex: desktop ? 1 : undefined }}
          >
            {data.forecast && data.accounts.items.length > 0 ? (
              <>
                <View
                  style={[
                    styles.decision,
                    { backgroundColor: forecastTone?.soft },
                  ]}
                >
                  <Icon
                    name={forecastTone?.icon ?? "chart"}
                    color={forecastTone?.color ?? palette.accent}
                    size={20}
                  />
                  <View style={styles.lineMain}>
                    <Text
                      style={[
                        styles.decisionTitle,
                        { color: forecastTone?.color },
                      ]}
                    >
                      {ru.forecast.level[data.forecast.risk_level]}
                    </Text>
                    <Text
                      style={[styles.decisionText, { color: palette.text }]}
                    >
                      {data.forecast.risk_level === "high" &&
                      data.forecast.risk.date
                        ? `${ru.dashboard.riskOn} ${formatDay(data.forecast.risk.date, year)}. ${ru.dashboard.riskGap} ${formatRubApprox(data.forecast.risk.shortfall_minor)}.`
                        : data.forecast.risk_level === "high"
                          ? ru.dashboard.reserveOften
                          : data.forecast.risk_level === "medium"
                            ? ru.dashboard.reserveTight
                            : ru.dashboard.reserveKeeps}
                    </Text>
                  </View>
                </View>
                <View style={styles.safeDetail}>
                  <Muted>
                    {ru.forecast.minimum} ·{" "}
                    {formatDay(data.forecast.risk.min_balance_date, year)}
                  </Muted>
                  <Money
                    minor={data.forecast.risk.min_balance_minor}
                    approximate
                    style={[
                      typeScale.title,
                      {
                        color:
                          data.forecast.risk.min_balance_minor <
                          data.forecast.reserve_minor
                            ? palette.danger
                            : palette.text,
                      },
                    ]}
                  />
                </View>
                <View
                  style={[
                    styles.safeDetail,
                    { borderColor: palette.border, borderTopWidth: 1 },
                  ]}
                >
                  <Muted>Ваш финансовый резерв</Muted>
                  <Text style={[typeScale.heading, { color: palette.text }]}>
                    {formatRub(data.forecast.reserve_minor)}
                  </Text>
                </View>
              </>
            ) : (
              <Muted>Оценка риска появится после расчёта прогноза.</Muted>
            )}
          </Card>
        </View>
      </Reveal>

      <Reveal delay={110}>
        <View style={[styles.overviewGrid, desktop && styles.horizontal]}>
          <View style={{ flex: desktop ? 1.55 : undefined, minWidth: 0 }}>
            {" "}
            <Card title={ru.dashboard.upcomingTitle} icon="calendar">
              {next.items.length === 0 ? (
                <Muted>{ru.dashboard.upcomingEmpty}</Muted>
              ) : (
                <>
                  {next.items.map((item) => (
                    <View
                      key={`${item.obligation_id}-${item.date}`}
                      style={styles.line}
                    >
                      <View
                        style={[
                          styles.dot,
                          {
                            backgroundColor:
                              item.status === "confirmed"
                                ? palette.accent
                                : palette.warning,
                          },
                        ]}
                      />
                      <View style={styles.lineMain}>
                        <Text
                          style={[styles.lineTitle, { color: palette.text }]}
                        >
                          {item.title}
                        </Text>
                        <Muted>
                          {formatDay(item.date, year)} ·{" "}
                          {ru.status[item.status as keyof typeof ru.status] ??
                            item.status}
                        </Muted>
                      </View>
                      <Text
                        style={[styles.lineAmount, { color: palette.text }]}
                      >
                        {formatRub(-item.amount_minor)}
                      </Text>
                    </View>
                  ))}
                  <View
                    style={[
                      styles.line,
                      styles.total,
                      { borderColor: palette.border },
                    ]}
                  >
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
          </View>
          <View style={{ flex: desktop ? 1 : undefined, minWidth: 0 }}>
            {" "}
            <Card title={ru.dashboard.accountsTitle} icon="wallet">
              {data.accounts.items.map((account) => {
                const line = describeAccount(account);
                return (
                  <View key={account.id} style={styles.line}>
                    <View style={styles.lineMain}>
                      <Text style={[styles.lineTitle, { color: palette.text }]}>
                        {account.name}
                      </Text>
                      <Muted>
                        {ru.accountType[account.type]}
                        {account.bank_name ? ` · ${account.bank_name}` : ""}
                        {line.kind === "excluded"
                          ? ` · ${ru.dashboard.notLiquid}`
                          : ""}
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
          </View>
        </View>
      </Reveal>

      <Card title={ru.dashboard.recentTitle} icon="wallet">
        <Muted>{ru.dashboard.recentHint}</Muted>
        {data.transactions.length === 0 ? (
          <Muted>{ru.dashboard.recentEmpty}</Muted>
        ) : (
          data.transactions.map((transaction) => (
            <View key={transaction.id} style={styles.activity}>
              <View style={styles.lineMain}>
                <Text style={[styles.lineTitle, { color: palette.text }]}>
                  {transaction.description ??
                    transaction.category ??
                    ru.feedback.fallbackTitle}
                </Text>
                <Muted>{formatMoment(transaction.occurred_at)}</Muted>
                {transaction.user_note ? (
                  <Text style={[styles.activityNote, { color: palette.muted }]}>
                    {`${ru.dashboard.personalNote}: ${transaction.user_note}`}
                  </Text>
                ) : null}
                {transaction.label ? (
                  <View style={styles.activityBadge}>
                    <Badge
                      label={ru.feedback.labels[transaction.label]}
                      tone="muted"
                    />
                  </View>
                ) : null}
              </View>
              <Text
                style={[
                  styles.lineAmount,
                  {
                    color:
                      transaction.amount_minor > 0 ? palette.ok : palette.text,
                  },
                ]}
              >
                {formatRub(transaction.amount_minor)}
              </Text>
            </View>
          ))
        )}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  overviewGrid: { gap: space.xl },
  horizontal: { flexDirection: "row", alignItems: "stretch" },
  sectionHeading: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    flexWrap: "wrap",
  },
  balanceBottom: {
    borderTopWidth: 1,
    paddingTop: space.lg,
    gap: space.lg,
    marginTop: space.md,
  },
  safeDetail: { gap: space.sm, paddingVertical: space.md },
  heroTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: space.md,
  },
  heroActions: { flexDirection: "row", gap: space.sm },
  // Бейджи сжимаются и переносятся, колокольчик остаётся в панели даже на 320–375 px.
  heroBadges: {
    flex: 1,
    flexDirection: "row",
    gap: space.sm,
    flexWrap: "wrap",
  },
  balance: { gap: space.md, paddingTop: space.lg },
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
  decisionTitle: {
    fontSize: 16,
    fontWeight: "600",
    lineHeight: 22,
    letterSpacing: -0.32,
  },
  decisionText: { fontSize: 14, lineHeight: 20 },
  stats: { flexDirection: "row", gap: space.sm },
  inlineChart: { gap: space.sm, paddingTop: space.xs },
  inlineChartTitle: { fontSize: 14, fontWeight: "600" },
  line: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space.md,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  lineMain: { flex: 1, gap: 2 },
  lineTitle: { fontSize: 14, fontWeight: "500" },
  lineAmount: {
    maxWidth: "48%",
    flexShrink: 1,
    fontSize: 14,
    fontWeight: "500",
    textAlign: "right",
    fontVariant: ["tabular-nums"],
  },
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
});
