import { Redirect } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";

import {
  api,
  ApiError,
  type AlertItem,
  type AlertAnalytics,
  type NotificationSettings,
} from "@/shared/api/client";
import { formatDay, formatMoment } from "@/shared/format";
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
import { Text } from "@/shared/ui/text";

import { groupHidden, QUIET_PRESETS, quietPresetOf, timesLabel, type QuietPreset } from "./logic";

const t = ru.alerts;
type Mode = "quiet" | "smart" | "active";
type Limit = "0" | "1" | "2" | "3";

interface State {
  items: AlertItem[];
  settings: NotificationSettings;
  analytics: AlertAnalytics;
}

export function AlertsScreen() {
  const palette = usePalette();
  const { session } = useSession();
  const token = session?.access_token;
  const [state, setState] = useState<State | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [alerts, settings, analytics] = await Promise.all([
        api.listAlerts(token),
        api.getNotificationSettings(token),
        api.getAlertAnalytics(token),
      ]);
      setState({ items: alerts.items, settings, analytics });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!session || !token) {
    return <Redirect href="/" />;
  }

  const feedback = async (id: string, value: "useful" | "not_relevant" | "disable_type") => {
    try {
      await api.sendAlertFeedback(token, id, value);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    }
  };

  const updateSettings = async (patch: Parameters<typeof api.updateNotificationSettings>[1]) => {
    try {
      await api.updateNotificationSettings(token, patch);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    }
  };

  if (error) {
    return (
      <Screen>
        <ErrorState title={t.error} message={error} onRetry={() => void load()} />
      </Screen>
    );
  }
  if (!state) {
    return (
      <Screen>
        <LoadingState label={t.loading} />
      </Screen>
    );
  }

  const shown = state.items.filter((a) => a.action === "send");
  const hidden = state.items.filter((a) => a.action !== "send");
  const settings = state.settings;
  const quiet = quietPresetOf(settings.quiet_hours_start ?? null, settings.quiet_hours_end ?? null);

  return (
    <Screen>
      <Card title={t.title} icon="bell">
        <Muted>{t.lead}</Muted>
        {shown.length === 0 ? <Muted>{t.empty}</Muted> : null}
        {shown.map((alert) => (
          <View key={alert.id} style={[styles.alert, { borderColor: palette.warning }]}>
            <View style={styles.row}>
              <Badge
                label={alert.priority === "critical" ? t.critical : t.normal}
                tone="warning"
              />
              <Muted>{formatMoment(alert.created_at)}</Muted>
            </View>
            <Text style={[styles.message, { color: palette.text }]}>{alert.message}</Text>
            {alert.feedback ? (
              <Muted>
                {t.thanks}: {t.feedback[alert.feedback as keyof typeof t.feedback]}
              </Muted>
            ) : (
              <View style={styles.row}>
                <Button label={t.feedback.useful} onPress={() => void feedback(alert.id, "useful")} />
                <Button
                  label={t.feedback.not_relevant}
                  variant="secondary"
                  onPress={() => void feedback(alert.id, "not_relevant")}
                />
                <Button
                  label={t.feedback.disable_type}
                  variant="secondary"
                  onPress={() => void feedback(alert.id, "disable_type")}
                />
              </View>
            )}
          </View>
        ))}
      </Card>

      {hidden.length > 0 ? (
        <Card title={t.hiddenTitle} icon="shield">
          <Muted>{t.hiddenLead}</Muted>
          {groupHidden(hidden)
            .slice(0, 10)
            .map(({ first: alert, count }) => (
              <View key={alert.id} style={styles.hidden}>
                <Text style={{ color: palette.text }}>
                  {alert.action === "defer" ? t.deferred : t.suppressed}
                  {count > 1 ? ` ${timesLabel(count)}` : ""}
                  {alert.risk_date ? ` · ${t.riskOn} ${formatDay(alert.risk_date)}` : ""}
                </Text>
                <Muted>{alert.reason_text}</Muted>
              </View>
            ))}
        </Card>
      ) : null}

      <Card title={t.settingsTitle} icon="sparkle">
        <Choice<Mode>
          label={t.mode}
          value={settings.mode as Mode}
          onChange={(mode) => void updateSettings({ mode })}
          options={[
            { value: "quiet", label: t.modes.quiet },
            { value: "smart", label: t.modes.smart },
            { value: "active", label: t.modes.active },
          ]}
        />
        <Muted>{t.modeHint[settings.mode as Mode]}</Muted>
        <Choice<QuietPreset>
          label={t.quietHours}
          value={quiet}
          onChange={(preset) => {
            const [start, end] = QUIET_PRESETS[preset];
            void updateSettings({ quiet_hours_start: start, quiet_hours_end: end });
          }}
          options={[
            { value: "off", label: t.quiet.off },
            { value: "night", label: t.quiet.night },
            { value: "late", label: t.quiet.late },
          ]}
        />
        <Choice<Limit>
          label={t.limit}
          value={String(Math.min(settings.max_noncritical_per_week, 3)) as Limit}
          onChange={(value) => void updateSettings({ max_noncritical_per_week: Number(value) })}
          options={(["0", "1", "2", "3"] as const).map((value) => ({ value, label: value }))}
        />
        <Muted>{t.limitHint}</Muted>
      </Card>

      <Card title={t.statsTitle} icon="chart">
        <Muted>
          {t.stats.decisions}: {state.analytics.total_decisions} · {t.stats.sent7}:{" "}
          {state.analytics.sent_last_7_days} · {t.stats.suppressed}:{" "}
          {state.analytics.by_action.suppress ?? 0}
        </Muted>
        <Muted>{t.inAppOnly}</Muted>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  alert: { borderLeftWidth: 3, paddingLeft: space.md, gap: space.sm },
  row: { flexDirection: "row", gap: space.sm, alignItems: "center", flexWrap: "wrap" },
  message: { fontSize: 15, lineHeight: 22 },
  hidden: { gap: 2 },
});
