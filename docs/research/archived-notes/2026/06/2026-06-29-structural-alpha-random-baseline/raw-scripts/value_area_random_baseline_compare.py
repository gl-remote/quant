from __future__ import annotations

# 文件级元信息：
# - 创建背景：R29 需要多 seed 随机入场复验，CLI 单次回测会触发报告构建，不适合批量结构基准对比。
# - 用途：轻量运行 value_area_reacceptance_baseline 与 value_area_random_baseline 的同 runner 相对比较，并输出 CSV/JSON 摘要。
# - 注意事项：输出指标使用 vnpy BacktestResult 口径，只用于同一 runner 内部比较，不替代 trade_clearings 清算口径。
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

RandomMode = Literal["same", "random"]
TrialMode = Literal["structure", "same", "random"]

RANDOM_PARAM_KEYS = {
    "random_seed",
    "random_baseline_mode",
    "random_direction_mode",
    "random_entry_probability",
    "random_breakout_extra_ticks",
}

R29_PARAMS: dict[str, Any] = {
    "kline_period": "1m",
    "profile_mode": "close",
    "value_area_ratio": 0.7,
    "min_breakout_ticks": 4,
    "failure_buffer_ticks": 1,
    "strict_close_exit": True,
    "take_profit_mode": "poc",
    "target_distance_ratio": 0.8,
    "target_band_ticks": 0,
    "min_reaccept_ticks": 3,
    "min_reaccept_va_width_ratio": 0,
    "max_hold_bars": 60,
    "stop_widen_multiplier": 1.0,
    "min_target_ticks": 8,
    "min_price_raw_rr": 0.8,
    "max_trades_per_day": 3,
    "reentry_cooldown_minutes": 15,
    "reentry_requires_prev_stop_same_direction": True,
    "reentry_take_profit_r": 1.3,
    "random_baseline_mode": "direction_matched",
    "random_entry_probability": 1.0,
    "random_breakout_extra_ticks": 10,
}


@dataclass(frozen=True)
class TrialResult:
    symbol: str
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


def main() -> None:
    args = _parse_args()
    symbols = args.symbols
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    modes = args.modes

    output_dir = project_data_root() / "research" / "random_baseline"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[TrialResult] = []
    rows.extend(_run_structure(symbol) for symbol in symbols)

    jobs = [(symbol, seed, mode) for symbol in symbols for mode in modes for seed in seeds]
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(_run_random, symbol, seed, mode) for symbol, seed, mode in jobs]
        for future in as_completed(futures):
            rows.append(future.result())

    rows.sort(key=lambda row: (row.symbol, row.mode, row.seed))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"value_area_random_baseline_compare_{timestamp}.csv"
    summary_path = output_dir / f"value_area_random_baseline_compare_{timestamp}.json"
    _write_csv(csv_path, rows)
    summary = _build_summary(symbols, rows)
    summary.update(
        {
            "symbols": symbols,
            "seeds": seeds,
            "modes": modes,
            "workers": args.workers,
            "structure_strategy": "value_area_reacceptance_baseline",
            "random_strategy": "value_area_random_baseline",
            "params": R29_PARAMS,
            "git_hash": get_git_hash(),
            "csv_path": str(csv_path),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"CSV: {csv_path}")
    print(f"Summary: {summary_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare value_area_reacceptance_baseline against value_area_random_baseline"
    )
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--modes", choices=["same", "random"], nargs="+", default=["same", "random"])
    return parser.parse_args()


def _run_structure(symbol: str) -> TrialResult:
    return _run_backtest(
        symbol, "value_area_reacceptance_baseline", _structure_params(R29_PARAMS), seed=0, mode="structure"
    )


def _run_random(symbol: str, seed: int, mode: RandomMode) -> TrialResult:
    params = {
        **R29_PARAMS,
        "random_seed": seed,
        "random_direction_mode": mode,
    }
    return _run_backtest(symbol, "value_area_random_baseline", params, seed=seed, mode=mode)


def _run_backtest(
    symbol: str,
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
        datasets = dm.load_kline([symbol], None, None, interval)
        if not datasets:
            raise RuntimeError(f"数据加载失败: {symbol} {interval}")
        loaded_symbol, df, _ = datasets[0]
        engine = VnpyBacktestEngine(bc)
        engine.set_git_hash(get_git_hash())
        result = engine.run([(loaded_symbol, df, strategy, params)], batch_mode=True)[0]
        return _to_trial_result(result, symbol=loaded_symbol, strategy=strategy, seed=seed, mode=mode)
    except Exception as exc:
        return TrialResult(
            symbol=symbol,
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


def _to_trial_result(result: Any, symbol: str, strategy: str, seed: int, mode: TrialMode) -> TrialResult:
    return TrialResult(
        symbol=symbol,
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


def _build_summary(symbols: Sequence[str], rows: list[TrialResult]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for symbol in symbols:
        symbol_rows = [row for row in rows if row.symbol == symbol]
        structure = next((row for row in symbol_rows if row.mode == "structure"), None)
        grouped = {
            mode: [row for row in symbol_rows if row.mode == mode and row.success] for mode in ("same", "random")
        }
        summaries[symbol] = {
            "structure": structure.__dict__ if structure else None,
            "same_direction": _summarize_group(grouped["same"], structure),
            "random_direction": _summarize_group(grouped["random"], structure),
            "failures": [row.__dict__ for row in symbol_rows if not row.success],
        }
    all_structure = [row for row in rows if row.mode == "structure" and row.success]
    return {
        "symbols_summary": summaries,
        "portfolio_structure": _summarize_portfolio(all_structure),
        "portfolio_same_direction": _summarize_portfolio([row for row in rows if row.mode == "same" and row.success]),
        "portfolio_random_direction": _summarize_portfolio(
            [row for row in rows if row.mode == "random" and row.success]
        ),
        "failures": [row.__dict__ for row in rows if not row.success],
    }


def _summarize_group(rows: list[TrialResult], structure: TrialResult | None) -> dict[str, Any]:
    pnls = [row.total_net_pnl for row in rows]
    returns = [row.total_return for row in rows]
    drawdowns = [row.max_drawdown for row in rows]
    win_rates = [row.win_rate for row in rows]
    trades = [row.total_trades for row in rows]
    return {
        "count": len(rows),
        "net_pnl_mean": _mean(pnls),
        "net_pnl_median": _median(pnls),
        "net_pnl_p25": _quantile(pnls, 0.25),
        "net_pnl_p75": _quantile(pnls, 0.75),
        "structure_net_pnl_percentile": _percentile_rank(pnls, structure.total_net_pnl) if structure else 0.0,
        "return_mean": _mean(returns),
        "return_median": _median(returns),
        "max_drawdown_mean": _mean(drawdowns),
        "max_drawdown_median": _median(drawdowns),
        "structure_drawdown_percentile": _percentile_rank(drawdowns, structure.max_drawdown) if structure else 0.0,
        "win_rate_mean": _mean(win_rates),
        "win_rate_median": _median(win_rates),
        "structure_win_rate_edge_mean": structure.win_rate - _mean(win_rates) if structure else 0.0,
        "structure_win_rate_edge_median": structure.win_rate - _median(win_rates) if structure else 0.0,
        "trade_count_mean": _mean(trades),
        "trade_count_median": _median(trades),
    }


def _summarize_portfolio(rows: list[TrialResult]) -> dict[str, Any]:
    pnls = [row.total_net_pnl for row in rows]
    return {
        "count": len(rows),
        "net_pnl_sum": sum(pnls),
        "net_pnl_mean": _mean(pnls),
        "net_pnl_median": _median(pnls),
        "win_rate_mean": _mean([row.win_rate for row in rows]),
        "trade_count_sum": sum(row.total_trades for row in rows),
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
