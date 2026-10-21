import { Redirect, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api, ApiError, type Forecast, type ScenarioResult } from "@/shared/api/client";
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

import { ForecastChart } from "../forecast/ForecastChart";
import { RiskBanner } from "../forecast/ForecastScreen";
import { buildEvents, comparisonRows, type ComparisonRow } from "./logic";

const t = ru.simulate;
const DELAYS = ["0", "2", "5"] as const;
type Delay = (typeof DELAYS)[number];

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "Неизвестная ошибка.";
}

function cell(row: ComparisonRow, value: string | number | null, year: number): string {
  if (value === null) return "—";
  if (row.kind === "level") return ru.forecast.level[value as keyof typeof ru.forecast.level];
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
  const [amount, setAmount] = useState("");
  const [label, setLabel] = useState("");
  const [date, setDate] = useState("");
  const [delay, setDelay] = useState<Delay>("0");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    // Нужен только список доходов (items), календарь здесь не используется.
    Promise.all([api.createForecast(token, {}), api.listIncomes(token, "2000-01-01", "2000-01-02")])
      .then(([forecast, incomes]) => {
        setBase(forecast);
        setDate(formatDateInput(addDays(forecast.today, 1)));
        const salary = incomes.items.find((i) => i.kind === "salary") ?? incomes.items[0];
        setSalaryId(salary?.id ?? null);
      })
      .catch((err: unknown) => setFailure(messageOf(err)));
  }, [token]);

  if (!session || !token) {
    return <Redirect href="/" />;
  }
  if (!base) {
    return (
      <Screen>
        {failure ? <ErrorState title={t.error} message={failure} /> : <LoadingState label={t.loading} />}
      </Screen>
    );
  }

  const year = Number(base.today.slice(0, 4));
  const safe = base.safe_to_spend;

  const simulate = async () => {
    const parsedAmount = amount.trim() ? parseRubInput(amount) : null;
    const parsedDate = parseDateInput(date, base.today);
    const next: Record<string, string> = {};
    if (parsedAmount && !parsedAmount.ok) next.amount = parsedAmount.error;
    if (!parsedDate.ok) next.date = parsedDate.error;
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
    try {
      setResult(await api.createScenario(token, { base_forecast_id: base.forecast_id, events }));
    } catch (err) {
      setFailure(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const saveAsPlan = async () => {
    const parsedAmount = parseRubInput(amount);
    const parsedDate = parseDateInput(date, base.today);
    if (!parsedAmount.ok || !parsedDate.ok) return;
    try {
      await api.createObligation(token, {
        title: `${t.planPrefix}: ${label.trim() || t.defaultLabel}`,
        kind: "manual",
        amount_minor: parsedAmount.value,
        due_date: parsedDate.value,
        recurrence: "none",
        priority: "normal",
        movable: true,
      });
      setSaved(t.saved);
    } catch (err) {
      setFailure(messageOf(err));
    }
  };

  const discard = () => {
    setResult(null);
    setAmount("");
    setLabel("");
    setDelay("0");
    setSaved(null);
  };

  return (
    <Screen>
      <Card title={t.title}>
        {safe.available ? (
          <View style={styles.safe}>
            <Text style={{ color: palette.text }}>
              {t.safeLead} {formatDay(safe.date, year)}:{" "}
              <Text style={styles.bold}>{formatRubApprox(safe.base_minor)}</Text>
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
          onChangeText={setAmount}
          keyboardType="decimal-pad"
          placeholder="12 000"
          error={errors.amount}
        />
        <Field label={t.label} value={label} onChangeText={setLabel} placeholder={t.defaultLabel} />
        <Field label={t.date} value={date} onChangeText={setDate} error={errors.date} />
        {salaryId && session.user.plan === "plus" ? (
          <Choice
            label={t.delay}
            value={delay}
            onChange={setDelay}
            options={DELAYS.map((value) => ({
              value,
              label: value === "0" ? t.onTime : `${t.later} ${value} ${t.days}`,
            }))}
          />
        ) : salaryId ? <Muted>Задержка дохода и комбинации сценариев доступны в Plus. Режим можно проверить в разделе «Free и Plus».</Muted> : null}
        <Button testID="calculate-scenario" label={t.calculate} onPress={() => void simulate()} loading={busy} />
        <Muted>{t.noPayment}</Muted>
      </Card>

      {failure ? <ErrorState title={t.error} message={failure} /> : null}

      {result ? (
        <>
          <RiskBanner forecast={result.result} />
          <Card title={t.compareTitle}>
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
          <Card title={t.chartTitle}>
            <ForecastChart
              points={result.result.points}
              reserveMinor={result.result.reserve_minor}
              compare={result.base.points}
            />
            <Muted>{t.chartHint}</Muted>
          </Card>
          {amount.trim() ? (
            <Button label={t.saveAsPlan} onPress={() => void saveAsPlan()} disabled={saved !== null} />
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
  safe: { gap: space.xs },
  bold: { fontWeight: "700" },
  tableHead: { flexDirection: "row", gap: space.sm },
  headCell: { flex: 1, fontSize: 13, textAlign: "right" },
  row: { flexDirection: "row", gap: space.sm, alignItems: "center" },
  rowLabel: { flex: 1, fontSize: 14 },
  rowCell: { flex: 1, fontSize: 14, textAlign: "right" },
});
