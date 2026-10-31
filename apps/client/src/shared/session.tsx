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

// Токен держим только в памяти: после перезапуска демо начинается заново,
// участник пилота входит снова по своему коду.
interface SessionState {
  session: Session | null;
  setSession: (session: Session | null) => void;
  /** Сессия закончилась на сервере (срок, выход на другом устройстве, новая база). */
  expired: boolean;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      const saved = window.sessionStorage.getItem("brigadir-session");
      return saved ? (JSON.parse(saved) as Session) : null;
    } catch {
      return null;
    }
  });
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setSessionExpiredListener(() => {
      setSessionState(null);
      if (typeof window !== "undefined") {
        window.sessionStorage.removeItem("brigadir-session");
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
          if (next) window.sessionStorage.setItem("brigadir-session", JSON.stringify(next));
          else window.sessionStorage.removeItem("brigadir-session");
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
