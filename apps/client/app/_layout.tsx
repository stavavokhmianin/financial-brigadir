import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { Platform, StyleSheet, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ru } from "@/shared/i18n/ru";
import { SessionProvider } from "@/shared/session";
import { fonts, usePalette } from "@/shared/ui/theme";

export default function RootLayout() {
  const palette = usePalette();
  // Geist лежит в assets/fonts: статические начертания с кириллицей (OFL).
  const [loaded, failed] = useFonts({
    [fonts.regular]: require("../assets/fonts/Geist_400Regular.ttf"),
    [fonts.medium]: require("../assets/fonts/Geist_500Medium.ttf"),
    [fonts.bold]: require("../assets/fonts/Geist_600SemiBold.ttf"),
    [fonts.heavy]: require("../assets/fonts/Geist_700Bold.ttf"),
    [fonts.mono]: require("../assets/fonts/GeistMono_400Regular.ttf"),
    [fonts.monoMedium]: require("../assets/fonts/GeistMono_500Medium.ttf"),
  });
  // Без шрифта не ждём бесконечно: системный шрифт лучше пустого экрана.
  if (!loaded && !failed) return null;

  return (
    <SafeAreaProvider>
      <SessionProvider>
        <StatusBar style="auto" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: palette.background },
            // Шапка отделена тонкой линией: на iOS — нативной, на web — своим фоном.
            // На Android нативная граница — это material-тень, поэтому там её нет.
            headerShadowVisible: Platform.OS === "ios",
            headerBackground:
              Platform.OS === "web"
                ? () => (
                    <View
                      style={[
                        styles.headerBackground,
                        { backgroundColor: palette.background, borderColor: palette.border },
                      ]}
                    />
                  )
                : undefined,
            headerTintColor: palette.text,
            headerTitleStyle: {
              fontFamily: fonts.bold,
              fontSize: 16,
              color: palette.text,
            },
            contentStyle: { backgroundColor: palette.background },
          }}
        >
          <Stack.Screen name="index" options={{ title: ru.appName, headerShown: false }} />
          <Stack.Screen name="dashboard" options={{ title: ru.dashboard.screenTitle }} />
          <Stack.Screen name="import" options={{ title: ru.imports.screenTitle }} />
          <Stack.Screen name="add" options={{ title: ru.manual.screenTitle }} />
          <Stack.Screen name="calendar" options={{ title: ru.calendar.screenTitle }} />
          <Stack.Screen name="forecast" options={{ title: ru.forecast.screenTitle }} />
          <Stack.Screen name="simulate" options={{ title: ru.simulate.screenTitle }} />
          <Stack.Screen name="duplicates" options={{ title: ru.duplicates.screenTitle }} />
          <Stack.Screen name="alerts" options={{ title: ru.alerts.screenTitle }} />
          <Stack.Screen name="privacy" options={{ title: "Приватность и данные" }} />
          <Stack.Screen name="bank" options={{ title: "Учебный банк" }} />
          <Stack.Screen name="plans" options={{ title: "Free и Plus" }} />
        </Stack>
      </SessionProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  headerBackground: { flex: 1, borderBottomWidth: StyleSheet.hairlineWidth },
});
