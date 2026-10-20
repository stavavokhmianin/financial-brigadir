"""Бэктест базового прогноза на синтетике (раздел 15.2, критерий 19.12).

    python scripts/backtest_baseline.py [--seeds 30] [--out docs/backtest/baseline.md]

Сравнивает три модели на одних и тех же профилях и периодах:
  A — только календарь подтверждённых событий (без повседневных трат);
  B — календарь + медиана трат по дням недели (baseline из ТЗ);
  M — модель baseline-0.1: календарь + среднее трат по дням недели без аномалий.

Модель видит только ``known`` (данные на дату прогноза); оценка — по
``hidden_future``. Синтетика не доказывает качество на реальных данных (12.1).
"""

import argparse
import statistics
from dataclasses import dataclass
from pathlib import Path

from forecast_core.adapters import actual_liquid_path, snapshot_from_dataset
from forecast_core.baseline import run_baseline
from synthetic_generator import PROFILES, generate

HORIZON = 30
RESERVE = 500_000
MODELS = {
    "A": ("Календарь", {"without_spending": True}, "median"),
    "B": ("Календарь + медиана по дням недели", {}, "median"),
    "M": ("baseline-0.1 (среднее без аномалий)", {}, "mean"),
}


@dataclass
class Score:
    mae: list[float]
    bias: list[float]
    coverage: list[float]
    hits: int = 0  # реальный разрыв предсказан (risk ≥ medium)
    misses: int = 0  # реальный разрыв не предсказан
    false_alarms: int = 0  # предупреждение без реального разрыва
    quiet: int = 0  # нет ни разрыва, ни предупреждения


def evaluate(seeds: int) -> dict[str, dict[str, Score]]:
    results: dict[str, dict[str, Score]] = {}
    for profile_id, info in PROFILES.items():
        if not info.mvp:
            continue
        results[profile_id] = {key: Score([], [], []) for key in MODELS}
        for seed in range(1, seeds + 1):
            data = generate(profile_id, seed=seed)
            actual = actual_liquid_path(data, HORIZON)
            breached = min(actual.values()) < RESERVE
            for key, (_, snapshot_kwargs, estimator) in MODELS.items():
                snapshot = snapshot_from_dataset(data, RESERVE, HORIZON, **snapshot_kwargs)
                result = run_baseline(snapshot, estimator=estimator)  # type: ignore[arg-type]
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
                else:
                    score.quiet += 1
    return results


def _rub(minor: float) -> str:
    return f"{minor / 100:,.0f}".replace(",", " ")


def render(results: dict[str, dict[str, Score]], seeds: int) -> str:
    lines = [
        "# Бэктест базового прогноза",
        "",
        "Сгенерировано `scripts/backtest_baseline.py`. Горизонт 30 дней, резерв 5 000 ₽,",
        f"{seeds} профилей каждого типа (seed 1…{seeds}), дата прогноза 19.10.2026.",
        "Модель видит только данные на дату прогноза, оценка идёт по скрытому будущему генератора.",
        "",
        "> Это синтетика: результат проверяет корректность расчёта, но не доказывает качество",
        "> на реальном поведении людей (раздел 12.1).",
        "",
        "Модели: " + "; ".join(f"**{k}** — {v[0]}" for k, v in MODELS.items()) + ".",
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
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--out", default="docs/backtest/baseline.md")
    args = parser.parse_args()
    text = render(evaluate(args.seeds), args.seeds)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
