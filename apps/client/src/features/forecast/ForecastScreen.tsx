import { Redirect, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api, ApiError, type Forecast } from "@/shared/api/client";
import { formatDay, formatRub, formatRubApprox } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import {
  Badge,
  Button,
  Card,
  Choice,
  ErrorState,
  LoadingState,
  Muted,
  Screen,
} from "@/shared/ui/components";
import { space, usePalette } from "@/shared/ui/theme";

import { ForecastChart } from "./ForecastChart";
import { keyDays, riskTone } from "./logic";

const t = ru.forecast;
const RESERVES = ["0", "500000", "1000000", "2000000"] as const;
type ReserveOption = (typeof RESERVES)[number];

export function RiskBanner({ forecast }: { forecast: Forecast }) {
  const palette = usePalette();
  const tone = riskTone(forecast.risk_level);
  const color = tone === "danger" ? palette.danger : tone === "warning" ? palette.warning : palette.ok;
  return (
    <View
      accessibilityRole="alert"
      style={[styles.banner, { borderColor: color, backgroundColor: palette.card }]}
    >
      <Text style={[styles.bannerTitle, { color }]}>{t.level[forecast.risk_level]}</Text>
      <Text style={[styles.bannerText, { color: palette.text }]}>
        {forecast.risk.explanation}
      </Text>
      {forecast.risk.shortfall_minor > 0 ? (
        <Muted>
          {forecast.risk_level === "medium" ? t.shortfallPessimistic : t.shortfall}:{" "}
          {formatRubApprox(forecast.risk.shortfall_minor)}
        </Muted>
      ) : null}
    </View>
  );
}

export function ForecastScreen() {
  const router = useRouter();
  const palette = usePalette();
  const { session } = useSession();
  const token = session?.access_token;
  const [reserve, setReserve] = useState<ReserveOption>("500000");
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      setForecast(await api.createForecast(token, { reserve_minor: Number(reserve) }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    } finally {
      setLoading(false);
    }
  }, [token, reserve]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!session || !token) {
    return <Redirect href="/" />;
  }

  const year = forecast ? Number(forecast.today.slice(0, 4)) : undefined;

  return (
    <Screen>
      <Card title={t.title}>
        <Choice
          label={t.reserve}
          value={reserve}
          onChange={setReserve}
          options={RESERVES.map((value) => ({ value, label: formatRub(Number(value)) }))}
        />
        <Muted>{t.reserveHint}</Muted>
      </Card>

      {error ? <ErrorState title={t.error} message={error} onRetry={() => void load()} /> : null}
      {loading && !forecast ? <LoadingState label={t.loading} /> : null}

      {forecast ? (
        <>
          <RiskBanner forecast={forecast} />

          <Card title={t.chartTitle}>
            <ForecastChart points={forecast.points} reserveMinor={forecast.reserve_minor} />
            <View style={styles.legend}>
              <Badge label={t.legendBase} tone="ok" />
              <Badge label={t.legendRange} />
              <Badge label={t.legendBelow} tone="warning" />
            </View>
            <Muted>
              {t.minimum}: {formatRubApprox(forecast.risk.min_balance_minor)} ·{" "}
              {formatDay(forecast.risk.min_balance_date, year)} · {t.pessimistic}:{" "}
              {formatRubApprox(forecast.risk.pessimistic_min_minor)}
            </Muted>
          </Card>

          {forecast.risk.drivers.length > 0 ? (
            <Card title={t.driversTitle}>
              {forecast.risk.drivers.map((driver) => (
                <View key={`${driver.kind}-${driver.code}-${driver.date ?? ""}`} style={styles.line}>
                  <View style={styles.lineMain}>
                    <Text style={{ color: palette.text }}>{driver.label}</Text>
                    <Muted>
                      {t.driverKind[driver.kind]}
                      {driver.date ? ` · ${formatDay(driver.date, year)}` : ""}
                    </Muted>
                  </View>
                  {driver.amount_minor > 0 ? (
                    <Text style={[styles.amount, { color: palette.text }]}>
                      {formatRubApprox(-driver.amount_minor)}
                    </Text>
                  ) : null}
                </View>
              ))}
            </Card>
          ) : null}

          <Card title={t.daysTitle}>
            {keyDays(forecast.points, forecast.risk_date, forecast.risk.min_balance_date).map(
              (point) => (
                <View key={point.day} style={styles.line}>
                  <View style={styles.lineMain}>
                    <Text style={{ color: point.below_reserve ? palette.danger : palette.text }}>
                      {formatDay(point.day, year)}
                    </Text>
                    <Muted>
                      {point.outflow_minor > 0 ? `${t.payments} ${formatRub(-point.outflow_minor)} ` : ""}
                      {point.inflow_minor > 0 ? `${t.incomes} ${formatRub(point.inflow_minor)}` : ""}
                    </Muted>
                  </View>
                  <View style={styles.values}>
                    <Text style={[styles.amount, { color: palette.text }]}>
                      {formatRubApprox(point.p50_minor)}
                    </Text>
                    <Muted>
                      {formatRubApprox(point.p10_minor)} … {formatRubApprox(point.p90_minor)}
                    </Muted>
                  </View>
                </View>
              ),
            )}
          </Card>

          <Card title={t.qualityTitle}>
            {forecast.quality.notes.map((note) => (
              <Muted key={note}>• {note}</Muted>
            ))}
            <Muted>
              {t.model} {forecast.model_version} · {t.history} {forecast.quality.history_days}{" "}
              {t.days}
            </Muted>
            <Muted>{t.disclaimer}</Muted>
          </Card>

          <Button label={t.refresh} onPress={() => void load()} loading={loading} />
          <Button label={t.toCalendar} variant="secondary" onPress={() => router.push("/calendar")} />
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  banner: { borderWidth: 2, borderRadius: 14, padding: space.lg, gap: space.sm },
  bannerTitle: { fontSize: 18, fontWeight: "700" },
  bannerText: { fontSize: 15, lineHeight: 22 },
  legend: { flexDirection: "row", gap: space.sm, flexWrap: "wrap" },
  line: { flexDirection: "row", justifyContent: "space-between", gap: space.md },
  lineMain: { flex: 1, gap: 2 },
  values: { alignItems: "flex-end", gap: 2 },
  amount: { fontWeight: "600" },
});
