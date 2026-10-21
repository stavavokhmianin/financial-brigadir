import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import type { Session } from "./api/client";

// Токен держим только в памяти: после перезапуска демо начинается заново,
// участник пилота входит снова по своему коду.
interface SessionState {
  session: Session | null;
  setSession: (session: Session | null) => void;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
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
