import { Redirect } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";

import { api, ApiError, type DuplicatePair } from "@/shared/api/client";
import { formatMoment, formatRub } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import { Button, Card, ErrorState, LoadingState, Muted, Screen } from "@/shared/ui/components";
import { space, usePalette } from "@/shared/ui/theme";
import { Text } from "@/shared/ui/text";

const t = ru.duplicates;

export function DuplicatesScreen() {
  const palette = usePalette();
  const { session } = useSession();
  const token = session?.access_token;
  const [pairs, setPairs] = useState<DuplicatePair[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setPairs((await api.listDuplicates(token)).items);
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

  const decide = async (id: string, decision: "duplicate" | "not_duplicate") => {
    setBusy(id);
    try {
      await api.resolveDuplicate(token, id, decision);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Неизвестная ошибка.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Screen>
      <Card title={t.title} icon="alert">
        <Muted>{t.lead}</Muted>
      </Card>
      {error ? <ErrorState title={t.error} message={error} onRetry={() => void load()} /> : null}
      {pairs === null && !error ? <LoadingState label={t.loading} /> : null}
      {pairs?.length === 0 ? <Muted>{t.empty}</Muted> : null}
      {pairs?.map((pair) => (
        <Card key={pair.transaction.id}>
          <Text style={[styles.title, { color: palette.text }]}>
            {pair.transaction.description || pair.transaction.category || "—"} ·{" "}
            {formatRub(pair.transaction.amount_minor)}
          </Text>
          <Muted>{t.reason[pair.reason]}</Muted>
          {[pair.original, pair.transaction].map((tx, index) => (
            <View key={tx.id} style={styles.row}>
              <Muted>{index === 0 ? t.first : t.second}</Muted>
              <Muted>
                {formatMoment(tx.occurred_at)}
                {tx.booked_at ? ` · ${t.booked} ${formatMoment(tx.booked_at)}` : ""}
              </Muted>
            </View>
          ))}
          <View style={styles.actions}>
            <Button
              label={t.isDuplicate}
              size="sm"
              onPress={() => void decide(pair.transaction.id, "duplicate")}
              loading={busy === pair.transaction.id}
            />
            <Button
              label={t.notDuplicate}
              size="sm"
              variant="secondary"
              onPress={() => void decide(pair.transaction.id, "not_duplicate")}
              disabled={busy === pair.transaction.id}
            />
          </View>
        </Card>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: 16, fontWeight: "600", letterSpacing: -0.32 },
  row: { gap: 2 },
  actions: { flexDirection: "row", gap: space.sm, flexWrap: "wrap", paddingTop: space.xs },
});
