import { useLocalSearchParams, useRouter } from "expo-router";
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
  Field,
  Hero,
  LoadingState,
  Muted,
  Screen,
  type PressState,
} from "@/shared/ui/components";
import { Icon, type IconName } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { radius, space, typeScale, usePalette } from "@/shared/ui/theme";

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
  return error instanceof ApiError ? error.message : ru.server.unknown;
}

export function DemoLaunchScreen({ notice }: { notice?: ReactNode }) {
  const router = useRouter();
  const params = useLocalSearchParams<{ technical?: string }>();
  const { width } = useWindowDimensions();
  const desktop = width >= 960;
  const palette = usePalette();
  const { setSession } = useSession();
  const technical = params.technical === "1";

  const [authMode, setAuthMode] = useState<"register" | "signin">("register");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [startingLive, setStartingLive] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const [profiles, setProfiles] = useState<DemoProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState(DEFAULT_PROFILE);
  const [starting, setStarting] = useState(false);

  const loadProfiles = useCallback(async () => {
    setLoadError(null);
    setProfiles(null);
    try {
      setProfiles(await api.listDemoProfiles());
    } catch (error) {
      setLoadError(messageOf(error));
    }
  }, []);

  useEffect(() => {
    if (technical) void loadProfiles();
  }, [loadProfiles, technical]);

  const submitAuth = async () => {
    setAuthBusy(true);
    setStartError(null);
    try {
      const session =
        authMode === "register"
          ? await api.registerUser({ display_name: displayName, email, password })
          : await api.createUserSession({ email, password });
      setSession(session);
      router.replace("/dashboard");
    } catch (error) {
      setStartError(messageOf(error));
    } finally {
      setAuthBusy(false);
    }
  };

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

  const startTechnical = async () => {
    setStarting(true);
    setStartError(null);
    try {
      setSession(await api.createDemoSession({ profile_id: selected, seed: DEMO_SEED }));
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
            gap: desktop ? 48 : 28,
            alignItems: desktop ? "center" : "stretch",
          }}
        >
          <View style={{ flex: 1, gap: 24, minWidth: 0 }}>
            <Text style={[typeScale.eyebrow, { color: palette.heroMuted }]}>
              СПОКОЙСТВИЕ НАЧИНАЕТСЯ С ЯСНОСТИ
            </Text>
            <View style={styles.brandRow}>
              <Logo onHero />
              <Text style={[styles.brandName, { color: palette.heroText }]}>{ru.appName}</Text>
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
            <Text style={[styles.lead, { color: palette.heroMuted }]}>{ru.demo.lead}</Text>
            <View style={styles.features}>
              {FEATURES.map((feature) => (
                <View
                  key={feature.label}
                  style={[styles.feature, { backgroundColor: palette.heroChip }]}
                >
                  <Icon name={feature.icon} color={palette.heroText} size={16} />
                  <Text style={[styles.featureText, { color: palette.heroText }]}>
                    {feature.label}
                  </Text>
                </View>
              ))}
            </View>
          </View>

          <Card
            title={authMode === "register" ? ru.auth.createTitle : ru.auth.signInTitle}
            icon="user"
            style={{ width: desktop ? 410 : "100%" }}
          >
            {authMode === "register" ? <Muted>{ru.auth.createLead}</Muted> : null}
            {authMode === "register" ? (
              <Field
                label={ru.auth.name}
                value={displayName}
                onChangeText={setDisplayName}
                placeholder={ru.auth.namePlaceholder}
                autoComplete="name"
                autoCapitalize="words"
              />
            ) : null}
            <Field
              label={ru.auth.email}
              value={email}
              onChangeText={setEmail}
              placeholder="name@example.com"
              keyboardType="email-address"
              autoComplete="email"
            />
            <Field
              label={ru.auth.password}
              value={password}
              onChangeText={setPassword}
              hint={authMode === "register" ? ru.auth.passwordHint : undefined}
              secureTextEntry
              autoComplete={authMode === "register" ? "new-password" : "current-password"}
            />
            <Button
              label={authMode === "register" ? ru.auth.create : ru.auth.signIn}
              onPress={() => void submitAuth()}
              loading={authBusy}
              disabled={
                authBusy ||
                !email.trim() ||
                !password ||
                (authMode === "register" && (!displayName.trim() || password.length < 10))
              }
            />
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setAuthMode((value) => (value === "register" ? "signin" : "register"));
                setStartError(null);
              }}
              style={styles.textButton}
            >
              <Text style={[styles.textButtonLabel, { color: palette.muted }]}>
                {authMode === "register" ? ru.auth.haveAccount : ru.auth.needAccount}
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              disabled={startingLive || authBusy}
              onPress={() => void startLive()}
              style={styles.textButton}
            >
              <Text style={[styles.textButtonLabel, { color: palette.muted }]}>
                {startingLive ? ru.live.starting : ru.auth.continueGuest}
              </Text>
            </Pressable>
          </Card>
        </View>
      </Hero>

      {startError ? (
        <ErrorState title={ru.auth.error} message={startError} hint={ru.demo.serverHint} />
      ) : null}

      <View style={{ flexDirection: desktop ? "row" : "column", gap: 16 }}>
        {[
          ["01", "Соберите картину", "Счета, поступления и обязательства — в одном пространстве."],
          ["02", "Посмотрите вперёд", "Узнайте, когда запас денег может опуститься ниже резерва."],
          ["03", "Решайте спокойнее", "Проверьте влияние покупки на прогноз до оплаты."],
        ].map(([number, title, description]) => (
          <Card key={number} style={{ flex: desktop ? 1 : undefined }}>
            <Text style={[typeScale.eyebrow, { color: palette.muted }]}>{number}</Text>
            <Text style={[typeScale.heading, { color: palette.text }]}>{title}</Text>
            <Muted>{description}</Muted>
          </Card>
        ))}
      </View>

      {technical ? (
        <>
          <Card title={ru.demo.profilesTitle}>
            <Muted>{ru.demo.profilesLead}</Muted>
            {loadError ? (
              <ErrorState
                title={ru.demo.loadError}
                message={loadError}
                onRetry={() => void loadProfiles()}
              />
            ) : profiles === null ? (
              <LoadingState label={ru.demo.loading} />
            ) : (
              <View accessibilityRole="radiogroup" style={styles.list}>
                {profiles.map((profile) => {
                  const active = profile.id === selected;
                  return (
                    <Pressable
                      key={profile.id}
                      accessibilityRole="radio"
                      aria-checked={active}
                      accessibilityState={{ checked: active, disabled: !profile.mvp }}
                      disabled={!profile.mvp || starting}
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
            label={ru.demo.start}
            onPress={() => void startTechnical()}
            loading={starting}
            disabled={profiles === null || profiles.length === 0}
          />
        </>
      ) : null}

      <Muted>{ru.demo.disclaimer}</Muted>
    </Screen>
  );
}

const styles = StyleSheet.create({
  brandRow: { flexDirection: "row", alignItems: "center", gap: space.md },
  brandName: { fontSize: 15, fontWeight: "600", letterSpacing: -0.3 },
  lead: { fontSize: 16, lineHeight: 24 },
  features: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
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
  textButton: { minHeight: 36, alignItems: "center", justifyContent: "center" },
  textButtonLabel: { fontSize: 13, textDecorationLine: "underline" },
  list: { gap: space.md },
  option: {
    minHeight: 64,
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
  optionHeader: { flexDirection: "row", alignItems: "center", gap: space.sm, flexWrap: "wrap" },
  optionTitle: { fontSize: 15, fontWeight: "600", letterSpacing: -0.2 },
});
