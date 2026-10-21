# Нативная проверка Android

Workflow: `.github/workflows/android-e2e.yml`. Это сборка standalone приложения,
а не только Hermes-бандла. Аккаунт Expo не требуется для этого пути: Expo prebuild
создаёт Android-проект, Gradle собирает APK на GitHub runner.

## Что проверяется

1. APK включает ARM64 для телефонов и x86_64 для эмулятора.
2. Приложение устанавливается в виртуальное устройство Android 34.
3. Maestro проходит запуск демо, прогноз, покупку на 12 000 ₽, изменение риска,
   переключение Free/Plus, загрузку банковского мока, повтор без новых операций,
   отзыв согласия.
4. Сохраняются JUnit-результат и скриншоты. Падение проверки делает job красным.

Синтетический API запускается в той же изолированной CI-среде; `adb reverse`
связывает порт 8000 устройства с API. Клиент не обращается к публичному серверу
и не требует реальных банковских данных.

## APK для ручной проверки

В завершённом запуске workflow скачать артефакт `financial-brigadir-preview-apk`.
Второй артефакт — `android-e2e-evidence` со свидетельствами прогона. Срок хранения —
14 дней; для более поздней проверки workflow можно запустить вручную.

APK предназначен для демонстрации: использует тестовую подпись и локальный API.
Для USB-проверки на своём Android после запуска API на компьютере:

```text
adb devices
adb install -r app-release.apk
adb reverse tcp:8000 tcp:8000
```

Команды выполняются с Android Platform Tools. Приложение в этом APK обращается
к `http://127.0.0.1:8000` устройства; reverse направляет его на компьютер. Для доступа
по Wi-Fi нужна отдельная сборка с адресом вашего стенда в `EXPO_PUBLIC_API_URL`.

Для локального повторения при установленном Android SDK/JDK 17:

```text
cd apps/client
npm ci
npx expo prebuild --platform android --no-install
cd android
./gradlew :app:assembleRelease -PreactNativeArchitectures=arm64-v8a,x86_64
```

На Windows использовать `gradlew.bat`. До сборки задать `EXPO_PUBLIC_API_URL`
и `EAS_BUILD_PROFILE=preview`. Нативные каталоги генерируются и не коммитятся.

## Границы проверки

Успешный эмуляторный E2E подтверждает работу установленного Android-приложения.
Физическое устройство, iOS simulator/IPA, публикация в магазинах и промышленная
подпись — отдельные проверки. iOS Hermes export остаётся частью основного CI.
Результат именно текущего запуска фиксируется в `master/reports/REPORT_5.5.md`.

Основания реализации: [Expo CLI](https://docs.expo.dev/more/expo-cli/),
[Android emulator runner](https://github.com/ReactiveCircus/android-emulator-runner),
[Maestro CLI](https://docs.maestro.dev/maestro-cli/how-to-install-maestro-cli),
[Maestro scrolling](https://docs.maestro.dev/reference/commands-available/scrolluntilvisible).
