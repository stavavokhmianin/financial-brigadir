import { router } from "expo-router";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { setSessionExpiredListener, type Session } from "./api/client";

const STORAGE_KEY = "brigadir-session";

function loadStoredSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    // sessionStorage читаем один раз для бесшовного перехода со старой версии клиента.
    const saved = window.localStorage.getItem(STORAGE_KEY) ??
      window.sessionStorage.getItem(STORAGE_KEY);
    if (!saved) return null;
    const parsed = JSON.parse(saved) as Session;
    if (!parsed.expires_at || Date.parse(parsed.expires_at) <= Date.now()) {
      window.localStorage.removeItem(STORAGE_KEY);
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    window.localStorage.setItem(STORAGE_KEY, saved);
    window.sessionStorage.removeItem(STORAGE_KEY);
    return parsed;
  } catch {
    return null;
  }
}

interface SessionState {
  session: Session | null;
  setSession: (session: Session | null) => void;
  /** Сессия закончилась на сервере (срок, выход на другом устройстве, новая база). */
  expired: boolean;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(loadStoredSession);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setSessionExpiredListener(() => {
      setSessionState(null);
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(STORAGE_KEY);
        window.sessionStorage.removeItem(STORAGE_KEY);
      }
      setExpired(true);
      if (router.canDismiss()) router.dismissAll();
      router.replace("/");
    });
    return () => setSessionExpiredListener(null);
  }, []);

  const value = useMemo(
    () => ({
      session,
      expired,
      setSession: (next: Session | null) => {
        setExpired(false);
        setSessionState(next);
        if (typeof window !== "undefined") {
          if (next) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
          else window.localStorage.removeItem(STORAGE_KEY);
          window.sessionStorage.removeItem(STORAGE_KEY);
        }
      },
    }),
    [session, expired],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSession вызван вне SessionProvider");
  }
  return value;
}
