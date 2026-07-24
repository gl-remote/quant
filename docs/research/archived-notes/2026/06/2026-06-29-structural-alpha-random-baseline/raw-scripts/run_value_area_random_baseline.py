from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from backtest import VnpyBacktestEngine, load_strategy_and_config
from cli.workflows.backtests_run import get_git_hash
from config import ConfigManager
from data import DataManager
from data.output_paths import project_data_root
from strategies.runtime.aggregate import parse_period_minutes

Mode = Literal["same", "random"]

SYMBOL = "DCE.m2601"
STRATEGY = "value_area_random_baseline"

BASE_PARAMS: dict[str, Any] = {
    "kline_period": "5m",
    "profile_mode": "close",
    "value_area_ratio": 0.7,
    "min_breakout_ticks": 4,
    "failure_buffer_ticks": 1,
    "take_profit_mode": "poc",
    "max_hold_bars": 12,
    "stop_widen_multiplier": 1.5,
    "strict_close_exit": True,
    "max_trades_per_day": 1,
    "min_target_ticks": 8,
    "min_price_raw_rr": 0.5,
    "random_baseline_mode": "direction_matched",
    "random_entry_probability": 1.0,
}

STRUCTURE_PARAMS: dict[str, Any] = {key: value for key, value in BASE_PARAMS.items() if not key.startswith("random_")}


@dataclass(frozen=True)
class TrialResult:
    seed: int
    mode: Mode
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


def main() -> None:
    args = _parse_args()
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    output_dir = project_data_root() / "research" / "random_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    structure = _run_structure_baseline()
    rows: list[TrialResult] = []
    jobs = [(seed, mode) for mode in args.modes for seed in seeds]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(_run_trial, seed, mode) for seed, mode in jobs]
        for future in as_completed(futures):
            rows.append(future.result())

    rows.sort(key=lambda row: (row.mode, row.seed))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"value_area_random_baseline_r2_{timestamp}.csv"
    summary_path = output_dir / f"value_area_random_baseline_r2_{timestamp}.json"
    _write_csv(csv_path, rows)
    summary = _build_summary(structure, rows)
    summary.update(
        {
            "symbol": SYMBOL,
            "strategy": STRATEGY,
            "seeds": seeds,
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
    parser = argparse.ArgumentParser(description="Run value area random baseline multi-seed research")
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--modes", choices=["same", "random"], nargs="+", default=["same", "random"])
    return parser.parse_args()


def _run_structure_baseline() -> TrialResult:
    return _run_backtest("value_area_reacceptance", STRUCTURE_PARAMS, seed=0, mode="same")


def _run_trial(seed: int, mode: Mode) -> TrialResult:
    params = {
        **BASE_PARAMS,
        "random_seed": seed,
        "random_direction_mode": mode,
    }
    return _run_backtest(STRATEGY, params, seed=seed, mode=mode)


def _run_backtest(strategy: str, params: dict[str, Any], seed: int, mode: Mode) -> TrialResult:
    try:
        cm = ConfigManager(env="backtest")
        dm = DataManager(cm)
        bc = cm.get_backtest_config()
        interval = _required_interval(strategy, params, bc.interval)
        bc = bc.model_copy(update={"interval": interval})
        datasets = dm.load_kline([SYMBOL], None, None, interval)
        if not datasets:
            raise RuntimeError(f"数据加载失败: {SYMBOL} {interval}")
        symbol, df, _ = datasets[0]
        engine = VnpyBacktestEngine(bc)
        engine.set_git_hash(get_git_hash())
        result = engine.run([(symbol, df, strategy, params)], batch_mode=True)[0]
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


def _to_trial_result(result: Any, seed: int, mode: Mode) -> TrialResult:
    return TrialResult(
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
        writer = csv.DictWriter(f, fieldnames=list(TrialResult.__dataclass_fields__))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def _build_summary(structure: TrialResult, rows: list[TrialResult]) -> dict[str, Any]:
    grouped = {mode: [row for row in rows if row.mode == mode and row.success] for mode in ("same", "random")}
    return {
        "structure": structure.__dict__,
        "same_direction": _summarize_group(grouped["same"], structure),
        "random_direction": _summarize_group(grouped["random"], structure),
        "failures": [row.__dict__ for row in rows if not row.success],
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
        "net_pnl_mean": _mean(pnls),
        "net_pnl_median": _median(pnls),
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
