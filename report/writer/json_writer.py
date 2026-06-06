"""JSON 数据写入器

提供各类数据的 JSON 导出功能
"""

import json
from loguru import logger
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

from data import DataManager
from report.cache import KlineCache

# 全局数据管理器实例（按需创建）
_data_manager: DataManager | None = None

def get_data_manager() -> DataManager:
    """获取数据管理器实例"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager

def export_run_json(output_dir: str, run_id: int) -> None:
    """
    导出单次 run 的元信息到 JSON 文件
    
    Args:
        output_dir: 输出目录
        run_id: 运行ID
    """
    dm = get_data_manager()
    row = dm.get_run_info(run_id)

    if not row:
        logger.warning("run_id=%d 不存在", run_id)
        return

    data = {
        "id": row["id"],
        "strategy": row["strategy"],
        "engine": row["engine"],
        "symbols": row["symbols"],
        "status": row["status"],
        "created_at": row["created_at"],
    }
    _write_json(output_dir, f"r{run_id}/data/run.json", data)


def export_summary_json(output_dir: str, run_id: int) -> None:
    """
    导出品汇总表（每品种最优回测记录）
    
    Args:
        output_dir: 输出目录
        run_id: 运行ID
    """
    dm = get_data_manager()
    data = dm.get_run_summary(run_id)
    _write_json(output_dir, f"r{run_id}/data/summary.json", data)


def export_backtests_json(output_dir: str, run_id: int) -> None:
    """
    导出所有回测记录完整信息（含指标、参数、日线数据）
    
    Args:
        output_dir: 输出目录
        run_id: 运行ID
    """
    dm = get_data_manager()
    result = dm.get_backtests_for_run(run_id)
    _write_json(output_dir, f"r{run_id}/data/backtests.json", result)


def export_equity_json(output_dir: str, run_id: int) -> None:
    """
    导出资金曲线数据（每品种最优回测的日线权益/回撤）
    
    Args:
        output_dir: 输出目录
        run_id: 运行ID
    """
    dm = get_data_manager()
    summary = dm.get_run_summary(run_id)
    result: dict[str, Any] = {}
    for s in summary:
        s_id = s.get("id")
        if not s_id:
            continue
        equity = dm.get_equity_data(int(s_id))  # type: ignore[call-overload]
        if equity:
            equity['max_ddpercent'] = s.get('max_ddpercent', 0)  # type: ignore[arg-type]
            equity['initial_capital'] = s.get('initial_capital')  # type: ignore[arg-type]
            result[str(s["symbol"])] = equity
    _write_json(output_dir, f"r{run_id}/data/equity.json", result)


def export_kline_json(output_dir: str, run_id: int) -> None:
    """
    导出 K 线数据 JSON（使用 KlineCache 避免重复转换）

    从最优回测记录获取各品种的 CSV 路径和日期范围，
    按品种独立生成 kline_{symbol}.{interval}.json。
    """
    dm = get_data_manager()
    cache = KlineCache(output_dir)
    summary = dm.get_run_summary(run_id)

    for s in summary:
        symbol: str = str(s["symbol"])
        if not s.get("id"):
            continue

        data_src = str(s.get("data_src", ""))
        start_date = str(s.get("start_date")) if s.get("start_date") else None
        end_date = str(s.get("end_date")) if s.get("end_date") else None
        interval: str = str(s.get("kline_interval") or "1m")
        dest = Path(output_dir) / f"r{run_id}/data" / f"kline_{symbol}.{interval}.json"

        if not data_src:
            continue

        if cache.copy_to(symbol, data_src, interval, dest):
            logger.info("K线缓存命中: %s", symbol)
            continue

        if not Path(data_src).exists():
            logger.warning("K线数据源不存在: %s → %s", symbol, data_src)
            continue

        kline_dict = _build_kline_dict(
            data_src, symbol, interval, start_date, end_date
        )
        if kline_dict:
            cache.put(symbol, data_src, interval, kline_dict)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(kline_dict, f, ensure_ascii=False, default=str)
            logger.info("K线已导出: %s → %s", symbol, dest.name)


def export_trades_json(output_dir: str, run_id: int) -> None:
    """
    导出交易记录 JSON（取最优参数组合的所有品种的成交记录）
    
    逻辑：从 Optuna study 中找到最优 trial，仅导出该 trial 对应各品种的 backtest 的成交。
    这样 K 线图上展示的是同一组最优参数在所有品种上的交易表现。
    
    Args:
        output_dir: 输出目录
        run_id: 运行ID
    """
    dm = get_data_manager()
    
    # 1. 从 optuna study 找最佳 trial_index
    best_trial_index = dm.store.get_best_trial_index(run_id)
    
    # 2. 遍历所有成功回测，只取最优 trial 的成交
    import json as _j
    from data.models import Backtest, BacktestTrade
    
    all_trades: dict[str, list[dict[str, Any]]] = {}
    for bt in Backtest.select(Backtest.id, Backtest.symbol, Backtest.engine_config).where(
        Backtest.run_id == run_id, Backtest.status == 'success'
    ):
        ec = bt.engine_config
        if not ec:
            continue
        if isinstance(ec, str):
            try:
                cfg = _j.loads(ec)
            except Exception:
                continue
        else:
            cfg = ec
        if cfg.get('trial_index') != best_trial_index:
            continue
        
        symbol = bt.symbol
        trades = list(BacktestTrade.select().where(BacktestTrade.backtest_id == bt.id))
        all_trades[symbol] = []
        for t in trades:
            direction = t.direction
            if "." in str(direction):
                direction = str(direction).split(".")[-1]
            offset = t.offset
            if "." in str(offset):
                offset = str(offset).split(".")[-1]
            all_trades[symbol].append({
                'datetime': t.datetime,
                'symbol': t.symbol,
                'direction': direction,
                'offset': offset,
                'open_price': t.open_price,
                'close_price': t.close_price,
                'quantity': t.quantity,
                'pnl': t.pnl,
                'commission': t.commission,
                'reason': t.reason if hasattr(t, 'reason') else '',
            })
    
    _write_json(output_dir, f"r{run_id}/data/trades.json", all_trades)


def export_optuna_json(output_dir: str, run_id: int) -> None:
    """
    导出 Optuna 优化数据 JSON（含图表配置）
    
    Args:
        output_dir: 输出目录
        run_id: 运行ID
    """
    import os
    dm = get_data_manager()
    optuna_data = dm.get_optuna_data(run_id)
    if not optuna_data:
        return

    study_name = str(optuna_data.get('study_name', ''))
    
    charts_spec: dict[str, Any] = {}
    if study_name:
        try:
            from report.reporter import build_optuna_spec
            study_db_url = f"sqlite:///{os.path.abspath(dm.store.db_path)}"
            charts_spec = build_optuna_spec(study_db_url, study_name)
        except Exception as e:
            logger.warning(f"Optuna chart spec 生成失败: {e}")

    best_params_raw = optuna_data.get('best_params') or []
    best_params_from_optuna = charts_spec.get('best_params') or []
    merged_best_params = best_params_from_optuna if best_params_from_optuna else best_params_raw

    result = {
        'study_name': study_name,
        'trial_count': optuna_data.get('trial_count', 0),
        'best_value': charts_spec.get('best_value'),
        'best_params': merged_best_params,
        'optimization_history': charts_spec.get('optimization_history'),
        'param_importances': charts_spec.get('param_importances'),
        'parallel_coordinate': charts_spec.get('parallel_coordinate'),
        'contours': charts_spec.get('contours'),
    }
    _write_json(output_dir, f"r{run_id}/data/optuna.json", result)


def write_nav_json(output_dir: str) -> None:
    """
    导出全局导航数据 JSON（所有运行记录）
    
    Args:
        output_dir: 输出目录
    """
    dm = get_data_manager()
    runs = dm.get_all_runs()
    _write_json(output_dir, "data/nav.json", runs)


def _write_json(output_dir: str, rel_path: str, data: object) -> None:
    """
    将数据写入JSON文件
    
    Args:
        output_dir: 输出目录
        rel_path: 相对路径
        data: 要写入的数据
    """
    full_path = Path(output_dir) / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)  # 创建目录
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _build_kline_dict(
    csv_path: str,
    symbol: str,
    interval: str,
    start_date: str | None,
    end_date: str | None,
) -> dict | None:
    """
    从 CSV 构建 K 线 JSON dict (daily resampled + raw 降采样)

    CSV 中的 datetime 为北京时间字符串（无时区标记）。
    转换逻辑：解析为 Asia/Shanghai → 转 UTC → 输出 Unix timestamp（秒）。
    lightweight-charts 接收 UTC timestamp 后自动按浏览器本地时区显示。

    Args:
        csv_path: CSV文件路径
        symbol: 品种代码
        interval: K线周期
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        K线数据字典，失败返回None
    """
    try:
        df = pd.read_csv(csv_path)  # 读取CSV
        # 处理时间列
        if "datetime" not in df.columns:
            if "date" in df.columns:
                df["datetime"] = df["date"]
            else:
                return None

        # 解析 CSV datetime 为 Asia/Shanghai 时区的 Timestamp
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize("Asia/Shanghai")

        # 按日期范围筛选（使用带时区的 Timestamp 比较）
        if start_date:
            tz_start = pd.Timestamp(start_date, tz="Asia/Shanghai")
            df = df[df["datetime"] >= tz_start]
        if end_date:
            tz_end = pd.Timestamp(end_date, tz="Asia/Shanghai") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            df = df[df["datetime"] <= tz_end]

        if df.empty:
            return None

        # 重采样生成日线数据（先转 UTC 再 resample，确保日线分组合正确）
        df_for_daily = df.copy()
        df_for_daily["datetime"] = df_for_daily["datetime"].dt.tz_convert("UTC")
        df_for_daily = df_for_daily.set_index("datetime")
        daily_ohlc = (
            df_for_daily.resample("1D")
            .agg(
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
                volume=("volume", "sum"),
            )
            .dropna()
        )

        # 格式化日线数据（转为 UTC Unix 时间戳）
        daily_data = [
            {
                "datetime": int(idx.timestamp()),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": int(row.volume),
            }
            for idx, row in daily_ohlc.iterrows()
        ]

        # 原始数据（转为 UTC Unix 时间戳）
        raw_data = []
        for _, row in df.iterrows():
            raw_data.append({
                "datetime": int(row["datetime"].tz_convert("UTC").timestamp()),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0)),
            })

        total = len(df)
        return {
            "symbol": symbol,
            "interval": interval,
            "csv_source": csv_path,
            "daily": daily_data,
            "raw": raw_data,
            "raw_count": total,
            "raw_downsampled": False,
            "raw_sample_max": 0,
        }

    except Exception as e:
        logger.error("K线数据构建失败 [%s]: %s", symbol, e)
        return None