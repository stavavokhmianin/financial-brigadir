import { Redirect } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { StyleSheet, View, useWindowDimensions } from "react-native";

import {
  api,
  ApiError,
  type Forecast,
  type IncomesResponse,
  type ScenarioResult,
} from "@/shared/api/client";
import { addDays, formatDay, formatRubApprox, plural } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { formatDateInput, parseDateInput, parseRubInput } from "@/shared/input";
import { useSession } from "@/shared/session";
import {
  Button,
  Card,
  Choice,
  ErrorState,
  Field,
  LoadingState,
  Muted,
  Screen,
} from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { fonts, radius, space, usePalette } from "@/shared/ui/theme";
import { Money } from "@/shared/ui/money";
import { Reveal } from "@/shared/ui/motion";
import { Text } from "@/shared/ui/text";

import { ForecastChart } from "../forecast/ForecastChart";
import { RiskScale } from "../forecast/ForecastScreen";
import {
  buildEvents,
  comparisonRows,
  isScenarioDateAllowed,
  scenarioVerdict,
  scenarioDateRange,
  type ComparisonRow,
} from "./logic";

const t = ru.simulate;
const DELAYS = ["0", "2", "5"] as const;
type Delay = (typeof DELAYS)[number];
type Income = IncomesResponse["items"][number];

interface SubmittedPurchase {
  amountMinor: number;
  date: string;
  label: string;
  idempotencyKey: string;
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "Неизвестная ошибка.";
}

function cell(
  row: ComparisonRow,
  value: string | number | null,
  year: number,
): string {
  if (value === null) return "—";
  if (row.kind === "level")
    return ru.forecast.scale[value as keyof typeof ru.forecast.scale];
  if (row.kind === "date") return formatDay(String(value), year);
  if (row.kind === "days") return String(value);
  return formatRubApprox(Number(value));
}

export function SimulateScreen() {
  const palette = usePalette();
  const { width } = useWindowDimensions();
  const desktop = width >= 960;
  const { session } = useSession();
  const token = session?.access_token;
  const [base, setBase] = useState<Forecast | null>(null);
  const [salaryId, setSalaryId] = useState<string | null>(null);
  const [incomes, setIncomes] = useState<Income[]>([]);
  const [amount, setAmount] = useState("");
  const [merchant, setMerchant] = useState("");
  const [category, setCategory] = useState("");
  const [date, setDate] = useState("");
  const [delay, setDelay] = useState<Delay>("0");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [submittedPurchase, setSubmittedPurchase] =
    useState<SubmittedPurchase | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [reload, setReload] = useState(0);
  const inputRevision = useRef(0);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setBase(null);
    setFailure(null);
    setResult(null);
    setSubmittedPurchase(null);
    setSaved(null);
    // Без окна дат API возвращает сами доходы и календарь по умолчанию.
    Promise.all([api.createForecast(token, {}), api.listIncomes(token)])
      .then(([forecast, incomes]) => {
        if (!active) return;
        setBase(forecast);
        setDate(formatDateInput(addDays(forecast.today, 1)));
        setIncomes(incomes.items);
        const salary =
          incomes.items.find((i) => i.kind === "salary") ?? incomes.items[0];
        setSalaryId(salary?.id ?? null);
      })
      .catch((err: unknown) => {
        if (active) setFailure(messageOf(err));
      });
    return () => {
      active = false;
    };
  }, [token, reload]);

  if (!session || !token) {
    return <Redirect href="/" />;
  }
  if (!base) {
    return (
      <Screen wide>
        {failure ? (
          <ErrorState
            title={t.error}
            message={failure}
            onRetry={() => setReload((value) => value + 1)}
          />
        ) : (
          <LoadingState label={t.loading} />
        )}
      </Screen>
    );
  }

  const year = Number(base.today.slice(0, 4));
  const safe = base.safe_to_spend;
  const dateRange = scenarioDateRange(base.today, base.horizon_days);

  const invalidateResult = () => {
    inputRevision.current += 1;
    setResult(null);
    setSubmittedPurchase(null);
    setSaved(null);
    setShowDetails(false);
  };

  const simulate = async () => {
    const revision = inputRevision.current;
    const parsedAmount = amount.trim() ? parseRubInput(amount) : null;
    const parsedDate = parseDateInput(date, base.today);
    const next: Record<string, string> = {};
    if (parsedAmount && !parsedAmount.ok) next.amount = parsedAmount.error;
    if (!parsedDate.ok) next.date = parsedDate.error;
    if (
      parsedDate.ok &&
      !isScenarioDateAllowed(parsedDate.value, base.today, base.horizon_days)
    ) {
      next.date = `${t.dateRange} ${formatDay(dateRange.min, year)} — ${formatDay(dateRange.max, year)}`;
    }
    setErrors(next);
    if (Object.keys(next).length > 0 || !parsedDate.ok) return;
    const events = buildEvents({
      amountMinor: parsedAmount?.ok ? parsedAmount.value : null,
      date: parsedDate.value,
      merchant,
      category,
      salaryId,
      delayDays: Number(delay),
    });
    if (events.length === 0) {
      setErrors({ amount: t.nothing });
      return;
    }
    setBusy(true);
    setFailure(null);
    setSaved(null);
    setResult(null);
    setSubmittedPurchase(null);
    try {
      const nextResult = await api.createScenario(token, {
        base_forecast_id: base.forecast_id,
        events,
      });
      if (revision !== inputRevision.current) return;
      setResult(nextResult);
      if (parsedAmount?.ok) {
        setSubmittedPurchase({
          amountMinor: parsedAmount.value,
          date: parsedDate.value,
          label: merchant.trim() || category.trim() || t.defaultLabel,
          idempotencyKey: `scenario-plan-${nextResult.scenario_id}`,
        });
      }
    } catch (err) {
      setFailure(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const saveAsPlan = async () => {
    if (!submittedPurchase || saving || saved) return;
    setSaving(true);
    setFailure(null);
    try {
      await api.createObligation(
        token,
        {
          title: `${t.planPrefix}: ${submittedPurchase.label}`,
          kind: "manual",
          amount_minor: submittedPurchase.amountMinor,
          due_date: submittedPurchase.date,
          recurrence: "none",
          priority: "normal",
          movable: true,
        },
        submittedPurchase.idempotencyKey,
      );
      setSaved(t.saved);
    } catch (err) {
      setFailure(messageOf(err));
    } finally {
      setSaving(false);
    }
  };

  const discard = () => {
    setResult(null);
    setAmount("");
    setMerchant("");
    setCategory("");
    setDelay("0");
    setSaved(null);
    setSubmittedPurchase(null);
    setShowDetails(false);
  };

  const edit = () => {
    setResult(null);
    setSaved(null);
    setShowDetails(false);
  };

  const verdict = result ? scenarioVerdict(result) : null;
  const verdictTone = verdict
    ? verdict.kind === "shortfall"
      ? {
          color: palette.danger,
          soft: palette.dangerSoft,
          icon: "alert" as const,
        }
      : verdict.kind === "tight"
        ? {
            color: palette.warning,
            soft: palette.warningBg,
            icon: "alert" as const,
          }
        : { color: palette.ok, soft: palette.okSoft, icon: "check" as const }
    : null;

  return (
    <Screen wide>
      {!result ? (
        <View
          style={{
            flexDirection: desktop ? "row" : "column",
            alignItems: "flex-start",
            gap: 24,
          }}
        >
          <Card
            title={t.title}
            icon="cart"
            style={{
              flex: desktop ? 1 : undefined,
              width: desktop ? undefined : "100%",
            }}
          >
            {safe.available ? (
              <View style={[styles.safe, { backgroundColor: palette.okSoft }]}>
                <Text style={{ color: palette.text }}>
                  {t.safeLead} {formatDay(safe.date, year)}:
                </Text>
                <Money
                  minor={safe.base_minor}
                  approximate
                  style={[styles.safeValue, { color: palette.ok }]}
                />
                <Muted>
                  {safe.conservative_minor > 0
                    ? `${t.safeCareful} ${formatRubApprox(safe.conservative_minor)}`
                    : t.safeCarefulNone}
                </Muted>
              </View>
            ) : (
              <Muted>{t.safeUnavailable}</Muted>
            )}
            <Field
              label={t.amount}
              testID="purchase-amount"
              value={amount}
              onChangeText={(value) => {
                setAmount(value);
                invalidateResult();
              }}
              keyboardType="decimal-pad"
              placeholder="12 000"
              error={errors.amount}
            />
            <Field
              label={t.merchant}
              value={merchant}
              onChangeText={(value) => {
                setMerchant(value);
                invalidateResult();
              }}
              placeholder={t.merchantPlaceholder}
              hint={t.contextHint}
            />
            <Field
              label={t.category}
              value={category}
              onChangeText={(value) => {
                setCategory(value);
                invalidateResult();
              }}
              placeholder={t.categoryPlaceholder}
            />
            <Field
              label={t.date}
              value={date}
              onChangeText={(value) => {
                setDate(value);
                invalidateResult();
              }}
              error={errors.date}
              hint={`${t.dateRange} ${formatDay(dateRange.min, year)} — ${formatDay(dateRange.max, year)}`}
            />
            {salaryId && session.user.plan === "plus" ? (
              <>
                {incomes.length > 1 ? (
                  <Choice
                    label={t.delayIncome}
                    value={salaryId}
                    onChange={(value) => {
                      setSalaryId(value);
                      invalidateResult();
                    }}
                    options={incomes.map((income) => ({
                      value: income.id,
                      label: income.title,
                    }))}
                  />
                ) : null}
                <Choice
                  label={t.delay}
                  value={delay}
                  onChange={(value) => {
                    setDelay(value);
                    invalidateResult();
                  }}
                  options={DELAYS.map((value) => ({
                    value,
                    label:
                      value === "0"
                        ? t.onTime
                        : `${t.later} ${value} ${t.days}`,
                  }))}
                />
              </>
            ) : salaryId ? (
              <Muted>{t.plusOnly}</Muted>
            ) : null}
            <Button
              testID="calculate-scenario"
              label={t.calculate}
              onPress={() => void simulate()}
              loading={busy}
            />
            <Muted>{t.noPayment}</Muted>
          </Card>
          <Card
            title="Ваш прогноз сейчас"
            icon="chart"
            style={{
              flex: desktop ? 1.2 : undefined,
              width: desktop ? undefined : "100%",
            }}
          >
            <Muted>
              После расчёта здесь появится сравнение с новым сценарием.
            </Muted>
            <ForecastChart
              points={base.points}
              reserveMinor={base.reserve_minor}
            />
            <RiskScale level={base.risk_level} />
          </Card>
        </View>
      ) : null}

      {failure ? <ErrorState title={t.error} message={failure} /> : null}

      {result && verdict && verdictTone ? (
        <>
          <Reveal>
            <View
              accessibilityRole="alert"
              testID={`scenario-verdict-${verdict.kind}`}
              style={[styles.verdict, { backgroundColor: verdictTone.soft }]}
            >
              <View
                style={[
                  styles.verdictIcon,
                  { backgroundColor: verdictTone.color },
                ]}
              >
                <Icon name={verdictTone.icon} color={palette.card} size={18} />
              </View>
              <Text style={[styles.verdictTitle, { color: verdictTone.color }]}>
                {t.verdict[verdict.kind]}
              </Text>
              <Text style={[styles.verdictLead, { color: palette.text }]}>
                {verdict.kind === "shortfall" && verdict.shortfallMinor > 0
                  ? `${t.verdictLead.shortfall} ${formatRubApprox(verdict.shortfallMinor)}.`
                  : t.verdictLead[verdict.kind]}
              </Text>
              {verdict.date ? (
                <Text style={[styles.verdictDate, { color: palette.text }]}>
                  {t.riskFrom} {formatDay(verdict.date, year)}.
                </Text>
              ) : null}
              <View style={styles.reasons}>
                <Text style={[styles.reasonTitle, { color: palette.muted }]}>
                  {t.why}
                </Text>
                {result.result.risk.drivers.length > 0 ? (
                  result.result.risk.drivers.slice(0, 2).map((driver) => (
                    <View
                      key={`${driver.kind}-${driver.code}-${driver.date ?? ""}`}
                      style={styles.reason}
                    >
                      <View
                        style={[
                          styles.reasonDot,
                          { backgroundColor: verdictTone.color },
                        ]}
                      />
                      <Text
                        style={[styles.reasonText, { color: palette.text }]}
                      >
                        {driver.label}
                        {driver.date
                          ? ` · ${formatDay(driver.date, year)}`
                          : ""}
                      </Text>
                    </View>
                  ))
                ) : (
                  <Muted>{verdict.explanation}</Muted>
                )}
              </View>
              {base.safe_to_spend.available ? (
                <View
                  style={[
                    styles.guide,
                    {
                      backgroundColor: palette.card,
                      borderColor: palette.border,
                    },
                  ]}
                >
                  <Text style={[styles.guideLabel, { color: palette.muted }]}>
                    {t.currentGuide}
                  </Text>
                  <Text style={[styles.guideValue, { color: palette.text }]}>
                    {formatRubApprox(base.safe_to_spend.base_minor)}
                  </Text>
                </View>
              ) : null}
              {result.purchase_context ? (
                <View
                  style={[
                    styles.context,
                    {
                      backgroundColor: palette.card,
                      borderColor: palette.border,
                    },
                  ]}
                >
                  <Text style={[styles.contextTitle, { color: palette.text }]}>
                    {t.contextTitle}
                  </Text>
                  {result.purchase_context.basis === "amount_only" ? (
                    <Muted>{t.contextUnavailable}</Muted>
                  ) : (
                    <>
                      <Muted>
                        {`${result.purchase_context.observations} ${plural(
                          result.purchase_context.observations,
                          t.similarTransactions,
                        )} · ${t.contextBasis[result.purchase_context.basis]}`}
                      </Muted>
                      {result.purchase_context.lower_minor !== null &&
                      result.purchase_context.upper_minor !== null ? (
                        <Text
                          style={[styles.contextRange, { color: palette.text }]}
                        >
                          {`${t.usualRange} ${formatRubApprox(result.purchase_context.lower_minor)} — ${formatRubApprox(result.purchase_context.upper_minor)}`}
                        </Text>
                      ) : null}
                      <Muted>
                        {
                          t.amountPosition[
                            result.purchase_context.amount_position
                          ]
                        }
                      </Muted>
                    </>
                  )}
                </View>
              ) : null}
            </View>
          </Reveal>

          {verdict.kind === "fits" && submittedPurchase ? (
            <Button
              label={t.saveAsPlan}
              onPress={() => void saveAsPlan()}
              loading={saving}
              disabled={saved !== null}
            />
          ) : (
            <Button label={t.edit} onPress={edit} />
          )}
          {saved ? <Text style={{ color: palette.ok }}>{saved}</Text> : null}
          {verdict.kind === "fits" ? (
            <Button label={t.edit} variant="secondary" onPress={edit} />
          ) : submittedPurchase ? (
            <Button
              label={t.saveAsPlan}
              variant="secondary"
              onPress={() => void saveAsPlan()}
              loading={saving}
              disabled={saved !== null}
            />
          ) : null}
          <Button
            label={showDetails ? t.detailsHide : t.detailsShow}
            variant="secondary"
            onPress={() => setShowDetails((value) => !value)}
          />

          <Card title={t.chartTitle} icon="chart">
            <ForecastChart
              points={result.result.points}
              reserveMinor={result.result.reserve_minor}
              compare={result.base.points}
            />
            <Muted>{t.chartHint}</Muted>
          </Card>
          {showDetails ? (
            <>
              <Card title={t.compareTitle} icon="sparkle">
                <RiskScale
                  level={result.risk_level_after}
                  previous={result.risk_level_before}
                />
                <Muted>{result.explanation}</Muted>
                <View style={styles.tableHead}>
                  <Text style={[styles.headCell, { color: palette.muted }]} />
                  <Text style={[styles.headCell, { color: palette.muted }]}>
                    {t.before}
                  </Text>
                  <Text style={[styles.headCell, { color: palette.muted }]}>
                    {t.after}
                  </Text>
                </View>
                {comparisonRows(result).map((row) => (
                  <View key={row.kind} style={styles.row}>
                    <Text style={[styles.rowLabel, { color: palette.text }]}>
                      {t.rows[row.kind]}
                    </Text>
                    <Text style={[styles.rowCell, { color: palette.text }]}>
                      {cell(row, row.before, year)}
                    </Text>
                    <Text
                      style={[
                        styles.rowCell,
                        styles.bold,
                        { color: row.worse ? palette.danger : palette.text },
                      ]}
                    >
                      {cell(row, row.after, year)}
                    </Text>
                  </View>
                ))}
                {result.base_recomputed ? <Muted>{t.recomputed}</Muted> : null}
              </Card>
            </>
          ) : null}
          <Button label={t.discard} variant="secondary" onPress={discard} />
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  safe: { gap: space.xs, borderRadius: radius.md, padding: space.md },
  safeValue: {
    fontSize: 26,
    fontWeight: "600",
    letterSpacing: -1,
    fontVariant: ["tabular-nums"],
  },
  verdict: { borderRadius: radius.lg, padding: space.xl, gap: space.md },
  verdictIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  verdictTitle: {
    fontSize: 24,
    lineHeight: 30,
    fontWeight: "600",
    letterSpacing: -0.96,
  },
  verdictLead: { fontSize: 16, lineHeight: 24, fontWeight: "500" },
  verdictDate: { fontSize: 14, lineHeight: 21, fontWeight: "500" },
  guide: { borderRadius: radius.md, borderWidth: 1, padding: space.md, gap: 2 },
  guideLabel: { fontSize: 13, fontWeight: "500" },
  guideValue: {
    fontSize: 22,
    fontWeight: "600",
    letterSpacing: -0.8,
    fontVariant: ["tabular-nums"],
  },
  context: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: space.md,
    gap: space.xs,
  },
  contextTitle: { fontSize: 14, lineHeight: 20, fontWeight: "600" },
  contextRange: { fontSize: 14, lineHeight: 20, fontWeight: "700" },
  reasons: { gap: space.sm },
  reasonTitle: {
    fontFamily: fonts.mono,
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  reason: { flexDirection: "row", alignItems: "center", gap: space.sm },
  reasonDot: { width: 7, height: 7, borderRadius: 4 },
  reasonText: { flex: 1, fontSize: 14, lineHeight: 21, fontWeight: "500" },
  bold: { fontWeight: "700" },
  tableHead: { flexDirection: "row", gap: space.sm },
  headCell: { flex: 1, fontSize: 13, textAlign: "right" },
  row: { flexDirection: "row", gap: space.sm, alignItems: "center" },
  rowLabel: { flex: 1, fontSize: 14 },
  rowCell: {
    flex: 1,
    fontSize: 14,
    textAlign: "right",
    fontVariant: ["tabular-nums"],
  },
});
