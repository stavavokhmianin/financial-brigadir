// Чистая логика главного экрана: без React, проверяется node --test.

export interface Occurrence {
  obligation_id: string;
  date: string;
  title: string;
  amount_minor: number;
  status: string;
  priority: string;
}

export interface AccountLike {
  type: string;
  available_balance_minor: number;
  credit_limit_minor?: number | null;
  blocked_minor: number;
  is_liquid: boolean;
}

/** Платежи в окне [from, to] по возрастанию даты, с накопленной суммой списаний. */
export function upcoming(
  calendar: readonly Occurrence[],
  from: string,
  to: string,
): { items: Occurrence[]; totalMinor: number } {
  const items = calendar
    .filter((item) => item.date >= from && item.date <= to)
    .slice()
    .sort((a, b) => (a.date === b.date ? a.title.localeCompare(b.title) : a.date < b.date ? -1 : 1));
  const totalMinor = items.reduce((sum, item) => sum + item.amount_minor, 0);
  return { items, totalMinor };
}

export type AccountLine =
  | { kind: "liquid"; balanceMinor: number; blockedMinor: number }
  | { kind: "credit"; debtMinor: number; limitMinor: number | null }
  | { kind: "excluded"; balanceMinor: number };

/** Как показывать счёт: кредитка — долг из лимита, неликвидный — отдельной строкой (7.3). */
export function describeAccount(account: AccountLike): AccountLine {
  if (account.type === "credit_card") {
    return {
      kind: "credit",
      debtMinor: Math.max(0, -account.available_balance_minor),
      limitMinor: account.credit_limit_minor ?? null,
    };
  }
  if (!account.is_liquid) {
    return { kind: "excluded", balanceMinor: account.available_balance_minor };
  }
  return {
    kind: "liquid",
    balanceMinor: account.available_balance_minor,
    blockedMinor: account.blocked_minor,
  };
}
