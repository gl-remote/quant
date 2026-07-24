from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from backtest import VnpyBacktestEngine, load_strategy_and_config
from cli.workflows.backtests_run import get_git_hash
from config import ConfigManager
from data import DataManager
from data.output_paths import project_data_root
from strategies.runtime.aggregate import parse_period_minutes

Symbol = str
RandomMode = Literal["same", "random"]
TrialMode = Literal["structure", "same", "random"]

DEFAULT_SYMBOL = "DCE.m2601"
RANDOM_PARAM_KEYS = {"random_seed", "random_baseline_mode", "random_direction_mode", "random_entry_probability"}


@dataclass(frozen=True)
class ExperimentConfig:
    key: str
    symbol: Symbol
    structure_strategy: str
    random_strategy: str
    params: dict[str, Any]


@dataclass(frozen=True)
class TrialResult:
    experiment: str
    strategy: str
    seed: int
    mode: TrialMode
    total_return: float
    total_net_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    win_trades: int
    loss_trades: int
    total_trades: int
    avg_win: float
    avg_loss: float
    win_loss_ratio: float
    total_commission: float
    total_slippage: float
    success: bool
    error: str


EXPERIMENT_CONFIGS: dict[str, ExperimentConfig] = {
    "prevday": ExperimentConfig(
        key="prevday",
        symbol=DEFAULT_SYMBOL,
        structure_strategy="prevday_reacceptance",
        random_strategy="prevday_random_baseline",
        params={
            "kline_period": "5m",
            "min_breakout_ticks": 2,
            "failure_buffer_ticks": 1,
            "take_profit_mode": "mid",
            "max_hold_bars": 12,
            "strict_close_exit": True,
            "max_trades_per_day": 1,
            "random_baseline_mode": "direction_matched",
            "random_entry_probability": 1.0,
        },
    ),
    "volume_shock": ExperimentConfig(
        key="volume_shock",
        symbol=DEFAULT_SYMBOL,
        structure_strategy="volume_shock_boundary",
        random_strategy="volume_shock_random_baseline",
        params={
            "kline_period": "5m",
            "volume_lookback": 20,
            "volume_multiplier": 2.5,
            "range_lookback": 20,
            "range_multiplier": 1.2,
            "min_body_ratio": 0.5,
            "shock_valid_bars": 12,
            "min_breakout_ticks": 1,
            "failure_buffer_ticks": 1,
            "take_profit_mode": "mid",
            "max_hold_bars": 12,
            "strict_close_exit": True,
            "max_trades_per_day": 1,
            "random_baseline_mode": "direction_matched",
            "random_entry_probability": 1.0,
        },
    ),
    "prevday_volume": ExperimentConfig(
        key="prevday_volume",
        symbol=DEFAULT_SYMBOL,
        structure_strategy="prevday_volume_filter",
        random_strategy="prevday_volume_random_baseline",
        params={
            "kline_period": "5m",
            "min_breakout_ticks": 2,
            "failure_buffer_ticks": 1,
            "take_profit_mode": "mid",
            "max_hold_bars": 12,
            "strict_close_exit": True,
            "max_trades_per_day": 1,
            "volume_filter_enabled": True,
            "volume_filter_stage": "breakout",
            "volume_lookback": 20,
            "volume_multiplier": 2.0,
            "range_lookback": 20,
            "range_multiplier": 1.0,
            "min_body_ratio": 0.0,
            "random_baseline_mode": "direction_matched",
            "random_entry_probability": 1.0,
        },
    ),
    "hourly_liquidity": ExperimentConfig(
        key="hourly_liquidity",
        symbol=DEFAULT_SYMBOL,
        structure_strategy="hourly_liquidity_sweep",
        random_strategy="hourly_liquidity_random_baseline",
        params={
            "kline_period": "5m",
            "structure_period": "1h",
            "lookback_hours": 24,
            "touch_tolerance_ticks": 4,
            "min_touches": 2,
            "min_breakout_ticks": 2,
            "failure_buffer_ticks": 1,
            "reaccept_mode": "band_inner",
            "take_profit_mode": "r",
            "take_profit_r": 1.0,
            "max_hold_bars": 12,
            "strict_close_exit": True,
            "max_trades_per_day": 1,
            "volatility_filter_enabled": False,
            "random_baseline_mode": "direction_matched",
            "random_entry_probability": 1.0,
        },
    ),
    "low_volatility": ExperimentConfig(
        key="low_volatility",
        symbol=DEFAULT_SYMBOL,
        structure_strategy="low_volatility_restart",
        random_strategy="low_volatility_random_baseline",
        params={
            "kline_period": "5m",
            "atr_lookback": 14,
            "impulse_lookback": 12,
            "compression_bars": 6,
            "min_impulse_atr": 1.5,
            "min_impulse_body_ratio": 0.5,
            "max_compression_width_atr": 1.0,
            "max_compression_bar_range_atr": 0.45,
            "min_breakout_ticks": 1,
            "failure_buffer_ticks": 1,
            "direction_mode": "breakout",
            "take_profit_r": 1.0,
            "max_hold_bars": 12,
            "strict_close_exit": True,
            "max_trades_per_day": 1,
            "random_entry_probability": 1.0,
        },
    ),
}


def main() -> None:
    args = _parse_args()
    experiments = _selected_experiments(args.experiments)
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    output_dir = project_data_root() / "research" / "random_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    structure_results = {experiment.key: _run_structure_baseline(experiment) for experiment in experiments}
    random_rows: list[TrialResult] = []
    jobs = [(experiment.key, seed, mode) for experiment in experiments for mode in args.modes for seed in seeds]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(_run_trial, experiment_key, seed, mode) for experiment_key, seed, mode in jobs]
        for future in as_completed(futures):
            random_rows.append(future.result())

    random_rows.sort(key=lambda row: (row.experiment, row.mode, row.seed))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"structural_random_baselines_{timestamp}.csv"
    summary_path = output_dir / f"structural_random_baselines_{timestamp}.json"
    _write_csv(csv_path, [*structure_results.values(), *random_rows])
    summary = _build_summary(experiments, structure_results, random_rows)
    summary.update(
        {
            "seeds": seeds,
            "modes": args.modes,
            "workers": args.workers,
            "git_hash": get_git_hash(),
            "csv_path": str(csv_path),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"CSV: {csv_path}")
    print(f"Summary: {summary_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run structural random baseline multi-seed research")
    parser.add_argument(
        "--experiments", choices=sorted(EXPERIMENT_CONFIGS), nargs="+", default=sorted(EXPERIMENT_CONFIGS)
    )
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--modes", choices=["same", "random"], nargs="+", default=["same", "random"])
    return parser.parse_args()


def _selected_experiments(keys: Sequence[str]) -> list[ExperimentConfig]:
    return [EXPERIMENT_CONFIGS[key] for key in keys]


def _run_structure_baseline(experiment: ExperimentConfig) -> TrialResult:
    return _run_backtest(
        experiment,
        experiment.structure_strategy,
        _structure_params(experiment.params),
        seed=0,
        mode="structure",
    )


def _run_trial(experiment_key: str, seed: int, mode: RandomMode) -> TrialResult:
    experiment = EXPERIMENT_CONFIGS[experiment_key]
    params = {
        **experiment.params,
        "random_seed": seed,
        "random_direction_mode": mode,
    }
    return _run_backtest(experiment, experiment.random_strategy, params, seed=seed, mode=mode)


def _run_backtest(
    experiment: ExperimentConfig,
    strategy: str,
    params: dict[str, Any],
    seed: int,
    mode: TrialMode,
) -> TrialResult:
    try:
        cm = ConfigManager(env="backtest")
        dm = DataManager(cm)
        bc = cm.get_backtest_config()
        interval = _required_interval(strategy, params, bc.interval)
        bc = bc.model_copy(update={"interval": interval})
        datasets = dm.load_kline([experiment.symbol], None, None, interval)
        if not datasets:
            raise RuntimeError(f"数据加载失败: {experiment.symbol} {interval}")
        symbol, df, _ = datasets[0]
        engine = VnpyBacktestEngine(bc)
        engine.set_git_hash(get_git_hash())
        result = engine.run([(symbol, df, strategy, params)], batch_mode=True)[0]
        return _to_trial_result(result, experiment=experiment.key, strategy=strategy, seed=seed, mode=mode)
    except Exception as exc:
        return TrialResult(
            experiment=experiment.key,
            strategy=strategy,
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


def _structure_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if key not in RANDOM_PARAM_KEYS}


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


def _to_trial_result(result: Any, experiment: str, strategy: str, seed: int, mode: TrialMode) -> TrialResult:
    return TrialResult(
        experiment=experiment,
        strategy=strategy,
        seed=seed,
        mode=mode,
        total_return=float(result.total_return or 0.0),
        total_net_pnl=float(result.total_net_pnl or 0.0),
        max_drawdown=float(result.max_drawdown or 0.0),
        sharpe_ratio=float(result.sharpe_ratio or 0.0),
        win_rate=float(result.win_rate or 0.0),
        win_trades=int(result.win_trades or 0),
        loss_trades=int(result.loss_trades or 0),
        total_trades=int(result.total_trades or 0),
        avg_win=float(result.avg_win or 0.0),
        avg_loss=float(result.avg_loss or 0.0),
        win_loss_ratio=float(result.win_loss_ratio or 0.0),
        total_commission=float(result.total_commission or 0.0),
        total_slippage=float(result.total_slippage or 0.0),
        success=bool(result.success),
        error=result.error_message or "",
    )


def _write_csv(path: Path, rows: list[TrialResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[field.name for field in fields(TrialResult)])
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def _build_summary(
    experiments: list[ExperimentConfig],
    structure_results: dict[str, TrialResult],
    rows: list[TrialResult],
) -> dict[str, Any]:
    experiment_summaries: dict[str, Any] = {}
    for experiment in experiments:
        structure = structure_results[experiment.key]
        experiment_rows = [row for row in rows if row.experiment == experiment.key]
        grouped = {
            mode: [row for row in experiment_rows if row.mode == mode and row.success] for mode in ("same", "random")
        }
        experiment_summaries[experiment.key] = {
            "symbol": experiment.symbol,
            "structure_strategy": experiment.structure_strategy,
            "random_strategy": experiment.random_strategy,
            "structure_params": _structure_params(experiment.params),
            "random_base_params": experiment.params,
            "structure": structure.__dict__,
            "same_direction": _summarize_group(grouped["same"], structure),
            "random_direction": _summarize_group(grouped["random"], structure),
            "failures": [row.__dict__ for row in experiment_rows if not row.success],
        }
    return {
        "experiments": experiment_summaries,
        "failures": [row.__dict__ for row in rows if not row.success]
        + [row.__dict__ for row in structure_results.values() if not row.success],
    }


def _summarize_group(rows: list[TrialResult], structure: TrialResult) -> dict[str, Any]:
    returns = [row.total_return for row in rows]
    pnls = [row.total_net_pnl for row in rows]
    drawdowns = [row.max_drawdown for row in rows]
    win_rates = [row.win_rate for row in rows]
    trades = [row.total_trades for row in rows]
    return {
        "count": len(rows),
        "return_mean": _mean(returns),
        "return_median": _median(returns),
        "return_p25": _quantile(returns, 0.25),
        "return_p75": _quantile(returns, 0.75),
        "structure_return_percentile": _percentile_rank(returns, structure.total_return),
        "net_pnl_mean": _mean(pnls),
        "net_pnl_median": _median(pnls),
        "net_pnl_p25": _quantile(pnls, 0.25),
        "net_pnl_p75": _quantile(pnls, 0.75),
        "structure_net_pnl_percentile": _percentile_rank(pnls, structure.total_net_pnl),
        "max_drawdown_mean": _mean(drawdowns),
        "max_drawdown_median": _median(drawdowns),
        "structure_drawdown_percentile": _percentile_rank(drawdowns, structure.max_drawdown),
        "win_rate_mean": _mean(win_rates),
        "win_rate_median": _median(win_rates),
        "structure_win_rate_edge_mean": structure.win_rate - _mean(win_rates),
        "structure_win_rate_edge_median": structure.win_rate - _median(win_rates),
        "trade_count_mean": _mean(trades),
        "trade_count_median": _median(trades),
    }


def _mean(values: Sequence[float | int]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def _median(values: Sequence[float | int]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return float(ordered[index])


def _percentile_rank(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    below_or_equal = sum(1 for item in values if item <= value)
    return below_or_equal / len(values) * 100


if __name__ == "__main__":
    main()
