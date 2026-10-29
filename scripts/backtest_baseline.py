"""Бэктест прогноза и калибровка вероятностей на синтетике (разделы 9.3, 15.2, критерий 19.12).

    python scripts/backtest_baseline.py [--seeds 30] [--out docs/backtest/baseline.md]

Сравнивает модели на одних и тех же профилях и периодах:
  A — только календарь подтверждённых событий (без повседневных трат);
  B — календарь + медиана трат по дням недели (baseline из ТЗ);
  M — baseline-0.1: календарь + среднее трат по дням недели без аномалий;
  P — mc-0.2: симуляция Монте-Карло с вероятностью нарушения резерва.

Модели видят только ``known`` (данные на дату прогноза); оценка — по
``hidden_future``. Параметры симуляции не подбирались по этим данным.
Синтетика не доказывает качество на реальных данных (12.1).
"""

import argparse
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from forecast_core.adapters import actual_liquid_path, snapshot_from_dataset
from forecast_core.baseline import ForecastResult, run_baseline
from forecast_core.probabilistic import run_monte_carlo
from synthetic_generator import PROFILES, generate

HORIZON = 30
RESERVE = 500_000
MODELS = {
    "A": "Календарь",
    "B": "Календарь + медиана по дням недели",
    "M": "baseline-0.1 (среднее без аномалий)",
    "P": "mc-0.2 (симуляция)",
}
BINS = ((0.0, 0.1), (0.1, 0.3), (0.3, 0.6), (0.6, 1.01))


@dataclass
class Score:
    mae: list[float] = field(default_factory=list)
    bias: list[float] = field(default_factory=list)
    coverage: list[float] = field(default_factory=list)
    hits: int = 0  # реальный разрыв предсказан (risk ≥ medium)
    misses: int = 0  # реальный разрыв не предсказан
    false_alarms: int = 0  # предупреждение без реального разрыва


@dataclass
class Calibration:
    """Пары (предсказанная вероятность, исход) — по горизонту и по дням."""

    horizon: list[tuple[float, int]] = field(default_factory=list)
    daily: list[tuple[float, int]] = field(default_factory=list)


def _run(key: str, data: dict) -> ForecastResult:  # type: ignore[type-arg]
    if key == "A":
        return run_baseline(snapshot_from_dataset(data, RESERVE, HORIZON, without_spending=True))
    snapshot = snapshot_from_dataset(data, RESERVE, HORIZON)
    if key == "B":
        return run_baseline(snapshot, estimator="median")
    if key == "M":
        return run_baseline(snapshot)
    return run_monte_carlo(snapshot)


def evaluate(seeds: int) -> tuple[dict[str, dict[str, Score]], Calibration]:
    results: dict[str, dict[str, Score]] = {}
    calibration = Calibration()
    for profile_id, info in PROFILES.items():
        if not info.mvp:
            continue
        results[profile_id] = {key: Score() for key in MODELS}
        for seed in range(1, seeds + 1):
            data = generate(profile_id, seed=seed)
            actual = actual_liquid_path(data, HORIZON)
            breached = min(actual.values()) < RESERVE
            for key in MODELS:
                result = _run(key, data)
                errors = [p.p50_minor - actual[p.day] for p in result.points]
                inside = [p.p10_minor <= actual[p.day] <= p.p90_minor for p in result.points]
                score = results[profile_id][key]
                score.mae.append(sum(abs(e) for e in errors) / len(errors))
                score.bias.append(sum(errors) / len(errors))
                score.coverage.append(sum(inside) / len(inside))
                warned = result.risk_level != "low"
                if breached and warned:
                    score.hits += 1
                elif breached:
                    score.misses += 1
                elif warned:
                    score.false_alarms += 1
                if key == "P" and result.gap_probability is not None:
                    calibration.horizon.append((result.gap_probability, int(breached)))
                    calibration.daily.extend(
                        (p.risk_probability or 0.0, int(actual[p.day] < RESERVE))
                        for p in result.points
                    )
    return results, calibration


def brier(pairs: list[tuple[float, int]]) -> float:
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs) if pairs else float("nan")


def skill(pairs: list[tuple[float, int]]) -> float:
    """Brier skill score против «климатологии» — постоянной частоты событий."""
    if not pairs:
        return float("nan")
    base_rate = sum(o for _, o in pairs) / len(pairs)
    reference = brier([(base_rate, o) for _, o in pairs])
    return 1 - brier(pairs) / reference if reference else float("nan")


def _rub(minor: float) -> str:
    return f"{minor / 100:,.0f}".replace(",", " ")


def _reliability(pairs: list[tuple[float, int]], title: str) -> list[str]:
    lines = [
        f"**{title}** — Brier {brier(pairs):.3f}, skill {skill(pairs):+.2f} (n = {len(pairs)})",
        "",
        "| Предсказанная вероятность | Прогнозов | Средняя предсказанная | Фактическая частота |",
        "|---|---:|---:|---:|",
    ]
    for low, high in BINS:
        bucket = [(p, o) for p, o in pairs if low <= p < high]
        if not bucket:
            lines.append(f"| {low:.0%}–{min(high, 1):.0%} | 0 | — | — |")
            continue
        predicted = statistics.mean(p for p, _ in bucket)
        observed = statistics.mean(o for _, o in bucket)
        lines.append(
            f"| {low:.0%}–{min(high, 1):.0%} | {len(bucket)} | {predicted:.0%} | {observed:.0%} |"
        )
    return [*lines, ""]


def render(results: dict[str, dict[str, Score]], calibration: Calibration, seeds: int) -> str:
    lines = [
        "# Бэктест прогноза и калибровка вероятностей",
        "",
        "Сгенерировано `scripts/backtest_baseline.py`. Горизонт 30 дней, резерв 5 000 ₽,",
        f"{seeds} профилей каждого типа (seed 1…{seeds}), дата прогноза 19.10.2026.",
        "Модели видят только данные на дату прогноза, оценка идёт по скрытому будущему генератора.",
        "",
        "> Это синтетика: результат проверяет корректность расчёта, но не доказывает качество",
        "> на реальном поведении людей (раздел 12.1).",
        "",
        "Модели: " + "; ".join(f"**{k}** — {v}" for k, v in MODELS.items()) + ".",
        "",
        "## Точность остатка и обнаружение разрывов",
        "",
        "| Профиль | Модель | MAE остатка, ₽ | Смещение, ₽ | Факт в коридоре p10–p90 |"
        " Разрыв пойман | Пропущен | Ложная тревога |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for profile_id, scores in results.items():
        for key, score in scores.items():
            lines.append(
                f"| {profile_id} | {key} | {_rub(statistics.mean(score.mae))} | "
                f"{_rub(statistics.mean(score.bias))} | {statistics.mean(score.coverage):.0%} | "
                f"{score.hits} | {score.misses} | {score.false_alarms} |"
            )
    lines += [
        "",
        "Смещение > 0 — прогноз выше факта (модель оптимистична). «Разрыв» — фактический",
        "остаток ниже резерва хотя бы в один день горизонта. Предупреждение — уровень риска",
        "medium или high.",
        "",
        "## Калибровка вероятностей модели P (раздел 9.3)",
        "",
        "Brier score — средний квадрат ошибки вероятности (0 — идеально). Skill > 0 — лучше, чем",
        "всегда называть среднюю частоту разрывов. В хорошо откалиброванной модели предсказанная",
        "вероятность в каждой корзине близка к фактической частоте.",
        "",
        *_reliability(calibration.horizon, "Разрыв за 30 дней"),
        *_reliability(calibration.daily, "Остаток ниже резерва в конкретный день"),
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--out", default="docs/backtest/baseline.md")
    args = parser.parse_args()
    results, calibration = evaluate(args.seeds)
    text = render(results, calibration, args.seeds)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
