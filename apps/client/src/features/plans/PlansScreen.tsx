import { Redirect, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { StyleSheet, View, useWindowDimensions } from "react-native";

import { api, type Schemas } from "@/shared/api/client";
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
import { space, usePalette } from "@/shared/ui/theme";

type PlanSpec = Schemas["PlansOut"]["plans"][number];

function features(plan: PlanSpec): string[] {
  return [
    `${plan.max_new_accounts === null ? "Несколько счетов" : "Один счёт"}. Прогноз до ${plan.max_horizon_days} дней.`,
    plan.advanced_scenarios
      ? "Покупки, задержка дохода и комбинации сценариев."
      : "Базовый прогноз и проверка одной покупки.",
    "Ручные обязательства, доходы, уведомления, экспорт и удаление доступны в обоих режимах.",
  ];
}

export function PlansScreen() {
  const palette = usePalette();
  const { width } = useWindowDimensions();
  const { session, setSession } = useSession();
  const token = session?.access_token;
  const [plans, setPlans] = useState<Schemas["PlansOut"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    setError(null);
    try {
      setPlans(await api.getPlans(token));
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось загрузить тарифы.",
      );
    }
  }, [token]);
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );
  if (!session || !token) return <Redirect href="/" />;

  async function preview(plan: "free" | "plus") {
    if (!session || !token) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.previewDemoPlan(token, plan);
      setPlans(result);
      setSession({
        ...session,
        user: { ...session.user, plan: result.current_plan },
      });
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Не удалось сменить режим.",
      );
    } finally {
      setBusy(false);
    }
  }

  const renderPlan = (plan: PlanSpec) => {
    const plus = plan.plan === "plus";
    const name = plus ? "Plus" : "Free";
    const current = plans?.current_plan === plan.plan;
    const textColor = plus ? palette.heroText : palette.text;
    const checkColor = plus ? palette.heroText : palette.ok;
    const body = (
      <>
        <View style={styles.planHead}>
          <Text
            accessibilityRole="header"
            style={[styles.planName, { color: textColor }]}
          >
            {name}
          </Text>
          {current ? (
            <View>
              <Badge label="сейчас" tone={plus ? "hero" : "ok"} />
            </View>
          ) : null}
        </View>
        <Text
          style={[
            styles.price,
            { color: plus ? palette.heroMuted : palette.muted },
          ]}
        >
          {plus ? "в демо — бесплатно" : "0 ₽"}
        </Text>
        {features(plan).map((line) => (
          <View key={line} style={styles.feature}>
            <Icon name="check" color={checkColor} size={18} />
            <Text
              style={[
                styles.featureText,
                { color: plus ? palette.heroText : palette.text },
              ]}
            >
              {line}
            </Text>
          </View>
        ))}
        {plans?.demo_preview ? (
          <Button
            label={`Проверить ${name} в демо`}
            variant={plus ? "inverse" : "primary"}
            disabled={busy || current}
            onPress={() => void preview(plan.plan)}
          />
        ) : null}
      </>
    );
    return plus ? (
      <Hero key={plan.plan} style={{ flex: width >= 800 ? 1 : undefined }}>
        {body}
      </Hero>
    ) : (
      <Card key={plan.plan} style={{ flex: width >= 800 ? 1 : undefined }}>
        {body}
      </Card>
    );
  };

  return (
    <Screen wide>
      {error ? (
        <ErrorState
          title="Тарифы"
          message={error}
          onRetry={() => void load()}
        />
      ) : null}
      {!plans && !error ? (
        <LoadingState label="Загружаем возможности…" />
      ) : null}
      {plans ? (
        <>
          <Card title="Текущие возможности" icon="crown">
            <Badge
              label={`${plans.demo_preview ? "Демо: " : "Тариф: "}${plans.current_plan === "free" ? "Free" : "Plus"}`}
              tone="ok"
            />
            <Muted>
              Оплата не подключена. В демо можно проверить оба режима бесплатно;
              никаких списаний или подписки не возникает.
            </Muted>
            {plans.existing_accounts_over_limit ? (
              <Muted>
                Счетов больше лимита Free. Все они сохранены и участвуют в
                базовом прогнозе. Добавление новых счетов доступно в Plus.
              </Muted>
            ) : null}
          </Card>
          <View
            style={{ flexDirection: width >= 800 ? "row" : "column", gap: 24 }}
          >
            {plans.plans.map(renderPlan)}
          </View>
          <Muted>
            При переключении режима история, счета и сохранённые расчёты
            остаются. Family появится после MVP.
          </Muted>
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  planHead: { flexDirection: "row", alignItems: "center", gap: space.sm },
  planName: { fontSize: 28, fontWeight: "600", letterSpacing: -1.1 },
  price: { fontSize: 14, fontWeight: "500", marginTop: -space.sm },
  feature: { flexDirection: "row", gap: space.sm, alignItems: "flex-start" },
  featureText: { flex: 1, fontSize: 14, lineHeight: 21 },
});
