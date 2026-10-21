import { Platform } from "react-native";

import { API_URL_FROM_ENV } from "./env";

// Эмулятор Android видит хост-машину по 10.0.2.2, а не localhost.
const fallback = Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000";

export const DEFAULT_API_URL = (API_URL_FROM_ENV || fallback).replace(/\/+$/, "");

// Адрес можно сменить на стартовом экране: собранный APK на телефоне не знает,
// где запущен API (ноутбук в той же Wi-Fi, стенд команды). Живёт до перезапуска.
let currentApiUrl = DEFAULT_API_URL;

export function apiUrl(): string {
  return currentApiUrl;
}

export function setApiUrl(url: string): void {
  currentApiUrl = url;
}

export const DEMO_SEED = 42;
