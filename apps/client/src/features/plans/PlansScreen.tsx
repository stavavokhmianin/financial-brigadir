import { Redirect, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";

import { api, type Schemas } from "@/shared/api/client";
import { useSession } from "@/shared/session";
import { Badge, Button, Card, ErrorState, LoadingState, Muted, Screen } from "@/shared/ui/components";

export function PlansScreen() {
  const { session, setSession } = useSession();
  const token = session?.access_token;
  const [plans, setPlans] = useState<Schemas["PlansOut"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    setError(null);
    try { setPlans(await api.getPlans(token)); }
    catch (error) { setError(error instanceof Error ? error.message : "Не удалось загрузить тарифы."); }
  }, [token]);
  useFocusEffect(useCallback(() => { void load(); }, [load]));
  if (!session || !token) return <Redirect href="/" />;

  async function preview(plan: "free" | "plus") {
    if (!session || !token) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.previewDemoPlan(token, plan);
      setPlans(result);
      setSession({ ...session, user: { ...session.user, plan: result.current_plan } });
    } catch (error) { setError(error instanceof Error ? error.message : "Не удалось сменить режим."); }
    finally { setBusy(false); }
  }

  return <Screen>
    {error ? <ErrorState title="Тарифы" message={error} onRetry={() => void load()} /> : null}
    {!plans && !error ? <LoadingState label="Загружаем возможности…" /> : null}
    {plans ? <>
      <Card title="Текущие возможности">
        <Badge label={`${plans.demo_preview ? "Демо: " : "Тариф: "}${plans.current_plan === "free" ? "Free" : "Plus"}`} />
        <Muted>Оплата не подключена. В демо можно проверить оба режима бесплатно; никаких списаний или подписки не возникает.</Muted>
        {plans.existing_accounts_over_limit ? <Muted>Счетов больше лимита Free. Все они сохранены и участвуют в базовом прогнозе. Добавление новых счетов доступно в Plus.</Muted> : null}
      </Card>
      {plans.plans.map(plan => <Card key={plan.plan} title={plan.plan === "free" ? "Free" : "Plus"}>
        <Muted>{plan.max_new_accounts === null ? "Несколько счетов" : "Один счёт"}. Прогноз до {plan.max_horizon_days} дней.</Muted>
        <Muted>{plan.advanced_scenarios ? "Покупки, задержка дохода и комбинации сценариев." : "Базовый прогноз и проверка одной покупки."}</Muted>
        <Muted>Ручные обязательства, доходы, уведомления, экспорт и удаление доступны в обоих режимах.</Muted>
        {plans.demo_preview ? <Button label={`Проверить ${plan.plan === "free" ? "Free" : "Plus"} в демо`} disabled={busy || plans.current_plan === plan.plan} onPress={() => void preview(plan.plan)} /> : null}
      </Card>)}
      <Muted>При переключении режима история, счета и сохранённые расчёты остаются. Family появится после MVP.</Muted>
    </> : null}
  </Screen>;
}
