// Разбор адреса сервера, введённого вручную: «192.168.1.5:8000» → «http://192.168.1.5:8000».

const ADDRESS = /^https?:\/\/[A-Za-z0-9.-]+(?::(\d{1,5}))?$/;

export function normalizeServerUrl(input: string): string | null {
  let value = input.trim().replace(/\/+$/, "");
  if (!value) return null;
  if (!/^[a-z]+:\/\//i.test(value)) value = `http://${value}`;
  value = value.replace(/^HTTP(S?):\/\//i, (_, s: string) => `http${s.toLowerCase()}://`);
  const match = ADDRESS.exec(value);
  if (!match) return null;
  const port = match[1] === undefined ? null : Number(match[1]);
  return port === null || (port >= 1 && port <= 65535) ? value : null;
}

/** Адрес указывает на сам телефон — частая ошибка при запуске APK без эмулятора. */
export function pointsToDevice(url: string): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(url);
}
