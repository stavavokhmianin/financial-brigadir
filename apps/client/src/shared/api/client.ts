import { apiUrl } from "../config";
import type { components } from "./schema";

// Типы генерируются из packages/api_contracts/openapi.yaml (npm run gen:api).
export type Schemas = components["schemas"];
export type DemoProfile = Schemas["DemoProfileOut"];
export type DemoSession = Schemas["DemoSessionOut"];
export type DemoSessionCreate = Schemas["DemoSessionCreate"];
export type PilotSession = Schemas["PilotSessionOut"];
export type Session = DemoSession | PilotSession;
export type Meta = Schemas["MetaOut"];
export type AccountsResponse = Schemas["AccountsOut"];
export type Account = Schemas["AccountOut"];
export type ObligationsResponse = Schemas["ObligationsOut"];
export type ObligationOccurrence = Schemas["ObligationOccurrence"];
export type DataQuality = Schemas["DataQuality"];
export type ImportResult = Schemas["ImportResultOut"];
export type Obligation = Schemas["ObligationOut"];
export type ObligationCreate = Schemas["ObligationCreate"];
export type ObligationPatch = Schemas["ObligationPatch"];
export type AccountCreate = Schemas["AccountCreate"];
export type IncomesResponse = Schemas["IncomesOut"];
export type IncomeCreate = Schemas["IncomeCreate"];
export type TransactionsPage = Schemas["TransactionsPage"];
export type Forecast = Schemas["ForecastOut"];
export type ForecastRequest = Schemas["ForecastRequest"];
export type ScenarioRequest = Schemas["ScenarioRequest"];
export type ScenarioResult = Schemas["ScenarioOut"];
export type DuplicatePair = Schemas["DuplicatePair"];
export type AlertItem = Schemas["AlertOut"];
export type AlertAnalytics = Schemas["AlertAnalyticsOut"];
export type NotificationSettings = Schemas["NotificationSettingsOut"];
export type LiveState = Schemas["LiveStateOut"];
export type Feedback = Schemas["FeedbackOut"];
export type FeedbackItem = Schemas["FeedbackItemOut"];
export type LabelResult = Schemas["TransactionLabelOut"];
export type TxLabel = NonNullable<Schemas["TransactionLabelIn"]["label"]>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type Query = Record<string, string | number | boolean | undefined>;

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  token?: string;
  query?: Query;
  headers?: Record<string, string>;
}

// Без таймаута запрос к недостижимому адресу (телефон в другой сети) висит минутами.
const TIMEOUT_MS = 20_000;
const UPLOAD_TIMEOUT_MS = 60_000;

type SessionExpiredListener = () => void;
let onSessionExpired: SessionExpiredListener | null = null;

/** Сессия истекла или отозвана на сервере: приложение возвращается на старт. */
export function setSessionExpiredListener(listener: SessionExpiredListener | null): void {
  onSessionExpired = listener;
}

function buildUrl(path: string, query?: Query): string {
  const params = Object.entries(query ?? {})
    .filter((entry): entry is [string, string | number | boolean] => entry[1] !== undefined)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  return `${apiUrl()}${path}${params.length ? `?${params.join("&")}` : ""}`;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers.Authorization = `Bearer ${options.token}`;

  const timeout = options.form ? UPLOAD_TIMEOUT_MS : TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body: options.form ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
      signal: controller.signal,
    });
  } catch {
    throw controller.signal.aborted
      ? new ApiError(0, "timeout", `Сервер не ответил за ${timeout / 1000} с. Проверьте адрес и сеть.`)
      : new ApiError(0, "network", "Сервер недоступен. Проверьте, что API запущен.");
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 401 && options.token) onSessionExpired?.();

  const payload: unknown = await response.json().catch(() => null);
  if (response.ok) {
    return payload as T;
  }
  const error = (payload as { error?: { code?: string; message?: string } } | null)?.error;
  if (error?.code && error.message) {
    throw new ApiError(response.status, error.code, error.message);
  }
  if (response.status === 422) {
    throw new ApiError(422, "validation_error", "Проверьте введённые данные.");
  }
  throw new ApiError(response.status, "http_error", `Ошибка сервера (${response.status}).`);
}

export interface CsvImportInput {
  accountId: string;
  content: string;
  mode: "preview" | "import";
  idempotencyKey?: string;
}

export const api = {
  getMeta: () => request<Meta>("/api/v1/meta"),
  createPilotSession: (body: Schemas["PilotSignIn"]) =>
    request<PilotSession>("/api/v1/pilot/sessions", { method: "POST", body }),
  getPlans: (token: string) => request<Schemas["PlansOut"]>("/api/v1/plans", { token }),
  previewDemoPlan: (token: string, plan: "free" | "plus") => request<Schemas["PlansOut"]>("/api/v1/plans/demo-preview", {
    token, method: "PATCH", body: { plan },
  }),
  bankConsent: (token: string) => request<Schemas["BankConsentOut"] | null>("/api/v1/connectors/bank-mock/consent", { token }),
  grantBankConsent: (token: string) => request<Schemas["BankConsentOut"]>("/api/v1/connectors/bank-mock/consent", {
    token, method: "POST", body: { accepted: true, scopes: ["accounts", "balances", "transactions"], ttl_hours: 24 },
  }),
  revokeBankConsent: (token: string) => request<void>("/api/v1/connectors/bank-mock/consent", { token, method: "DELETE" }),
  syncBank: (token: string, scenario: Schemas["BankMockSyncRequest"]["scenario"]) => request<Schemas["BankMockSyncOut"]>("/api/v1/connectors/bank-mock/sync", {
    token, method: "POST", body: { scenario },
  }),
  exportProfile: (token: string) => request<Record<string, unknown>>("/api/v1/privacy/export", { token }),
  logout: (token: string) => request<void>("/api/v1/privacy/logout", { token, method: "POST" }),
  deleteProfile: (token: string) => request<void>("/api/v1/privacy/profile", {
    token, method: "DELETE", body: { confirmation: "DELETE" },
  }),
  listDemoProfiles: () => request<DemoProfile[]>("/api/v1/demo/profiles"),

  createDemoSession: (body: DemoSessionCreate) =>
    request<DemoSession>("/api/v1/demo/sessions", { method: "POST", body }),

  createLiveSession: () =>
    request<DemoSession>("/api/v1/demo/live-sessions", { method: "POST", body: {} }),

  getLiveState: (token: string) => request<LiveState>("/api/v1/live", { token }),

  liveAction: (token: string, action: "next-day" | "pause" | "resume") =>
    request<LiveState>(`/api/v1/live/${action}`, { method: "POST", token }),

  getFeedback: (token: string) => request<Feedback>("/api/v1/feedback", { token }),

  setTransactionLabel: (token: string, id: string, label: TxLabel | null) =>
    request<LabelResult>(`/api/v1/transactions/${encodeURIComponent(id)}/label`, {
      method: "PUT",
      token,
      body: { label },
    }),

  listAccounts: (token: string) => request<AccountsResponse>("/api/v1/accounts", { token }),

  listObligations: (token: string, dateFrom: string, dateTo: string) =>
    request<ObligationsResponse>("/api/v1/obligations", {
      token,
      query: { date_from: dateFrom, date_to: dateTo },
    }),

  listTransactions: (token: string, dateFrom: string, dateTo: string, limit = 200) =>
    request<TransactionsPage>("/api/v1/transactions", {
      token,
      query: { date_from: dateFrom, date_to: dateTo, limit },
    }),

  createAccount: (token: string, body: AccountCreate) =>
    request<Account>("/api/v1/accounts", { method: "POST", token, body }),

  createObligation: (token: string, body: ObligationCreate, idempotencyKey?: string) =>
    request<Obligation>("/api/v1/obligations", {
      method: "POST",
      token,
      body,
      headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
    }),

  updateObligation: (token: string, id: string, body: ObligationPatch) =>
    request<Obligation>(`/api/v1/obligations/${encodeURIComponent(id)}`, {
      method: "PATCH",
      token,
      body,
    }),

  listIncomes: (token: string, dateFrom?: string, dateTo?: string) =>
    request<IncomesResponse>("/api/v1/incomes", {
      token,
      query: { date_from: dateFrom, date_to: dateTo },
    }),

  createIncome: (token: string, body: IncomeCreate) =>
    request<Schemas["IncomeOut"]>("/api/v1/incomes", { method: "POST", token, body }),

  createForecast: (token: string, body: ForecastRequest) =>
    request<Forecast>("/api/v1/forecasts", { method: "POST", token, body }),

  createScenario: (token: string, body: ScenarioRequest) =>
    request<ScenarioResult>("/api/v1/scenarios", { method: "POST", token, body }),

  listDuplicates: (token: string) =>
    request<Schemas["DuplicatesOut"]>("/api/v1/transactions/duplicates", { token }),

  resolveDuplicate: (token: string, id: string, decision: "duplicate" | "not_duplicate") =>
    request<Schemas["TransactionOut"]>(
      `/api/v1/transactions/${encodeURIComponent(id)}/duplicate-resolution`,
      { method: "POST", token, body: { decision } },
    ),

  listAlerts: (token: string) => request<Schemas["AlertsOut"]>("/api/v1/alerts", { token }),

  getAlertAnalytics: (token: string) =>
    request<AlertAnalytics>("/api/v1/alerts/analytics", { token }),

  sendAlertFeedback: (
    token: string,
    id: string,
    feedback: "useful" | "not_relevant" | "disable_type",
  ) =>
    request<AlertItem>(`/api/v1/alerts/${encodeURIComponent(id)}`, {
      method: "PATCH",
      token,
      body: { feedback },
    }),

  getNotificationSettings: (token: string) =>
    request<NotificationSettings>("/api/v1/notification-settings", { token }),

  updateNotificationSettings: (token: string, body: Schemas["NotificationSettingsPatch"]) =>
    request<NotificationSettings>("/api/v1/notification-settings", {
      method: "PATCH",
      token,
      body,
    }),

  importCsv: (token: string, input: CsvImportInput) => {
    // Текст отправляется полем content: так одинаково работает web, Android и iOS
    // без выбора файла через нативный диалог.
    const form = new FormData();
    form.append("account_id", input.accountId);
    form.append("mode", input.mode);
    form.append("content", input.content);
    return request<ImportResult>("/api/v1/imports/csv", {
      method: "POST",
      token,
      form,
      headers: input.idempotencyKey ? { "Idempotency-Key": input.idempotencyKey } : undefined,
    });
  },
};
