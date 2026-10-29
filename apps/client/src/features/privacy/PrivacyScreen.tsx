import { Redirect, useRouter } from "expo-router";
import { useState } from "react";
import { Platform, Share, View } from "react-native";

import { api, ApiError } from "@/shared/api/client";
import { useSession } from "@/shared/session";
import { Button, Card, Field, Muted, Screen } from "@/shared/ui/components";

export function PrivacyScreen() {
  const { session, setSession } = useSession();
  const router = useRouter();
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  if (!session) return <Redirect href="/" />;
  const token = session.access_token;

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try { await action(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось выполнить запрос."); }
    finally { setBusy(false); }
  }

  async function exportData() {
    const data = JSON.stringify(await api.exportProfile(token), null, 2);
    if (Platform.OS === "web") {
      const url = URL.createObjectURL(new Blob([data], { type: "application/json" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "brigadir-profile.json";
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } else {
      await Share.share({ title: "Мои данные — Финансовый бригадир", message: data });
    }
    setMessage("Экспорт подготовлен. Он содержит ваши финансовые данные — выбирайте место сохранения внимательно.");
  }

  async function finish(remove: boolean) {
    if (remove) await api.deleteProfile(token);
    else {
      try { await api.logout(token); }
      catch (error) {
        // An expired/revoked session is already inactive on the server.
        if (!(error instanceof ApiError) || error.status !== 401) throw error;
      }
    }
    setSession(null);
    router.dismissAll();
    router.replace("/");
  }

  return <Screen>
    <Card title="Приватность и данные" icon="shield">
      <Muted>На сервере хранятся счета, нормализованные операции, обязательства, прогнозы и журнал действий. Исходный CSV не сохраняется приложением. Сторонним ИИ-сервисам данные не отправляются.</Muted>
      <Muted>{session.user.is_demo ? "Токен сессии хранится только в памяти приложения. После выхода или перезапуска восстановить доступ к этому демо-профилю нельзя. Сначала экспортируйте нужные данные или удалите профиль." : "Токен сессии хранится только в памяти приложения. После выхода войдите снова по своему коду участника. После удаления профиля код перестанет действовать."}</Muted>
      <Muted>Удаление сразу очищает рабочую базу, расчёты и все сессии. Срок удаления резервных копий зависит от оператора стенда; перед загрузкой реальной выписки уточните его политику хранения.</Muted>
      <Button label="Экспортировать мои данные" disabled={busy} onPress={() => void run(exportData)} />
    </Card>
    <Card title="Удалить профиль" icon="alert">
      <Muted>Будут удалены все данные текущего профиля, включая историю, импорт, прогнозы и предупреждения. Отменить действие нельзя. Для подтверждения введите УДАЛИТЬ.</Muted>
      <Field label="Подтверждение удаления" value={confirmation} onChangeText={setConfirmation} />
      <Button label="Удалить все мои данные" disabled={busy || confirmation !== "УДАЛИТЬ"} onPress={() => void run(() => finish(true))} />
    </Card>
    <Button label="Выйти и отозвать сессии" variant="secondary" disabled={busy} onPress={() => void run(() => finish(false))} />
    {message ? <View accessibilityRole="alert"><Muted>{message}</Muted></View> : null}
  </Screen>;
}
