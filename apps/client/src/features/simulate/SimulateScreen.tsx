import { Redirect, useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { StyleSheet, View } from "react-native";

import {
  api,
  ApiError,
  type Forecast,
  type IncomesResponse,
  type ScenarioResult,
} from "@/shared/api/client";
import { addDays, formatDay, formatRubApprox } from "@/shared/format";
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
import { space, usePalette } from "@/shared/ui/theme";
import { Text } from "@/shared/ui/text";

import { ForecastChart } from "../forecast/ForecastChart";
import { RiskBanner } from "../forecast/ForecastScreen";
import {
  buildEvents,
  comparisonRows,
  isScenarioDateAllowed,
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

function cell(row: ComparisonRow, value: string | number | null, year: number): string {
  if (value === null) return "—";
  if (row.kind === "level") return ru.forecast.scale[value as keyof typeof ru.forecast.scale];
  if (row.kind === "date") return formatDay(String(value), year);
  if (row.kind === "days") return String(value);
  return formatRubApprox(Number(value));
}

export function SimulateScreen() {
  const router = useRouter();
  const palette = usePalette();
  const { session } = useSession();
  const token = session?.access_token;
  const [base, setBase] = useState<Forecast | null>(null);
  const [salaryId, setSalaryId] = useState<string | null>(null);
  const [incomes, setIncomes] = useState<Income[]>([]);
  const [amount, setAmount] = useState("");
  const [label, setLabel] = useState("");
  const [date, setDate] = useState("");
  const [delay, setDelay] = useState<Delay>("0");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [submittedPurchase, setSubmittedPurchase] = useState<SubmittedPurchase | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
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
    // Нужен только список доходов (items), календарь здесь не используется.
    Promise.all([api.createForecast(token, {}), api.listIncomes(token, "2000-01-01", "2000-01-02")])
      .then(([forecast, incomes]) => {
        if (!active) return;
        setBase(forecast);
        setDate(formatDateInput(addDays(forecast.today, 1)));
        setIncomes(incomes.items);
        const salary = incomes.items.find((i) => i.kind === "salary") ?? incomes.items[0];
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
      <Screen>
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
      label,
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
          label: label.trim() || t.defaultLabel,
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
    setLabel("");
    setDelay("0");
    setSaved(null);
    setSubmittedPurchase(null);
  };

  return (
    <Screen>
      <Card title={t.title} icon="cart">
        {safe.available ? (
          <View style={[styles.safe, { backgroundColor: palette.okSoft }]}>
            <Text style={{ color: palette.text }}>
              {t.safeLead} {formatDay(safe.date, year)}:
            </Text>
            <Text style={[styles.safeValue, { color: palette.ok }]}>
              {formatRubApprox(safe.base_minor)}
            </Text>
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
          label={t.label}
          value={label}
          onChangeText={(value) => {
            setLabel(value);
            invalidateResult();
          }}
          placeholder={t.defaultLabel}
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
                options={incomes.map((income) => ({ value: income.id, label: income.title }))}
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
                label: value === "0" ? t.onTime : `${t.later} ${value} ${t.days}`,
              }))}
            />
          </>
        ) : salaryId ? <Muted>{t.plusOnly}</Muted> : null}
        <Button testID="calculate-scenario" label={t.calculate} onPress={() => void simulate()} loading={busy} />
        <Muted>{t.noPayment}</Muted>
      </Card>

      {failure ? <ErrorState title={t.error} message={failure} /> : null}

      {result ? (
        <>
          <RiskBanner forecast={result.result} previous={result.risk_level_before} />
          <Card title={t.compareTitle} icon="sparkle">
            <Muted>{result.explanation}</Muted>
            <View style={styles.tableHead}>
              <Text style={[styles.headCell, { color: palette.muted }]} />
              <Text style={[styles.headCell, { color: palette.muted }]}>{t.before}</Text>
              <Text style={[styles.headCell, { color: palette.muted }]}>{t.after}</Text>
            </View>
            {comparisonRows(result).map((row) => (
              <View key={row.kind} style={styles.row}>
                <Text style={[styles.rowLabel, { color: palette.text }]}>{t.rows[row.kind]}</Text>
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
          <Card title={t.chartTitle} icon="chart">
            <ForecastChart
              points={result.result.points}
              reserveMinor={result.result.reserve_minor}
              compare={result.base.points}
            />
            <Muted>{t.chartHint}</Muted>
          </Card>
          {submittedPurchase ? (
            <Button
              label={t.saveAsPlan}
              onPress={() => void saveAsPlan()}
              loading={saving}
              disabled={saved !== null}
            />
          ) : null}
          {saved ? <Text style={{ color: palette.ok }}>{saved}</Text> : null}
          <Button label={t.discard} variant="secondary" onPress={discard} />
          <Button label={t.toForecast} variant="secondary" onPress={() => router.push("/forecast")} />
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  safe: { gap: space.xs, borderRadius: 14, padding: space.md },
  safeValue: { fontSize: 26, fontWeight: "800", letterSpacing: -0.5 },
  bold: { fontWeight: "700" },
  tableHead: { flexDirection: "row", gap: space.sm },
  headCell: { flex: 1, fontSize: 13, textAlign: "right" },
  row: { flexDirection: "row", gap: space.sm, alignItems: "center" },
  rowLabel: { flex: 1, fontSize: 14 },
  rowCell: { flex: 1, fontSize: 14, textAlign: "right" },
});
