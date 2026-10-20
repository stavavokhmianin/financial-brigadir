# REPORT 4.4 — Мобильная сборка

- **Этап:** 4 (2–15 ноября 2026)
- **Ответственный по 16.1:** B — client/product
- **Коммит:** [`77437ba`](https://github.com/stavavokhmianin/financial-brigadir/commit/77437ba) в `step4ik`

## Что сделано

- `expo-doctor`: **18/18 проверок**. Исправлена версия `react-native`: 0.81.5, как требует SDK 54.
- Иконки генерирует воспроизводимый скрипт `apps/client/scripts/make_icons.py`: столбики
  остатка и пунктир резерва на акцентном фоне. Есть адаптивная иконка Android и favicon.
- `eas.json`:
  - `preview` — внутренняя раздача, APK для Android и сборка для симулятора iOS;
  - `production` — автоинкремент версии.
- `app.config.js` + `expo-build-properties`:
  - на Android `http` к локальному API (Wi-Fi, эмулятор) разрешён только вне production;
  - на iOS разрешена только локальная сеть (`NSAllowsLocalNetworking`).
- Проверено локально:
  - `expo config --type prebuild` валиден;
  - `expo export --platform android` собирает Hermes-бандл.
- CI теперь собирает мобильные бандлы Android и iOS на каждый push.

## Что не сделано (нужен аккаунт Expo и устройства)

- `eas init` и `eas build -p android --profile preview` — нужен вход в аккаунт Expo команды.
- Ручной прогон на реальных Android и iOS в Expo Go: `npx expo start`, затем
  `EXPO_PUBLIC_API_URL=http://<IP ноутбука>:8000`.
- CI этого коммита не дождался: лимит сессии закончился.
