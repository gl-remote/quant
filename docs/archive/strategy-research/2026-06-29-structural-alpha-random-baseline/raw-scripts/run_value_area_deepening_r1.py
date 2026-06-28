from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from cli.workflows.backtests_run import get_git_hash
from data.output_paths import project_data_root
from run_value_area_random_baseline import (
    BASE_PARAMS,
    STRATEGY,
    STRUCTURE_PARAMS,
    SYMBOL,
    Mode,
    TrialResult,
    _build_summary,
    _run_backtest,
)


@dataclass(frozen=True)
class VariantConfig:
    name: str
    description: str
    params: dict[str, Any]


VARIANTS: list[VariantConfig] = [
    VariantConfig(
        name="baseline",
        description="r2 原始口径：VAH/VAL 重新接受 + POC 目标 + 空间/RR 预筛",
        params={},
    ),
    VariantConfig(
        name="quick_reaccept",
        description="只保留边界外停留不超过 1 根 K 的快速重新接受",
        params={"max_breakout_bars": 1},
    ),
    VariantConfig(
        name="deep_reaccept",
        description="重新接受必须至少收回边界内 2 ticks",
        params={"min_reaccept_ticks": 2},
    ),
    VariantConfig(
        name="quick_deep_reaccept",
        description="快速重新接受 + 至少收回边界内 2 ticks",
        params={"max_breakout_bars": 1, "min_reaccept_ticks": 2},
    ),
]


def main() -> None:
    args = _parse_args()
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    output_dir = project_data_root() / "research" / "random_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = [variant for variant in VARIANTS if not args.variants or variant.name in args.variants]
    summaries: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    for variant in selected:
        structure_params = {**STRUCTURE_PARAMS, **variant.params}
        random_base_params = {**BASE_PARAMS, **variant.params}
        structure = _run_backtest("value_area_reacceptance", structure_params, seed=0, mode="same")
        rows = _run_random_trials(random_base_params, seeds, args.workers, args.modes)
        summary = _build_summary(structure, rows)
        summary.update(
            {
                "description": variant.description,
                "params_override": variant.params,
                "structure_params": structure_params,
                "random_base_params": random_base_params,
            }
        )
        summaries[variant.name] = summary
        for row in rows:
            row_dict = asdict(row)
            row_dict["variant"] = variant.name
            all_rows.append(row_dict)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"value_area_deepening_r1_{timestamp}.csv"
    summary_path = output_dir / f"value_area_deepening_r1_{timestamp}.json"
    _write_csv(csv_path, all_rows)
    output = {
        "symbol": SYMBOL,
        "strategy": STRATEGY,
        "seeds": seeds,
        "modes": args.modes,
        "workers": args.workers,
        "git_hash": get_git_hash(),
        "csv_path": str(csv_path),
        "variants": summaries,
    }
    summary_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"CSV: {csv_path}")
    print(f"Summary: {summary_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run value area deepening r1 random-baseline variants")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--modes", choices=["same", "random"], nargs="+", default=["same", "random"])
    parser.add_argument("--variants", choices=[variant.name for variant in VARIANTS], nargs="+")
    return parser.parse_args()


def _run_random_trials(
    base_params: dict[str, Any],
    seeds: list[int],
    workers: int,
    modes: list[Mode],
) -> list[TrialResult]:
    rows: list[TrialResult] = []
    jobs = [(seed, mode) for mode in modes for seed in seeds]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_run_trial, base_params, seed, mode) for seed, mode in jobs]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: (row.mode, row.seed))
    return rows


def _run_trial(base_params: dict[str, Any], seed: int, mode: Mode) -> TrialResult:
    params = {
        **base_params,
        "random_seed": seed,
        "random_direction_mode": mode,
    }
    return _run_backtest(STRATEGY, params, seed=seed, mode=mode)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["variant", *TrialResult.__dataclass_fields__]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__ == "__main__":
    main()
