import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import type { DemoSession } from "./api/client";

// Токен демо-сессии держим только в памяти: перезапуск приложения = новая демо-сессия.
interface SessionState {
  session: DemoSession | null;
  setSession: (session: DemoSession | null) => void;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<DemoSession | null>(null);
  const value = useMemo(() => ({ session, setSession }), [session]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSession вызван вне SessionProvider");
  }
  return value;
}
