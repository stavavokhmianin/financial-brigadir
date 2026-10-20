import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ru } from "@/shared/i18n/ru";
import { SessionProvider } from "@/shared/session";

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <SessionProvider>
        <StatusBar style="auto" />
        <Stack>
          <Stack.Screen name="index" options={{ title: ru.appName }} />
          <Stack.Screen name="dashboard" options={{ title: ru.dashboard.screenTitle }} />
          <Stack.Screen name="import" options={{ title: ru.imports.screenTitle }} />
        </Stack>
      </SessionProvider>
    </SafeAreaProvider>
  );
}
