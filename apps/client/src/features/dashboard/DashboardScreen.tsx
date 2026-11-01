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
import { ReserveEditor } from "@/features/forecast/ReserveEditor";
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
  Choice,
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
  const [detailsTab, setDetailsTab] = useState<
    "upcoming" | "accounts" | "activity"
  >("upcoming");
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
    <Screen
      wide
      headerActions={
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
      }
    >
      <View style={styles.dashboardHeader}>
        <View style={styles.headingBlock}>
          <Text style={[typeScale.eyebrow, { color: palette.muted }]}>
            ЛИЧНЫЙ КАПИТАЛ
          </Text>
          <Text
            accessibilityRole="header"
            style={[
              desktop ? typeScale.display : typeScale.title,
              { color: palette.text },
            ]}
          >
            Обзор финансов
          </Text>
          <Text style={[typeScale.body, { color: palette.muted }]}>
            Всё важное о ваших деньгах. В одном месте.
          </Text>
          <View style={styles.heroBadges}>
            <Badge label={session.user.display_name ?? ru.live.badge} />
            <Badge
              label={ru.dashboard.coverage[quality.coverage]}
              tone="muted"
            />
          </View>
        </View>
      </View>

      <Hero style={{ padding: desktop ? 32 : 20, gap: desktop ? 24 : 16 }}>
        <View style={[styles.heroSummary, desktop && styles.horizontal]}>
          <View style={[styles.balance, { flex: desktop ? 1.45 : undefined }]}>
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
            <Text style={[styles.heroLabel, { color: palette.heroMuted }]}>
              На счетах сейчас, без кредитных лимитов
            </Text>
          </View>

          <View
            style={[
              styles.safeInline,
              { backgroundColor: palette.heroChip, borderColor: palette.heroBorder },
              { flex: desktop ? 1 : undefined },
            ]}
          >
            <Text style={[typeScale.eyebrow, { color: palette.heroMuted }]}>
              МОЖНО ПОТРАТИТЬ ДО{" "}
              {data.forecast?.safe_to_spend.available
                ? formatDay(data.forecast.safe_to_spend.date, year)
                : "—"}
            </Text>
            {data.forecast?.safe_to_spend.available &&
            data.accounts.items.length > 0 ? (
              <>
                <Money
                  minor={data.forecast.safe_to_spend.base_minor}
                  approximate
                  style={[typeScale.title, { color: palette.heroText }]}
                />
                <Text
                  style={[styles.heroLabel, { color: palette.heroMuted }]}
                >
                  Из свободных средств уже вычтены будущие платежи, обычные
                  расходы и неснижаемый остаток {formatRub(data.forecast.reserve_minor)}
                </Text>
                <Text
                  style={[styles.heroLabel, { color: palette.heroMuted }]}
                >
                  Осторожная оценка:{" "}
                  {formatRubApprox(
                    data.forecast.safe_to_spend.conservative_minor,
                  )}
                </Text>
              </>
            ) : (
              <Text style={[styles.heroLabel, { color: palette.heroMuted }]}>
                Недостаточно данных для оценки
              </Text>
            )}
            <Button
              label={ru.forecast.whatIf}
              trailingIcon="arrow"
              variant="inverse"
              onPress={() =>
                router.push(data.accounts.items.length ? "/simulate" : "/add")
              }
            />
          </View>
        </View>

        <View
          style={[
            styles.balanceBottom,
            { borderColor: palette.heroBorder },
            desktop && styles.balanceBottomDesktop,
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

      {isLive && token ? (
        <SpendingReview
          token={token}
          refreshKey={feedbackKey}
          onChanged={onArrived}
        />
      ) : null}

      <Reveal delay={55}>
        <Card title="Прогноз на 30 дней" icon="chart">
          {data.forecast && data.accounts.items.length > 0 ? (
            <>
              <View
                style={[styles.forecastSummary, desktop && styles.horizontal]}
              >
                <View
                  style={[
                    styles.decision,
                    { backgroundColor: forecastTone?.soft, flex: 1 },
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
                        ? `Резерв может не сохраниться с ${formatDay(data.forecast.risk.date, year)}`
                        : data.forecast.risk_level === "medium"
                          ? "Запас сохранится, но неблагоприятный сценарий близок к резерву"
                          : "Даже неблагоприятный сценарий остаётся выше резерва"}
                    </Text>
                  </View>
                </View>
                <View style={styles.forecastStat}>
                  <Muted>
                    Минимум ·{" "}
                    {formatDay(data.forecast.risk.min_balance_date, year)}
                  </Muted>
                  <Money
                    minor={data.forecast.risk.min_balance_minor}
                    approximate
                    style={[typeScale.heading, { color: palette.text }]}
                  />
                </View>
                {token ? (
                  <ReserveEditor
                    token={token}
                    reserveMinor={data.forecast.reserve_minor}
                    onSaved={() => load(true)}
                  />
                ) : null}
              </View>
              <Text style={[typeScale.caption, { color: palette.muted }]}>
                Линия — ожидаемый остаток; полоса вокруг неё — возможный разброс
              </Text>
              <ForecastChart
                points={data.forecast.points}
                reserveMinor={data.forecast.reserve_minor}
                compact
              />
            </>
          ) : (
            <Muted>
              {data.accounts.items.length === 0
                ? ru.dashboard.noAccounts
                : ru.forecast.error}
            </Muted>
          )}
        </Card>
      </Reveal>

      <Reveal delay={110}>
        <Card title="Финансовые детали" icon="wallet">
          <Choice
            value={detailsTab}
            onChange={setDetailsTab}
            options={[
              { value: "upcoming", label: "Ближайшее" },
              { value: "accounts", label: "Счета" },
              { value: "activity", label: "Операции" },
            ]}
          />
          {detailsTab === "upcoming" ? (
            <View style={styles.detailContent}>
              {next.items.length === 0 ? (
                <Muted>{ru.dashboard.upcomingEmpty}</Muted>
              ) : (
                <>
                  {next.items.slice(0, 4).map((item) => (
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
                          {formatDay(item.date, year)}
                          {item.status === "confirmed"
                            ? ""
                            : ` · ${
                                ru.status[
                                  item.status as keyof typeof ru.status
                                ] ?? item.status
                              }`}
                        </Muted>
                      </View>
                      <Text
                        style={[styles.lineAmount, { color: palette.text }]}
                      >
                        {formatRub(-item.amount_minor)}
                      </Text>
                    </View>
                  ))}
                  {next.items.length > 4 ? (
                    <Button
                      label={`Ещё ${next.items.length - 4} в календаре`}
                      variant="secondary"
                      onPress={() => router.push("/calendar")}
                    />
                  ) : null}
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
            </View>
          ) : detailsTab === "accounts" ? (
            <View style={styles.detailContent}>
              {data.accounts.items.length === 0 ? (
                <Muted>{ru.dashboard.noAccounts}</Muted>
              ) : null}
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
            </View>
          ) : (
            <View style={styles.detailContent}>
              {data.transactions.length === 0 ? (
                <Muted>{ru.dashboard.recentEmpty}</Muted>
              ) : (
                data.transactions.slice(0, 4).map((transaction) => (
                  <View key={transaction.id} style={styles.activity}>
                    <View style={styles.lineMain}>
                      <Text
                        style={[styles.lineTitle, { color: palette.text }]}
                      >
                        {transaction.description ??
                          transaction.category ??
                          ru.feedback.fallbackTitle}
                      </Text>
                      <Muted>{formatMoment(transaction.occurred_at)}</Muted>
                      {transaction.user_note ? (
                        <Text
                          style={[
                            styles.activityNote,
                            { color: palette.muted },
                          ]}
                        >
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
                            transaction.amount_minor > 0
                              ? palette.ok
                              : palette.text,
                        },
                      ]}
                    >
                      {formatRub(transaction.amount_minor)}
                    </Text>
                  </View>
                ))
              )}
              {data.transactions.length > 0 ? (
                <Button
                  label="Вся история"
                  variant="secondary"
                  onPress={() => router.push("/calendar")}
                />
              ) : null}
            </View>
          )}
        </Card>
      </Reveal>
    </Screen>
  );
}

const styles = StyleSheet.create({
  horizontal: { flexDirection: "row", alignItems: "stretch" },
  dashboardHeader: {
    justifyContent: "space-between",
    gap: space.lg,
  },
  headingBlock: { flex: 1, gap: space.sm },
  detailContent: { gap: space.md },
  heroSummary: { gap: space.xl, alignItems: "stretch" },
  forecastSummary: { gap: space.md, alignItems: "stretch" },
  forecastStat: {
    flex: 0.7,
    minWidth: 160,
    gap: space.xs,
    justifyContent: "center",
  },
  safeInline: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.lg,
    padding: space.lg,
    gap: space.md,
    justifyContent: "center",
  },
  balanceBottom: {
    borderTopWidth: 1,
    paddingTop: space.lg,
    gap: space.lg,
    marginTop: space.md,
  },
  balanceBottomDesktop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  heroActions: {
    flexDirection: "row",
    gap: space.sm,
    alignSelf: "flex-start",
  },
  // Бейджи сжимаются и переносятся, колокольчик остаётся в панели даже на 320–375 px.
  heroBadges: {
    flex: 1,
    flexDirection: "row",
    gap: space.sm,
    flexWrap: "wrap",
  },
  balance: { gap: space.md, paddingTop: space.lg },
  heroLabel: { fontSize: 13, fontWeight: "500" },
  freshness: { flexDirection: "row", alignItems: "center", gap: 6 },
  decision: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: space.md,
    borderRadius: radius.md,
    padding: space.md,
  },
  decisionTitle: {
    fontSize: 16,
    fontWeight: "600",
    lineHeight: 22,
    letterSpacing: -0.32,
  },
  decisionText: { fontSize: 14, lineHeight: 20 },
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
