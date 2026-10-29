import { useState } from "react";

import { apiUrl, setApiUrl } from "@/shared/config";
import { ru } from "@/shared/i18n/ru";
import { normalizeServerUrl, pointsToDevice } from "@/shared/server";
import { Button, Card, Field, Muted } from "@/shared/ui/components";

const t = ru.server;

/** Смена адреса API, когда сервер недоступен: APK на телефоне, API на ноутбуке. */
export function ServerCard({ onConnect }: { onConnect: () => void }) {
  const [value, setValue] = useState(apiUrl());
  const [error, setError] = useState<string | null>(null);

  const connect = () => {
    const url = normalizeServerUrl(value);
    if (!url) {
      setError(t.invalid);
      return;
    }
    setError(null);
    setValue(url);
    setApiUrl(url);
    onConnect();
  };

  return (
    <Card title={t.title} icon="wallet">
      <Muted>{t.lead}</Muted>
      {pointsToDevice(apiUrl()) ? <Muted>{t.deviceHint}</Muted> : null}
      <Field
        label={t.label}
        testID="server-url"
        value={value}
        onChangeText={setValue}
        placeholder="http://192.168.1.5:8000"
        keyboardType="url"
        error={error}
        hint={t.hint}
      />
      <Button testID="server-connect" label={t.connect} onPress={connect} />
    </Card>
  );
}
