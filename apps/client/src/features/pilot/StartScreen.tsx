import { useCallback, useEffect, useState } from "react";

import { api, ApiError, type Meta } from "@/shared/api/client";
import { ru } from "@/shared/i18n/ru";
import { ErrorState, LoadingState, Screen } from "@/shared/ui/components";

import { DemoLaunchScreen } from "../demo/DemoLaunchScreen";
import { PilotSignInScreen } from "./PilotSignInScreen";
import { ServerCard } from "./ServerCard";

/** Стенд сам сообщает режим: демо-профили или вход участника пилота. */
export function StartScreen() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    let current = true;
    setMeta(null);
    setError(null);
    api
      .getMeta()
      .then((value) => current && setMeta(value))
      .catch((err: unknown) => {
        if (current) setError(err instanceof ApiError ? err.message : ru.server.unknown);
      });
    return () => {
      current = false;
    };
  }, []);

  useEffect(() => load(), [load]);

  if (meta?.mode === "pilot" && meta.pilot_terms_version) {
    return <PilotSignInScreen termsVersion={meta.pilot_terms_version} />;
  }
  if (meta) return <DemoLaunchScreen />;
  return (
    <Screen>
      {error ? (
        <>
          <ErrorState title={ru.server.unavailable} message={error} onRetry={() => void load()} />
          <ServerCard onConnect={() => void load()} />
        </>
      ) : (
        <LoadingState label={ru.pilot.loading} />
      )}
    </Screen>
  );
}
