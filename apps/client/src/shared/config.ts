import { Platform } from "react-native";

import { API_URL_FROM_ENV } from "./env";

// Эмулятор Android видит хост-машину по 10.0.2.2, а не localhost.
const fallback = Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000";

export const API_URL = (API_URL_FROM_ENV || fallback).replace(/\/+$/, "");

export const DEMO_SEED = 42;
