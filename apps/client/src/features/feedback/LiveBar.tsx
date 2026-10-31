import { useFocusEffect } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, View } from "react-native";

import { api, type LiveState } from "@/shared/api/client";
import { formatMoment, plural } from "@/shared/format";
import { ru } from "@/shared/i18n/ru";
import { Badge, Card, Muted, type PressState } from "@/shared/ui/components";
import { Icon } from "@/shared/ui/icons";
import { Text } from "@/shared/ui/text";
import { radius, space, usePalette } from "@/shared/ui/theme";

import { arrived, dayChanged } from "./logic";

// Опрос держит ленивое время сервера в движении, пока главная открыта.
const POLL_MS = 10_000;

interface Props {
  token: string;
  /** Последнее состояние, которое главная получила при своей загрузке. */
  latest: LiveState;
  /** Пришли новые операции: главной пора обновить остаток и прогноз. */
  onArrived: () => void;
}

export function LiveBar({ token, latest, onArrived }: Props) {
  const palette = usePalette();
  const [expanded, setExpanded] = useState(false);
  const [state, setState] = useState<LiveState>(latest);
  const [busy, setBusy] = useState(false);
  const [fresh, setFresh] = useState(0);
  const seen = useRef<number | null>(latest.revealed_total);
  const lastMoment = useRef(latest.virtual_now);

  /** ``notify`` — сообщить главной; когда состояние пришло от неё самой, не нужно. */
  const apply = useCallback(
    (next: LiveState, notify = true) => {
      const count = arrived(seen.current, next.revealed_total);
      const newDay = dayChanged(lastMoment.current, next.virtual_now);
      seen.current = next.revealed_total;
      lastMoment.current = next.virtual_now;
      setState(next);
      if (count > 0) setFresh(count);
      if ((count > 0 || newDay) && notify) onArrived();
    },
    [onArrived],
  );

  // Главная обновилась сама (после метки): новые операции могли прийти и тогда —
  // бейдж должен объяснить, откуда изменились числа.
  useEffect(() => {
    apply(latest, false);
  }, [latest, apply]);

  useFocusEffect(
    useCallback(() => {
      const timer = setInterval(() => {
        api.getLiveState(token).then(
          (next) => apply(next),
          () => undefined,
        );
      }, POLL_MS);
      return () => clearInterval(timer);
    }, [token, apply]),
  );

  const act = async (action: "next-day" | "pause" | "resume") => {
    setBusy(true);
    try {
      apply(await api.liveAction(token, action));
    } catch {
      // Ошибку сети покажет следующий опрос или загрузка главной.
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={ru.live.controls}
        accessibilityState={{ expanded }}
        aria-expanded={expanded}
        onPress={() => setExpanded((value) => !value)}
        style={({ pressed }) => [styles.row, { opacity: pressed ? 0.76 : 1 }]}
      >
        <View style={[styles.icon, { borderColor: palette.border }]}>
          <Icon name="clock" color={palette.text} size={16} />
        </View>
        <View style={styles.main}>
          <Muted>{ru.live.badge}</Muted>
          <Text
            accessibilityRole="summary"
            style={[styles.moment, { color: palette.text }]}
          >
            {formatMoment(state.virtual_now)}
          </Text>
        </View>
        {state.finished ? null : state.paused ? (
          <Badge label={ru.live.paused} tone="warning" />
        ) : fresh > 0 ? (
          <Badge
            label={`+${fresh} ${plural(fresh, ru.live.arrived)}`}
            tone="ok"
          />
        ) : (
          <Text style={[styles.toggle, { color: palette.accent }]}>
            {expanded ? ru.live.hideControls : ru.live.showControls}
          </Text>
        )}
      </Pressable>
      {expanded ? (
        state.finished ? (
          <Muted>{ru.live.finished}</Muted>
        ) : (
          <View style={styles.controlPanel}>
            <Muted>
              {ru.live.pace} {state.seconds_per_day} {ru.live.seconds}
            </Muted>
            <View style={styles.actions}>
              <Pill
                label={state.paused ? ru.live.resume : ru.live.pause}
                disabled={busy}
                onPress={() => void act(state.paused ? "resume" : "pause")}
              />
              <Pill
                label={ru.live.nextDay}
                disabled={busy}
                onPress={() => void act("next-day")}
              />
              {busy ? <ActivityIndicator color={palette.accent} /> : null}
            </View>
          </View>
        )
      ) : null}
    </Card>
  );
}

function Pill({
  label,
  onPress,
  disabled,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  const palette = usePalette();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed, hovered }: PressState) => [
        styles.pill,
        {
          backgroundColor: pressed || hovered ? palette.track : palette.card,
          borderColor: palette.border,
          opacity: disabled ? 0.5 : 1,
        },
      ]}
    >
      <Text style={[styles.pillText, { color: palette.text }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
  },
  icon: {
    width: 36,
    height: 36,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  main: { flex: 1, gap: 2 },
  moment: {
    fontSize: 16,
    fontWeight: "600",
    letterSpacing: -0.32,
    fontVariant: ["tabular-nums"],
  },
  toggle: { fontSize: 13, fontWeight: "500" },
  controlPanel: { gap: space.sm, paddingTop: space.sm },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    flexWrap: "wrap",
  },
  pill: {
    minHeight: 44,
    justifyContent: "center",
    borderRadius: radius.pill,
    borderWidth: 1,
    paddingHorizontal: space.lg,
    paddingVertical: 7,
  },
  pillText: { fontSize: 14, fontWeight: "500" },
});
