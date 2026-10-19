import { API_URL } from "../config";
import type { components } from "./schema";

// Типы генерируются из packages/api_contracts/openapi.yaml (npm run gen:api).
export type Schemas = components["schemas"];
export type DemoProfile = Schemas["DemoProfileOut"];
export type DemoSession = Schemas["DemoSessionOut"];
export type DemoSessionCreate = Schemas["DemoSessionCreate"];
export type AccountsResponse = Schemas["AccountsOut"];
export type Account = Schemas["AccountOut"];
export type ObligationsResponse = Schemas["ObligationsOut"];
export type ObligationOccurrence = Schemas["ObligationOccurrence"];
export type DataQuality = Schemas["DataQuality"];

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
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  token?: string;
  query?: Query;
}

function buildUrl(path: string, query?: Query): string {
  const params = Object.entries(query ?? {})
    .filter((entry): entry is [string, string | number | boolean] => entry[1] !== undefined)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  return `${API_URL}${path}${params.length ? `?${params.join("&")}` : ""}`;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers.Authorization = `Bearer ${options.token}`;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "network", "Сервер недоступен. Проверьте, что API запущен.");
  }

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

export const api = {
  listDemoProfiles: () => request<DemoProfile[]>("/api/v1/demo/profiles"),

  createDemoSession: (body: DemoSessionCreate) =>
    request<DemoSession>("/api/v1/demo/sessions", { method: "POST", body }),

  listAccounts: (token: string) => request<AccountsResponse>("/api/v1/accounts", { token }),

  listObligations: (token: string, dateFrom: string, dateTo: string) =>
    request<ObligationsResponse>("/api/v1/obligations", {
      token,
      query: { date_from: dateFrom, date_to: dateTo },
    }),
};
