import { useEffect, useState } from "react";

import { api, type Meta } from "@/shared/api/client";
import { ru } from "@/shared/i18n/ru";
import { LoadingState, Screen } from "@/shared/ui/components";

import { DemoLaunchScreen } from "../demo/DemoLaunchScreen";
import { PilotSignInScreen } from "./PilotSignInScreen";

/** Стенд сам сообщает режим: демо-профили или вход участника пилота. */
export function StartScreen() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let current = true;
    api
      .getMeta()
      .then((value) => current && setMeta(value))
      // Нет связи — экран демо сам покажет ошибку и кнопку «Повторить».
      .catch(() => current && setFailed(true));
    return () => {
      current = false;
    };
  }, []);

  if (meta?.mode === "pilot" && meta.pilot_terms_version) {
    return <PilotSignInScreen termsVersion={meta.pilot_terms_version} />;
  }
  if (meta || failed) return <DemoLaunchScreen />;
  return (
    <Screen>
      <LoadingState label={ru.pilot.loading} />
    </Screen>
  );
}
