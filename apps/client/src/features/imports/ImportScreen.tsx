import { Redirect, useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";

import { api, ApiError, type Account, type ImportResult } from "@/shared/api/client";
import { formatMoment, formatRub } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
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
import { Text } from "@/shared/ui/text";

import { CSV_TEMPLATE } from "./template";

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "Неизвестная ошибка.";
}

export function ImportScreen() {
  const router = useRouter();
  const palette = usePalette();
  const { session } = useSession();
  const token = session?.access_token;
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [accountId, setAccountId] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [previewedContent, setPreviewedContent] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .listAccounts(token)
      .then((data) => {
        const liquid = data.items.filter((a) => a.type !== "deposit");
        setAccounts(liquid);
        setAccountId((current) => current ?? liquid[0]?.id ?? null);
      })
      .catch((err: unknown) => setError(messageOf(err)));
  }, [token]);

  const options = useMemo(
    () => (accounts ?? []).map((a) => ({ value: a.id, label: a.name })),
    [accounts],
  );

  if (!session || !token) {
    return <Redirect href="/" />;
  }

  const run = async (mode: "preview" | "import") => {
    if (!accountId || !content.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api.importCsv(token, {
        accountId,
        content,
        mode,
        idempotencyKey: mode === "import" ? `import-${preview?.fingerprint ?? ""}` : undefined,
      });
      if (mode === "preview") {
        setPreview(response);
        setPreviewedContent(content);
        setResult(null);
      } else {
        setResult(response);
      }
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  // После успешного импорта кнопка неактивна: повторное касание отправило бы тот же файл
  // ещё раз и показало бы «уже загружена» поверх результата.
  const canImport =
    preview !== null &&
    previewedContent === content &&
    preview.rows_total > preview.rows_rejected &&
    result === null;

  return (
    <Screen>
      <Card title={ru.imports.title} icon="upload">
        <Muted>{ru.imports.lead}</Muted>
        {accounts === null && !error ? <LoadingState label={ru.imports.loadingAccounts} /> : null}
        {accounts !== null ? (
          <Choice
            label={ru.imports.account}
            options={options}
            value={accountId}
            onChange={(value) => {
              setAccountId(value);
              setResult(null);
            }}
          />
        ) : null}
        <Field
          label={ru.imports.content}
          value={content}
          onChangeText={(value) => {
            setContent(value);
            setResult(null);
          }}
          placeholder={ru.imports.placeholder}
          hint={ru.imports.hint}
          multiline
          monospace
        />
        <View style={styles.row}>
          <Button
            label={ru.imports.useTemplate}
            variant="secondary"
            onPress={() => setContent(CSV_TEMPLATE)}
          />
          <Button
            label={ru.imports.check}
            onPress={() => void run("preview")}
            loading={busy && !canImport}
            disabled={!accountId || !content.trim()}
          />
        </View>
      </Card>

      {error ? <ErrorState title={ru.imports.error} message={error} /> : null}

      {preview && previewedContent === content ? (
        <Card title={ru.imports.previewTitle} icon="check">
          <Muted>
            {ru.imports.rows}: {preview.rows_total} · {ru.imports.rejected}: {preview.rows_rejected}
            {preview.period_from && preview.period_to
              ? ` · ${preview.period_from} — ${preview.period_to}`
              : ""}
          </Muted>
          <Muted>
            {ru.imports.mapping}:{" "}
            {Object.entries(preview.column_mapping)
              .map(([field, header]) => `${header} → ${field}`)
              .join(", ")}
          </Muted>
          {preview.preview.map((row) => (
            <View key={row.row} style={styles.line}>
              <View style={styles.lineMain}>
                <Text style={{ color: palette.text }}>{row.description || row.category || "—"}</Text>
                <Muted>
                  {row.occurred_at ? formatMoment(row.occurred_at) : ""} ·{" "}
                  {ru.txType[row.type as keyof typeof ru.txType] ?? row.type}
                  {row.status !== "posted"
                    ? ` · ${ru.txStatus[row.status as keyof typeof ru.txStatus] ?? row.status}`
                    : ""}
                </Muted>
              </View>
              <Text style={[styles.amount, { color: palette.text }]}>
                {formatRub(Number(row.amount_minor))}
              </Text>
            </View>
          ))}
          {preview.issues.map((issue) => (
            <Text key={`${issue.row}-${issue.code}`} style={{ color: palette.danger }}>
              {ru.imports.row} {issue.row}: {issue.message}
            </Text>
          ))}
          <Button
            label={ru.imports.import}
            onPress={() => void run("import")}
            loading={busy && canImport}
            disabled={!canImport}
          />
        </Card>
      ) : null}

      {result ? (
        <Card title={result.already_imported ? ru.imports.alreadyTitle : ru.imports.doneTitle} icon="check">
          {result.already_imported ? (
            // Сервер вернул итог прошлой загрузки этого же файла: новых операций нет.
            <Muted>
              {ru.imports.alreadyLead} {result.rows_imported}.
            </Muted>
          ) : (
            <Muted>
              {ru.imports.imported}: {result.rows_imported} · {ru.imports.duplicates}:{" "}
              {result.rows_duplicate} · {ru.imports.rejected}: {result.rows_rejected}
            </Muted>
          )}
          <Button label={ru.imports.toDashboard} onPress={() => router.replace("/dashboard")} />
        </Card>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: space.md, flexWrap: "wrap" },
  line: { flexDirection: "row", justifyContent: "space-between", gap: space.md },
  lineMain: { flex: 1, gap: 2 },
  amount: { fontWeight: "600" },
});
