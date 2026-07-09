from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backtest import VnpyBacktestEngine, load_strategy_and_config
from cli.workflows.backtests_run import get_git_hash
from config import ConfigManager
from data import DataManager
from data.output_paths import project_data_root
from run_value_area_random_baseline import (
    BASE_PARAMS,
    STRATEGY,
    STRUCTURE_PARAMS,
    Mode,
    TrialResult,
    _build_summary,
    _to_trial_result,
)
from strategies.runtime.aggregate import parse_period_minutes


@dataclass(frozen=True)
class ExperimentConfig:
    symbol: str
    min_reaccept_ticks: int


def main() -> None:
    args = _parse_args()
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    output_dir = project_data_root() / "research" / "random_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    experiments = [
        ExperimentConfig(symbol=symbol, min_reaccept_ticks=ticks)
        for symbol in args.symbols
        for ticks in args.min_reaccept_ticks
    ]
    summaries: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    for experiment in experiments:
        key = f"{experiment.symbol}_reaccept_{experiment.min_reaccept_ticks}"
        structure_params = {**STRUCTURE_PARAMS, "min_reaccept_ticks": experiment.min_reaccept_ticks}
        random_base_params = {**BASE_PARAMS, "min_reaccept_ticks": experiment.min_reaccept_ticks}
        structure = _run_backtest_for_symbol(
            symbol=experiment.symbol,
            strategy="value_area_reacceptance",
            params=structure_params,
            seed=0,
            mode="same",
        )
        rows = _run_random_trials(
            symbol=experiment.symbol,
            base_params=random_base_params,
            seeds=seeds,
            workers=args.workers,
        )
        summary = _build_summary(structure, rows)
        summary.update(
            {
                "symbol": experiment.symbol,
                "min_reaccept_ticks": experiment.min_reaccept_ticks,
                "structure_params": structure_params,
                "random_base_params": random_base_params,
            }
        )
        summaries[key] = summary
        for row in rows:
            row_dict = asdict(row)
            row_dict["symbol"] = experiment.symbol
            row_dict["min_reaccept_ticks"] = experiment.min_reaccept_ticks
            all_rows.append(row_dict)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"value_area_deepening_r2_{timestamp}.csv"
    summary_path = output_dir / f"value_area_deepening_r2_{timestamp}.json"
    _write_csv(csv_path, all_rows)
    output = {
        "strategy": STRATEGY,
        "symbols": args.symbols,
        "min_reaccept_ticks": args.min_reaccept_ticks,
        "seeds": seeds,
        "modes": ["same"],
        "workers": args.workers,
        "git_hash": get_git_hash(),
        "csv_path": str(csv_path),
        "experiments": summaries,
    }
    summary_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"CSV: {csv_path}")
    print(f"Summary: {summary_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run value area deepening r2 robustness checks")
    parser.add_argument("--symbols", nargs="+", default=["DCE.m2601", "CZCE.SR601"])
    parser.add_argument("--min-reaccept-ticks", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def _run_random_trials(
    symbol: str,
    base_params: dict[str, Any],
    seeds: list[int],
    workers: int,
) -> list[TrialResult]:
    rows: list[TrialResult] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_run_trial, symbol, base_params, seed) for seed in seeds]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row.seed)
    return rows


def _run_trial(symbol: str, base_params: dict[str, Any], seed: int) -> TrialResult:
    params = {
        **base_params,
        "random_seed": seed,
        "random_direction_mode": "same",
    }
    return _run_backtest_for_symbol(symbol=symbol, strategy=STRATEGY, params=params, seed=seed, mode="same")


def _run_backtest_for_symbol(
    symbol: str,
    strategy: str,
    params: dict[str, Any],
    seed: int,
    mode: Mode,
) -> TrialResult:
    try:
        cm = ConfigManager(env="backtest")
        dm = DataManager(cm)
        bc = cm.get_backtest_config()
        interval = _required_interval(strategy, params, bc.interval)
        bc = bc.model_copy(update={"interval": interval})
        datasets = dm.load_kline([symbol], None, None, interval)
        if not datasets:
            raise RuntimeError(f"数据加载失败: {symbol} {interval}")
        loaded_symbol, df, _ = datasets[0]
        engine = VnpyBacktestEngine(bc)
        engine.set_git_hash(get_git_hash())
        result = engine.run([(loaded_symbol, df, strategy, params)], batch_mode=True)[0]
        return _to_trial_result(result, seed=seed, mode=mode)
    except Exception as exc:
        return TrialResult(
            seed=seed,
            mode=mode,
            total_return=0.0,
            total_net_pnl=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            win_rate=0.0,
            win_trades=0,
            loss_trades=0,
            total_trades=0,
            avg_win=0.0,
            avg_loss=0.0,
            win_loss_ratio=0.0,
            total_commission=0.0,
            total_slippage=0.0,
            success=False,
            error=str(exc),
        )


def _required_interval(strategy: str, params: dict[str, Any], default_interval: str) -> str:
    strategy_cls, strategy_config = load_strategy_and_config(strategy, params)
    requirements = strategy_cls().data_requirements(strategy_config)
    if requirements is None:
        return default_interval
    all_periods = set(requirements.periods)
    for period in requirements.indicators:
        all_periods.add(period)
    if not all_periods:
        return default_interval
    required_interval = min(all_periods, key=parse_period_minutes)
    if parse_period_minutes(default_interval) > parse_period_minutes(required_interval):
        return required_interval
    return default_interval


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["symbol", "min_reaccept_ticks", *TrialResult.__dataclass_fields__]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__ == "__main__":
    main()
