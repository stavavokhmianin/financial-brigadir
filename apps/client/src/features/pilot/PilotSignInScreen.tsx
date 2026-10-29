import { useRouter } from "expo-router";
import { useState, type ReactNode } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { api, ApiError } from "@/shared/api/client";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import { Logo } from "@/shared/ui/brand";
import { Button, Card, ErrorState, Field, Hero, Muted, Screen } from "@/shared/ui/components";
import { space, usePalette } from "@/shared/ui/theme";
import { Text } from "@/shared/ui/text";

import { canSubmit } from "./logic";

const t = ru.pilot;

export function PilotSignInScreen({
  termsVersion,
  notice,
}: {
  termsVersion: string;
  notice?: ReactNode;
}) {
  const router = useRouter();
  const palette = usePalette();
  const { setSession } = useSession();
  const [code, setCode] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const session = await api.createPilotSession({
        access_code: code,
        accepted_terms_version: termsVersion,
      });
      setSession(session);
      router.replace("/dashboard");
      // Новый профиль пуст: сразу предлагаем добавить счёт, «назад» ведёт на главную.
      if (session.first_sign_in) router.push("/add");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.unknownError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen topInset>
      {notice}
      <Hero>
        <View style={styles.brandRow}>
          <Logo onHero />
          <Text style={[styles.brandName, { color: palette.heroText }]}>{ru.appName}</Text>
        </View>
        <Text accessibilityRole="header" style={[styles.title, { color: palette.heroText }]}>
          {ru.demo.title}
        </Text>
        <Text style={[styles.lead, { color: palette.heroMuted }]}>{t.lead}</Text>
      </Hero>
      <Card title={t.termsTitle} icon="shield">
        {t.terms.map((line) => (
          <Muted key={line}>• {line}</Muted>
        ))}
        <Muted>
          {t.termsVersion} {termsVersion}
        </Muted>
        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: accepted }}
          onPress={() => setAccepted(!accepted)}
          style={styles.check}
        >
          <View
            style={[
              styles.box,
              { borderColor: palette.accent, backgroundColor: accepted ? palette.accent : "transparent" },
            ]}
          >
            {accepted ? <Text style={{ color: palette.accentText }}>✓</Text> : null}
          </View>
          <Text style={[styles.checkText, { color: palette.text }]}>{t.accept}</Text>
        </Pressable>
      </Card>
      <Card title={t.codeTitle} icon="user">
        <Field
          label={t.codeLabel}
          testID="pilot-code"
          value={code}
          onChangeText={setCode}
          placeholder="ABCD-EFGH-JKMN-PQRS"
        />
        <Muted>{t.codeHint}</Muted>
        <Button
          testID="pilot-sign-in"
          label={t.signIn}
          onPress={() => void submit()}
          loading={busy}
          disabled={!canSubmit(code, accepted)}
        />
      </Card>
      {error ? <ErrorState title={t.errorTitle} message={error} /> : null}
      <Muted>{ru.demo.disclaimer}</Muted>
    </Screen>
  );
}

const styles = StyleSheet.create({
  brandRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  brandName: { fontSize: 17, fontWeight: "800" },
  title: { fontSize: 30, fontWeight: "800", lineHeight: 36, letterSpacing: -0.8 },
  lead: { fontSize: 15, lineHeight: 22 },
  check: { flexDirection: "row", alignItems: "center", gap: space.sm, paddingVertical: space.xs },
  box: {
    width: 24,
    height: 24,
    borderWidth: 2,
    borderRadius: 6,
    alignItems: "center",
    justifyContent: "center",
  },
  checkText: { flex: 1, fontSize: 15 },
});
