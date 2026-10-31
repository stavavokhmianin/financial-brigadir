import { usePathname, useRouter, type Href } from "expo-router";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { ReactNode } from "react";
import { Logo } from "./brand";
import { Icon, type IconName } from "./icons";
import { Text } from "./text";
import { fonts, radius, space, typeScale, usePalette, useTheme } from "./theme";
import { Reveal } from "./motion";

const pages: Record<string, [string, string, string]> = {
  "/dashboard": [
    "ЛИЧНЫЙ КАПИТАЛ",
    "Обзор финансов",
    "Всё важное о ваших деньгах. В одном месте.",
  ],
  "/forecast": [
    "ВЗГЛЯД ВПЕРЁД",
    "Деньги в перспективе",
    "Будущие поступления, платежи и запас прочности.",
  ],
  "/simulate": [
    "ПРОВЕРКА РЕШЕНИЙ",
    "А что, если?",
    "Проверьте покупку до того, как потратите деньги.",
  ],
  "/calendar": [
    "ВАШ РИТМ",
    "Календарь платежей",
    "История и ближайшие обязательства — по дням.",
  ],
  "/add": [
    "УЧЁТ",
    "Новая операция",
    "Добавьте счёт, платёж или ожидаемый доход.",
  ],
  "/import": [
    "ИСТОРИЯ ОПЕРАЦИЙ",
    "Импорт выписки",
    "Ваша история — основа более точного прогноза.",
  ],
  "/bank": [
    "ПОДКЛЮЧЕНИЯ",
    "Учебный банк",
    "Попробуйте банковский сценарий на демо-данных.",
  ],
  "/alerts": [
    "ПОД КОНТРОЛЕМ",
    "Уведомления",
    "Важные сигналы. В подходящий момент.",
  ],
  "/duplicates": [
    "КАЧЕСТВО ДАННЫХ",
    "Проверка повторов",
    "Убедитесь, что каждая операция учтена один раз.",
  ],
  "/plans": [
    "ВОЗМОЖНОСТИ",
    "Ваш следующий шаг",
    "Выберите глубину финансового планирования.",
  ],
  "/privacy": [
    "ВАШИ ДАННЫЕ",
    "Приватность",
    "Управляйте информацией, которую доверяете приложению.",
  ],
};
const destinations: { path: string; title: string; icon: IconName }[] = [
  { path: "/dashboard", title: "Обзор", icon: "wallet" },
  { path: "/forecast", title: "Прогноз", icon: "chart" },
  { path: "/calendar", title: "Календарь", icon: "calendar" },
  { path: "/simulate", title: "Что, если?", icon: "sparkle" },
];

export function AppShell({
  children,
  wide = false,
}: {
  children: ReactNode;
  wide?: boolean;
}) {
  const palette = usePalette();
  const { mode, toggle } = useTheme();
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  const router = useRouter();
  const desktop = width >= 800;
  const landing = pathname === "/";
  const page = pages[pathname];
  const maxWidth = wide ? 1200 : 800;
  const nav = (mobile: boolean) =>
    destinations.map((item) => {
      const active = pathname === item.path;
      return (
        <Pressable
          key={item.path}
          accessibilityRole="button"
          accessibilityLabel={item.title}
          accessibilityState={{ selected: active }}
          onPress={() => router.navigate(item.path as Href)}
          style={({ pressed }) => [
            styles.navItem,
            mobile && styles.mobileItem,
            {
              backgroundColor: active
                ? palette.accentSoft
                : pressed
                  ? palette.track
                  : "transparent",
            },
          ]}
        >
          <Icon
            name={item.icon}
            color={active ? palette.accent : palette.muted}
            size={18}
          />
          <Text
            style={[
              mobile ? styles.mobileLabel : styles.navLabel,
              { color: active ? palette.text : palette.muted },
            ]}
          >
            {item.title}
          </Text>
        </Pressable>
      );
    });
  return (
    <View style={{ flex: 1, backgroundColor: palette.background }}>
      <View
        style={[
          styles.top,
          {
            borderColor: palette.border,
            paddingTop: insets.top + 12,
            paddingHorizontal: desktop ? 32 : 16,
          },
        ]}
      >
        <View style={styles.topInner}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Финансовый бригадир — главная"
            onPress={() => router.navigate(landing ? "/" : "/dashboard")}
            style={styles.brand}
          >
            <Logo size={34} />
            <Text style={[styles.brandName, { color: palette.text }]}>
              Финансовый{"\n"}бригадир
            </Text>
          </Pressable>
          {!landing && desktop ? (
            <View style={styles.nav}>{nav(false)}</View>
          ) : null}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={
              mode === "dark" ? "Включить светлую тему" : "Включить тёмную тему"
            }
            onPress={toggle}
            style={({ pressed }) => [
              styles.theme,
              {
                backgroundColor: pressed ? palette.track : palette.surface,
                borderColor: palette.border,
              },
            ]}
          >
            <Text style={{ color: palette.accent, fontSize: 20 }}>
              {mode === "dark" ? "☼" : "◐"}
            </Text>
          </Pressable>
        </View>
      </View>
      <ScrollView
        style={{ flex: 1 }}
        automaticallyAdjustKeyboardInsets
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{
          alignItems: "center",
          paddingHorizontal: desktop ? 32 : 16,
          paddingTop: desktop ? 40 : 24,
          paddingBottom: 40 + (desktop || landing ? insets.bottom : 0),
        }}
      >
        <View style={{ width: "100%", maxWidth, gap: desktop ? 24 : 16 }}>
          {page ? (
            <View style={styles.pageHeading}>
              {!destinations.some((d) => d.path === pathname) ? (
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Вернуться к обзору"
                  onPress={() => router.navigate("/dashboard")}
                  style={styles.back}
                >
                  <Text style={{ color: palette.muted }}>← К обзору</Text>
                </Pressable>
              ) : null}
              <Text style={[typeScale.eyebrow, { color: palette.muted }]}>
                {page[0]}
              </Text>
              <Text
                accessibilityRole="header"
                style={[
                  desktop ? typeScale.display : typeScale.title,
                  { color: palette.text },
                ]}
              >
                {page[1]}
              </Text>
              <Text style={[typeScale.body, { color: palette.muted }]}>
                {page[2]}
              </Text>
            </View>
          ) : null}
          <Reveal revision={pathname} style={{ gap: desktop ? 24 : 16 }}>
            {children}
          </Reveal>
          <View style={[styles.footer, { borderColor: palette.border }]}>
            <Text style={[typeScale.caption, { color: palette.muted }]}>
              Финансовый бригадир
            </Text>
            <Text style={[typeScale.caption, { color: palette.muted }]}>
              Ясность сегодня. Спокойствие завтра.
            </Text>
          </View>
        </View>
      </ScrollView>
      {!landing && !desktop ? (
        <View
          style={[
            styles.mobileNav,
            {
              backgroundColor: palette.surface,
              borderColor: palette.border,
              paddingBottom: Math.max(insets.bottom, 8),
            },
          ]}
        >
          {nav(true)}
        </View>
      ) : null}
    </View>
  );
}
const styles = StyleSheet.create({
  top: { borderBottomWidth: 1, paddingBottom: 12 },
  topInner: {
    width: "100%",
    maxWidth: 1200,
    alignSelf: "center",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
  },
  brand: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 44 },
  brandName: {
    fontSize: 13,
    lineHeight: 16,
    fontWeight: "600",
    letterSpacing: -0.25,
  },
  nav: { flexDirection: "row", gap: 6 },
  navItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 44,
    paddingHorizontal: 16,
    gap: 8,
    borderRadius: radius.md,
  },
  navLabel: { fontSize: 13, fontWeight: "500" },
  theme: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  pageHeading: { gap: 8 },
  back: { minHeight: 44, justifyContent: "center", alignSelf: "flex-start" },
  mobileNav: {
    flexDirection: "row",
    paddingHorizontal: 8,
    paddingTop: 8,
    borderTopWidth: 1,
  },
  mobileItem: {
    flex: 1,
    paddingHorizontal: 2,
    flexDirection: "column",
    gap: 4,
    minHeight: 50,
  },
  mobileLabel: { fontSize: 10, fontWeight: "500" },
  footer: {
    borderTopWidth: 1,
    paddingTop: 20,
    marginTop: 12,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    justifyContent: "space-between",
  },
});
