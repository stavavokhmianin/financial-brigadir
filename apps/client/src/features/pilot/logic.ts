// Вход участника пилота: код 16 символов (группы по 4), регистр и разделители не важны.

export function normalizeCode(code: string): string {
  return code.toUpperCase().replace(/[^0-9A-Z]/g, "");
}

export function canSubmit(code: string, termsAccepted: boolean): boolean {
  return termsAccepted && normalizeCode(code).length === 16;
}
