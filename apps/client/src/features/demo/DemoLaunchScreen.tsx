import { useRouter } from "expo-router";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { api, ApiError, type DemoProfile } from "@/shared/api/client";
import { DEMO_SEED } from "@/shared/config";
import { ru } from "@/shared/i18n/ru";
import { useSession } from "@/shared/session";
import { Logo } from "@/shared/ui/brand";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Hero,
  LoadingState,
  Muted,
  Screen,
  type PressState,
} from "@/shared/ui/components";
import { Icon, type IconName } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { radius, space, usePalette } from "@/shared/ui/theme";

const DEFAULT_PROFILE = "young_specialist";

const PROFILE_ICON: Record<string, IconName> = {
  young_specialist: "user",
  credit_card: "wallet",
  freelancer: "sparkle",
  two_banks: "bank",
  family: "user",
};

const FEATURES: { icon: IconName; label: string }[] = [
  { icon: "chart", label: ru.demo.featureForecast },
  { icon: "cart", label: ru.demo.featureBefore },
  { icon: "shield", label: ru.demo.featureNoPasswords },
];

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
  const [startingLive, setStartingLive] = useState(false);
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

  // Основной вход (ADR-0007): учебный аккаунт без выбора персонажа.
  const startLive = async () => {
    setStartingLive(true);
    setStartError(null);
    try {
      setSession(await api.createLiveSession());
      router.replace("/dashboard");
    } catch (error) {
      setStartError(messageOf(error));
    } finally {
      setStartingLive(false);
    }
  };

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
        <Text style={[styles.lead, { color: palette.heroMuted }]}>{ru.demo.lead}</Text>
        <View style={styles.features}>
          {FEATURES.map((feature) => (
            <View key={feature.label} style={[styles.feature, { backgroundColor: palette.heroChip }]}>
              <Icon name={feature.icon} color={palette.heroText} size={16} />
              <Text style={[styles.featureText, { color: palette.heroText }]}>{feature.label}</Text>
            </View>
          ))}
        </View>
        <Button
          variant="inverse"
          trailingIcon="arrow"
          label={startingLive ? ru.live.starting : ru.live.start}
          onPress={() => void startLive()}
          loading={startingLive}
          disabled={starting}
        />
      </Hero>

      {startError ? (
        <ErrorState title={ru.demo.loadError} message={startError} hint={ru.demo.serverHint} />
      ) : null}

      <Card title={ru.demo.profilesTitle}>
        <Muted>{ru.demo.profilesLead}</Muted>
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
                  disabled={!profile.mvp || starting || startingLive}
                  onPress={() => setSelected(profile.id)}
                  style={({ hovered }: PressState) => [
                    styles.option,
                    {
                      borderColor:
                        active ? palette.text : hovered && profile.mvp ? palette.muted : palette.border,
                      backgroundColor: palette.card,
                      opacity: profile.mvp ? 1 : 0.5,
                    },
                  ]}
                >
                  <View
                    style={[
                      styles.avatar,
                      { backgroundColor: active ? palette.primary : palette.track },
                    ]}
                  >
                    <Icon
                      name={PROFILE_ICON[profile.id] ?? "user"}
                      color={active ? palette.primaryText : palette.muted}
                      size={20}
                    />
                  </View>
                  <View style={styles.optionBody}>
                    <View style={styles.optionHeader}>
                      <Text style={[styles.optionTitle, { color: palette.text }]}>
                        {profile.title}
                      </Text>
                      {active ? <Badge label={ru.demo.selected} tone="ok" /> : null}
                      {!profile.mvp ? <Badge label={ru.demo.afterMvp} /> : null}
                    </View>
                    <Muted>{profile.description}</Muted>
                  </View>
                </Pressable>
              );
            })}
          </View>
        )}
      </Card>

      <Button
        variant="secondary"
        trailingIcon="arrow"
        label={starting ? ru.demo.starting : ru.demo.start}
        onPress={() => void start()}
        loading={starting}
        disabled={profiles === null || profiles.length === 0 || startingLive}
      />
      <Muted>{ru.demo.disclaimer}</Muted>
    </Screen>
  );
}

const styles = StyleSheet.create({
  brandRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  brandName: { fontSize: 15, fontWeight: "600", letterSpacing: -0.3 },
  title: { fontSize: 34, fontWeight: "600", lineHeight: 40, letterSpacing: -1.4, paddingTop: space.lg },
  lead: { fontSize: 16, lineHeight: 24 },
  features: { flexDirection: "row", flexWrap: "wrap", gap: space.sm, paddingVertical: space.xs },
  feature: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderRadius: radius.pill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.14)",
    paddingHorizontal: space.md,
    paddingVertical: 5,
  },
  featureText: { fontSize: 13, fontWeight: "500" },
  list: { gap: space.md },
  option: {
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space.md + 2,
    flexDirection: "row",
    gap: space.md,
  },
  avatar: { width: 42, height: 42, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  optionBody: { flex: 1, gap: space.xs },
  optionHeader: { flexDirection: "row", alignItems: "center", gap: space.sm, flexWrap: "wrap" },
  optionTitle: { fontSize: 15, fontWeight: "600", letterSpacing: -0.2 },
});
