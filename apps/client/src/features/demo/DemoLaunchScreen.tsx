import { useRouter } from "expo-router";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { api, ApiError, type DemoProfile } from "@/shared/api/client";
import { DEMO_SEED } from "@/shared/config";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  LoadingState,
  Muted,
  Screen,
} from "@/shared/ui/components";
import { space, usePalette } from "@/shared/ui/theme";

const DEFAULT_PROFILE = "young_specialist";

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "Неизвестная ошибка.";
}

export function DemoLaunchScreen({ notice }: { notice?: ReactNode }) {
  const router = useRouter();
  const palette = usePalette();
  const { setSession } = useSession();
  const [profiles, setProfiles] = useState<DemoProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState(DEFAULT_PROFILE);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    setProfiles(null);
    try {
      setProfiles(await api.listDemoProfiles());
    } catch (error) {
      setLoadError(messageOf(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const start = async () => {
    setStarting(true);
    setStartError(null);
    try {
      const session = await api.createDemoSession({ profile_id: selected, seed: DEMO_SEED });
      setSession(session);
      router.replace("/dashboard");
    } catch (error) {
      setStartError(messageOf(error));
    } finally {
      setStarting(false);
    }
  };

  return (
    <Screen>
      {notice}
      <View style={styles.hero}>
        <Text accessibilityRole="header" style={[styles.title, { color: palette.text }]}>
          {ru.demo.title}
        </Text>
        <Muted>{ru.demo.lead}</Muted>
      </View>

      <Card title={ru.demo.profilesTitle}>
        {loadError ? (
          <ErrorState
            title={ru.demo.loadError}
            message={loadError}
            hint={ru.demo.serverHint}
            onRetry={() => void load()}
          />
        ) : profiles === null ? (
          <LoadingState label={ru.demo.loading} />
        ) : profiles.length === 0 ? (
          <Muted>{ru.demo.empty}</Muted>
        ) : (
          <View accessibilityRole="radiogroup" style={styles.list}>
            {profiles.map((profile) => {
              const active = profile.id === selected;
              return (
                <Pressable
                  key={profile.id}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: active, disabled: !profile.mvp }}
                  disabled={!profile.mvp || starting}
                  onPress={() => setSelected(profile.id)}
                  style={[
                    styles.option,
                    {
                      borderColor: active ? palette.accent : palette.border,
                      backgroundColor: palette.card,
                      opacity: profile.mvp ? 1 : 0.55,
                    },
                  ]}
                >
                  <View style={styles.optionHeader}>
                    <Text style={[styles.optionTitle, { color: palette.text }]}>
                      {profile.title}
                    </Text>
                    {active ? <Badge label={ru.demo.selected} tone="ok" /> : null}
                    {!profile.mvp ? <Badge label={ru.demo.afterMvp} /> : null}
                  </View>
                  <Muted>{profile.description}</Muted>
                </Pressable>
              );
            })}
          </View>
        )}
      </Card>

      {startError ? (
        <ErrorState title={ru.demo.loadError} message={startError} hint={ru.demo.serverHint} />
      ) : null}

      <Button
        label={starting ? ru.demo.starting : ru.demo.start}
        onPress={() => void start()}
        loading={starting}
        disabled={profiles === null || profiles.length === 0}
      />
      <Muted>{ru.demo.disclaimer}</Muted>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { gap: space.sm, paddingTop: space.md },
  title: { fontSize: 26, fontWeight: "700", lineHeight: 32 },
  list: { gap: space.md },
  option: { borderWidth: 1.5, borderRadius: 12, padding: space.md, gap: space.xs },
  optionHeader: { flexDirection: "row", alignItems: "center", gap: space.sm, flexWrap: "wrap" },
  optionTitle: { fontSize: 16, fontWeight: "600" },
});
