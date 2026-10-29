import {
  Manrope_500Medium,
  Manrope_600SemiBold,
  Manrope_700Bold,
  Manrope_800ExtraBold,
  useFonts,
} from "@expo-google-fonts/manrope";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ru } from "@/shared/i18n/ru";
import { SessionProvider } from "@/shared/session";
import { fonts, usePalette } from "@/shared/ui/theme";

export default function RootLayout() {
  const palette = usePalette();
  const [loaded, failed] = useFonts({
    Manrope_500Medium,
    Manrope_600SemiBold,
    Manrope_700Bold,
    Manrope_800ExtraBold,
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
            headerShadowVisible: false,
            headerTintColor: palette.accent,
            headerTitleStyle: { fontFamily: fonts.bold, fontSize: 18, color: palette.text },
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
