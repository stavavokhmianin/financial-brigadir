import { useRouter } from "expo-router";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Pressable, StyleSheet, View, useWindowDimensions } from "react-native";

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
import { blue, radius, space, typeScale, usePalette } from "@/shared/ui/theme";

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
  const { width } = useWindowDimensions();
  const desktop = width >= 960;
  const palette = usePalette();
  const { setSession } = useSession();
  const [profiles, setProfiles] = useState<DemoProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState(DEFAULT_PROFILE);
  const [starting, setStarting] = useState(false);
  const [startingLive, setStartingLive] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [showProfiles, setShowProfiles] = useState(false);

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
      const session = await api.createDemoSession({
        profile_id: selected,
        seed: DEMO_SEED,
      });
      setSession(session);
      router.replace("/dashboard");
    } catch (error) {
      setStartError(messageOf(error));
    } finally {
      setStarting(false);
    }
  };

  return (
    <Screen topInset wide>
      {notice}
      <Hero style={{ padding: desktop ? 48 : 24 }}>
        <View
          style={{
            flexDirection: desktop ? "row" : "column",
            gap: 32,
            alignItems: "center",
          }}
        >
          <View style={{ flex: 1, gap: 24, minWidth: 0 }}>
            <Text style={[typeScale.eyebrow, { color: palette.heroMuted }]}>
              СПОКОЙСТВИЕ НАЧИНАЕТСЯ С ЯСНОСТИ
            </Text>
            <View style={styles.brandRow}>
              <Logo onHero />
              <Text style={[styles.brandName, { color: palette.heroText }]}>
                {ru.appName}
              </Text>
            </View>
            <Text
              accessibilityRole="header"
              style={[
                desktop ? typeScale.hero : typeScale.display,
                { color: palette.heroText },
              ]}
            >
              {ru.demo.title}
            </Text>
            <Text style={[styles.lead, { color: palette.heroMuted }]}>
              {ru.demo.lead}
            </Text>
            <View style={styles.features}>
              {FEATURES.map((feature) => (
                <View
                  key={feature.label}
                  style={[
                    styles.feature,
                    { backgroundColor: palette.heroChip },
                  ]}
                >
                  <Icon
                    name={feature.icon}
                    color={palette.heroText}
                    size={16}
                  />
                  <Text
                    style={[styles.featureText, { color: palette.heroText }]}
                  >
                    {feature.label}
                  </Text>
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
          </View>
          {desktop ? (
            <View
              pointerEvents="none"
              accessibilityElementsHidden
              importantForAccessibility="no-hide-descendants"
              style={{ width: 360, height: 390, justifyContent: "center" }}
            >
              {[blue.midnight, blue.deep, blue.steel, blue.soft, blue.ice].map(
                (color, i) => (
                  <View
                    key={color}
                    style={{
                      position: "absolute",
                      top: 20 + i * 56,
                      left: 10 + i * 3,
                      width: 320,
                      height: 130,
                      borderRadius: 65,
                      backgroundColor: color,
                      borderWidth: 1,
                      borderColor: "rgba(193,232,255,0.2)",
                      boxShadow: "0 12px 28px rgba(2,16,36,0.3)",
                      transform: [{ rotate: "-12deg" }],
                    }}
                  />
                ),
              )}
            </View>
          ) : null}
        </View>
      </Hero>
      <View style={{ flexDirection: desktop ? "row" : "column", gap: 16 }}>
        {[
          [
            "01",
            "Соберите картину",
            "Счета, поступления и обязательства — в одном пространстве.",
          ],
          [
            "02",
            "Посмотрите вперёд",
            "Узнайте, когда запас денег может опуститься ниже резерва.",
          ],
          [
            "03",
            "Решайте спокойнее",
            "Проверьте влияние покупки на прогноз до оплаты.",
          ],
        ].map(([number, title, text]) => (
          <Card key={number} style={{ flex: desktop ? 1 : undefined }}>
            <Text style={[typeScale.eyebrow, { color: palette.muted }]}>
              {number}
            </Text>
            <Text style={[typeScale.heading, { color: palette.text }]}>
              {title}
            </Text>
            <Muted>{text}</Muted>
          </Card>
        ))}
      </View>

      {startError ? (
        <ErrorState
          title={ru.demo.loadError}
          message={startError}
          hint={ru.demo.serverHint}
        />
      ) : null}

      {showProfiles ? (
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
                    aria-checked={active}
                    accessibilityState={{
                      checked: active,
                      disabled: !profile.mvp,
                    }}
                    disabled={!profile.mvp || starting || startingLive}
                    onPress={() => setSelected(profile.id)}
                    style={({ hovered }: PressState) => [
                      styles.option,
                      {
                        borderColor: active
                          ? palette.text
                          : hovered && profile.mvp
                            ? palette.muted
                            : palette.border,
                        backgroundColor: palette.card,
                        opacity: profile.mvp ? 1 : 0.5,
                      },
                    ]}
                  >
                    <View
                      style={[
                        styles.avatar,
                        {
                          backgroundColor: active
                            ? palette.primary
                            : palette.track,
                        },
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
                        <Text
                          style={[styles.optionTitle, { color: palette.text }]}
                        >
                          {profile.title}
                        </Text>
                        {active ? (
                          <Badge label={ru.demo.selected} tone="ok" />
                        ) : null}
                        {!profile.mvp ? (
                          <Badge label={ru.demo.afterMvp} />
                        ) : null}
                      </View>
                      <Muted>{profile.description}</Muted>
                    </View>
                  </Pressable>
                );
              })}
            </View>
          )}
        </Card>
      ) : null}

      {showProfiles ? (
        <Button
          variant="secondary"
          trailingIcon="arrow"
          label={starting ? ru.demo.starting : ru.demo.start}
          onPress={() => void start()}
          loading={starting}
          disabled={profiles === null || profiles.length === 0 || startingLive}
        />
      ) : (
        <Pressable
          accessibilityRole="button"
          onPress={() => setShowProfiles(true)}
          style={{ minHeight: 44, justifyContent: "center" }}
        >
          <Text style={[styles.technical, { color: palette.muted }]}>
            Технические сценарии демо
          </Text>
        </Pressable>
      )}
      <Muted>{ru.demo.disclaimer}</Muted>
    </Screen>
  );
}

const styles = StyleSheet.create({
  brandRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  brandName: { fontSize: 15, fontWeight: "600", letterSpacing: -0.3 },
  title: {
    fontSize: 34,
    fontWeight: "600",
    lineHeight: 40,
    letterSpacing: -1.4,
    paddingTop: space.lg,
  },
  lead: { fontSize: 16, lineHeight: 24 },
  features: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.sm,
    paddingVertical: space.xs,
  },
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
  avatar: {
    width: 42,
    height: 42,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  optionBody: { flex: 1, gap: space.xs },
  optionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    flexWrap: "wrap",
  },
  optionTitle: { fontSize: 15, fontWeight: "600", letterSpacing: -0.2 },
  technical: {
    textAlign: "center",
    fontSize: 12,
    textDecorationLine: "underline",
  },
});
