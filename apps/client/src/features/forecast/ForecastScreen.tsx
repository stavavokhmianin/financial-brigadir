import { Redirect, useRouter } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, View, useWindowDimensions } from "react-native";

import { api, ApiError, type Forecast } from "@/shared/api/client";
import { formatDay, formatRub, formatRubApprox } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import {
  Button,
  Card,
  Choice,
  ErrorState,
  LoadingState,
  Muted,
  Screen,
  Stat,
} from "@/shared/ui/components";
import { Icon, type IconName } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { radius, space, usePalette, type Palette } from "@/shared/ui/theme";

import { ForecastChart } from "./ForecastChart";
import { keyDays, riskScale, riskShift, riskTone } from "./logic";

const t = ru.forecast;
const RESERVES = ["0", "500000", "1000000", "2000000"] as const;
type ReserveOption = (typeof RESERVES)[number];

function toneColors(
  palette: Palette,
  level: string,
): { color: string; soft: string } {
  const tone = riskTone(level);
  if (tone === "danger")
    return { color: palette.danger, soft: palette.dangerSoft };
  if (tone === "warning")
    return { color: palette.warning, soft: palette.warningBg };
  return { color: palette.ok, soft: palette.okSoft };
}

/** Шкала «низкий / средний / высокий» в одном треке; previous — уровень до сценария. */
export function RiskScale({
  level,
  previous,
}: {
  level: string;
  previous?: string | null;
}) {
  const palette = usePalette();
  const steps = riskScale(level, previous);
  const current = t.scale[level as keyof typeof t.scale] ?? level;
  const label = previous
    ? `${t.scaleTitle}: ${t.scale[previous as keyof typeof t.scale] ?? previous} → ${current}`
    : `${t.scaleTitle}: ${current}`;
  return (
    <View
      accessible
      accessibilityLabel={label}
      testID={`risk-scale-${level}`}
      style={[
        styles.scale,
        { backgroundColor: palette.card, borderColor: palette.border },
      ]}
    >
      {steps.map((step) => {
        const { color } = toneColors(palette, step.level);
        return (
          <View
            key={step.level}
            style={[
              styles.scaleStep,
              step.active ? { backgroundColor: color } : null,
              step.previous
                ? { borderColor: color, borderWidth: 1, borderStyle: "dashed" }
                : null,
            ]}
          >
            <Text
              style={[
                styles.scaleText,
                {
                  color: step.active
                    ? palette.card
                    : step.previous
                      ? color
                      : palette.muted,
                },
              ]}
            >
              {t.scale[step.level]}
            </Text>
            {step.previous ? (
              <Text style={[styles.scaleWas, { color }]}>{t.scaleWas}</Text>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

export function RiskBanner({
  forecast,
  previous,
}: {
  forecast: Forecast;
  previous?: string | null;
}) {
  const palette = usePalette();
  const { color, soft } = toneColors(palette, forecast.risk_level);
  const icon: IconName = forecast.risk_level === "low" ? "check" : "alert";
  return (
    <View
      accessibilityRole="alert"
      testID={`risk-${forecast.risk_level}`}
      style={[styles.banner, { backgroundColor: soft }]}
    >
      <View style={styles.bannerHead}>
        <View style={[styles.bannerIcon, { backgroundColor: color }]}>
          <Icon name={icon} color={palette.card} size={18} />
        </View>
        <Text style={[styles.bannerTitle, { color }]}>
          {t.level[forecast.risk_level]}
        </Text>
      </View>
      <RiskScale level={forecast.risk_level} previous={previous} />
      <Text style={[styles.bannerHint, { color }]}>
        {previous
          ? `${t.scaleShift[riskShift(previous, forecast.risk_level)]}. `
          : ""}
        {t.scaleHint[forecast.risk_level]}
      </Text>
      <Text style={[styles.bannerText, { color: palette.text }]}>
        {forecast.risk.explanation}
      </Text>
      {forecast.risk.shortfall_minor > 0 ? (
        <View style={[styles.shortfall, { backgroundColor: palette.card }]}>
          <Text style={[styles.shortfallText, { color: palette.muted }]}>
            {forecast.risk_level === "medium"
              ? t.shortfallPessimistic
              : t.shortfall}
          </Text>
          <Text style={[styles.shortfallValue, { color }]}>
            {formatRubApprox(forecast.risk.shortfall_minor)}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

/** Легенда графика: те же цвета и штрихи, что на самом графике. */
export function ChartLegend() {
  const palette = usePalette();
  return (
    <View style={styles.legend}>
      <View style={styles.legendItem}>
        <View
          style={[styles.legendLine, { backgroundColor: palette.accent }]}
        />
        <Text style={[styles.legendText, { color: palette.muted }]}>
          {t.legendBase}
        </Text>
      </View>
      <View style={styles.legendItem}>
        <View
          style={[styles.legendBand, { backgroundColor: palette.accentSoft }]}
        />
        <Text style={[styles.legendText, { color: palette.muted }]}>
          {t.legendRange}
        </Text>
      </View>
      <View style={styles.legendItem}>
        <View
          style={[styles.legendBand, { backgroundColor: palette.dangerSoft }]}
        />
        <Text style={[styles.legendText, { color: palette.muted }]}>
          {t.legendBelow}
        </Text>
      </View>
    </View>
  );
}

const DRIVER_ICON: Record<string, IconName> = {
  obligation: "calendar",
  daily_spending: "cart",
  income_after_risk: "clock",
};

export function ForecastScreen() {
  const { width } = useWindowDimensions();
  const desktop = width >= 960;
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
      setForecast(
        await api.createForecast(token, { reserve_minor: Number(reserve) }),
      );
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
    <Screen wide>
      <Card title={t.title} icon="shield">
        <Choice
          label={t.reserve}
          value={reserve}
          onChange={setReserve}
          options={RESERVES.map((value) => ({
            value,
            label: formatRub(Number(value)),
          }))}
        />
        <Muted>{t.reserveHint}</Muted>
      </Card>

      {error ? (
        <ErrorState
          title={t.error}
          message={error}
          onRetry={() => void load()}
        />
      ) : null}
      {loading && !forecast ? <LoadingState label={t.loading} /> : null}

      {forecast ? (
        <>
          <View style={{ flexDirection: desktop ? "row" : "column", gap: 24 }}>
            <Card
              title={t.chartTitle}
              icon="chart"
              style={{ flex: desktop ? 1.7 : undefined }}
            >
              <ForecastChart
                points={forecast.points}
                reserveMinor={forecast.reserve_minor}
              />
              <ChartLegend />
              <View style={styles.stats}>
                <Stat
                  label={`${t.minimum} · ${formatDay(forecast.risk.min_balance_date, year)}`}
                  value={formatRubApprox(forecast.risk.min_balance_minor)}
                  tone={
                    forecast.risk.min_balance_minor < forecast.reserve_minor
                      ? "danger"
                      : "default"
                  }
                />
                <Stat
                  label={t.pessimistic}
                  value={formatRubApprox(forecast.risk.pessimistic_min_minor)}
                  tone={
                    forecast.risk.pessimistic_min_minor < forecast.reserve_minor
                      ? "danger"
                      : "default"
                  }
                />
              </View>
            </Card>

            <View style={{ flex: desktop ? 1 : undefined, minWidth: 0 }}>
              <RiskBanner forecast={forecast} />
            </View>
          </View>

          {forecast.risk.drivers.length > 0 ? (
            <Card title={t.driversTitle} icon="sparkle">
              {forecast.risk.drivers.map((driver) => (
                <View
                  key={`${driver.kind}-${driver.code}-${driver.date ?? ""}`}
                  style={styles.line}
                >
                  <View
                    style={[styles.lineIcon, { borderColor: palette.border }]}
                  >
                    <Icon
                      name={DRIVER_ICON[driver.kind] ?? "chart"}
                      color={palette.text}
                      size={16}
                    />
                  </View>
                  <View style={styles.lineMain}>
                    <Text style={[styles.lineTitle, { color: palette.text }]}>
                      {driver.label}
                    </Text>
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

          <Card title={t.daysTitle} icon="calendar">
            {keyDays(
              forecast.points,
              forecast.risk_date,
              forecast.risk.min_balance_date,
            ).map((point) => (
              <View
                key={point.day}
                style={[
                  styles.line,
                  styles.dayRow,
                  point.below_reserve
                    ? { backgroundColor: palette.dangerSoft }
                    : null,
                ]}
              >
                <View
                  style={[
                    styles.dot,
                    {
                      backgroundColor: point.below_reserve
                        ? palette.danger
                        : palette.accent,
                    },
                  ]}
                />
                <View style={styles.lineMain}>
                  <Text
                    style={[
                      styles.lineTitle,
                      {
                        color: point.below_reserve
                          ? palette.danger
                          : palette.text,
                      },
                    ]}
                  >
                    {formatDay(point.day, year)}
                  </Text>
                  <Muted>
                    {point.outflow_minor > 0
                      ? `${t.payments} ${formatRub(-point.outflow_minor)} `
                      : ""}
                    {point.inflow_minor > 0
                      ? `${t.incomes} ${formatRub(point.inflow_minor)}`
                      : ""}
                  </Muted>
                </View>
                <View style={styles.values}>
                  <Text style={[styles.amount, { color: palette.text }]}>
                    {formatRubApprox(point.p50_minor)}
                  </Text>
                  <Muted>
                    {formatRubApprox(point.p10_minor)} …{" "}
                    {formatRubApprox(point.p90_minor)}
                  </Muted>
                </View>
              </View>
            ))}
          </Card>

          <Card title={t.qualityTitle} icon="check">
            {forecast.quality.notes.map((note) => (
              <Muted key={note}>• {note}</Muted>
            ))}
            <Muted>
              {t.model} {forecast.model_version} · {t.history}{" "}
              {forecast.quality.history_days} {t.days}
            </Muted>
            <Muted>{t.disclaimer}</Muted>
          </Card>

          <Button
            label={t.whatIf}
            icon="cart"
            onPress={() => router.push("/simulate")}
          />
          <Button
            label={t.refresh}
            variant="secondary"
            onPress={() => void load()}
            loading={loading}
          />
          <Button
            label={t.toCalendar}
            icon="calendar"
            variant="secondary"
            onPress={() => router.push("/calendar")}
          />
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  banner: { borderRadius: radius.lg, padding: space.lg + 4, gap: space.md },
  bannerHead: { flexDirection: "row", alignItems: "center", gap: space.md },
  bannerIcon: {
    width: 32,
    height: 32,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  bannerTitle: {
    fontSize: 20,
    fontWeight: "600",
    letterSpacing: -0.6,
    flexShrink: 1,
  },
  bannerHint: { fontSize: 14, fontWeight: "700", lineHeight: 20 },
  bannerText: { fontSize: 15, lineHeight: 23 },
  shortfall: {
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space.md,
  },
  shortfallText: { fontSize: 13, fontWeight: "600", flex: 1 },
  shortfallValue: {
    fontSize: 16,
    fontWeight: "600",
    fontVariant: ["tabular-nums"],
  },
  scale: {
    flexDirection: "row",
    gap: 4,
    padding: 3,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  scaleStep: {
    flex: 1,
    borderRadius: radius.pill,
    paddingVertical: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  scaleText: { fontSize: 13, fontWeight: "600" },
  scaleWas: { fontSize: 10, fontWeight: "700", marginTop: -1 },
  legend: { flexDirection: "row", gap: space.md, flexWrap: "wrap" },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  legendLine: { width: 16, height: 3, borderRadius: 2 },
  legendBand: { width: 14, height: 10, borderRadius: 3 },
  legendText: { fontSize: 12, fontWeight: "600" },
  stats: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  line: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: space.md,
  },
  dayRow: {
    borderRadius: radius.sm,
    paddingHorizontal: space.sm,
    paddingVertical: 6,
  },
  dot: { width: 8, height: 8, borderRadius: 4 },
  lineIcon: {
    width: 32,
    height: 32,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  lineMain: { flex: 1, gap: 2 },
  lineTitle: { fontSize: 15, fontWeight: "700" },
  values: { maxWidth: "48%", alignItems: "flex-end", gap: 2 },
  amount: { fontWeight: "500", fontSize: 14, fontVariant: ["tabular-nums"] },
});
