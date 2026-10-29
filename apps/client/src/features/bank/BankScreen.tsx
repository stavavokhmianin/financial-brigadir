import { Redirect } from "expo-router";
import { useEffect, useState } from "react";

import { api, type Schemas } from "@/shared/api/client";
import { formatMoment } from "@/shared/format";
import { useSession } from "@/shared/session";
import { Badge, Button, Card, Choice, Muted, Screen } from "@/shared/ui/components";

type Scenario = NonNullable<Schemas["BankMockSyncRequest"]["scenario"]>;
const scenarios: { value: Scenario; label: string }[] = [
  { value: "ok", label: "Обычная загрузка" },
  { value: "duplicates", label: "Повторные операции" },
  { value: "partial", label: "Часть истории" },
  { value: "network_error", label: "Сбой связи" },
  { value: "delayed", label: "Ответ с задержкой" },
  { value: "consent_expired", label: "Истечение согласия" },
];

export function BankScreen() {
  const { session } = useSession();
  const [consent, setConsent] = useState<Schemas["BankConsentOut"] | null>(null);
  const [scenario, setScenario] = useState<Scenario>("ok");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [message, setMessage] = useState("");
  const token = session?.access_token;
  useEffect(() => {
    let current = true;
    if (token) api.bankConsent(token).then(value => { if (current) { setConsent(value); setReady(true); } })
      .catch(error => { if (current) setMessage(error instanceof Error ? error.message : "Ошибка загрузки"); });
    return () => { current = false; };
  }, [token]);
  if (!session || !token) return <Redirect href="/" />;
  const accessToken = token;
  const active = consent && !consent.revoked_at && new Date(consent.expires_at).getTime() > Date.now();

  async function run(action: "grant" | "revoke" | "sync") {
    setBusy(true);
    setMessage("");
    try {
      if (action === "grant") setConsent(await api.grantBankConsent(accessToken));
      else if (action === "revoke") {
        await api.revokeBankConsent(accessToken);
        setConsent(await api.bankConsent(accessToken));
        setMessage("Доступ отозван. Новые синхронизации запрещены. Загруженную историю можно удалить вместе с профилем в разделе приватности.");
      } else {
        const result = await api.syncBank(accessToken, scenario);
        setMessage(`${result.message} Новых операций: ${result.transactions_new}; повторов пропущено: ${result.transactions_duplicate}. Данные на ${formatMoment(result.data_as_of)}.${result.status === "partial" ? " История неполная — это отмечено в прогнозе." : ""}`);
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось выполнить запрос."); }
    finally { setBusy(false); }
  }

  return <Screen>
    <Card title="Учебный банк" icon="bank">
      <Badge label="Только синтетика, без подключения к банкам" tone="warning" />
      <Muted>Можно проверить загрузку счетов, остатков и операций. Будет добавлен отдельный учебный счёт, который участвует в прогнозе. Пароли и коды банка не нужны.</Muted>
      <Muted>Нажатие «Разрешить» даёт доступ только к синтетическим счетам, остаткам и операциям на 24 часа. Отзыв остановит новые загрузки; уже загруженная история останется до удаления профиля.</Muted>
      {consent ? <Muted>Согласие: {active ? "действует" : "не действует"}. Срок: {formatMoment(consent.expires_at)}.</Muted> : null}
      <Button label="Разрешить чтение синтетики на 24 часа" disabled={busy || !ready} onPress={() => void run("grant")} />
      {active ? <Button label="Отозвать доступ" variant="secondary" disabled={busy} onPress={() => void run("revoke")} /> : null}
    </Card>
    <Card title="Проверка загрузки" icon="upload">
      <Choice options={scenarios} value={scenario} onChange={setScenario} />
      <Muted>После сбоя выберите обычную загрузку и повторите. Старый ответ не заменяет свежие данные. Для проверки задержанного обновления начните с нового демо-профиля.</Muted>
      <Button label="Синхронизировать учебный счёт" disabled={busy || !active} onPress={() => void run("sync")} />
      {message ? <Muted>{message}</Muted> : null}
    </Card>
  </Screen>;
}
