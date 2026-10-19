// Expo подставляет EXPO_PUBLIC_* при сборке только для буквального обращения
// process.env.EXPO_PUBLIC_…, поэтому чтение вынесено в отдельный JS-модуль
// (типы — в env.d.ts).
export const API_URL_FROM_ENV = process.env.EXPO_PUBLIC_API_URL;
