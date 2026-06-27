"""JSON 数据写入器

将数据库中的回测数据格式化为 JSON 文件并写入磁盘。

设计原则：
- 所有 `export_*` 函数接受可选的 `dm` 参数，调用者可注入 DataManager 实例
- `build_kline_dict` 是从 CSV 构建 K 线 JSON 结构的工具函数，对外暴露
- 单一职责：只做"读 DB → 格式化 → 写文件"，不做增量检查 / 缓存管理
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from data import DataManager
from loguru import logger

from report.cache import KlineCache
from report.output_paths import nav_json_path, run_data_dir


def _get_dm(dm: DataManager | None) -> DataManager:
    """返回传入的 dm，若无则创建新实例"""
    return dm if dm is not None else DataManager()


def export_run_json(run_id: int, dm: DataManager | None = None) -> None:
    """导出单次运行的元信息到 JSON 文件"""
    dm = _get_dm(dm)
    row = dm.get_run_info(run_id)

    if not row:
        logger.warning("run_id={} 不存在", run_id)
        return

    data = {
        "id": row["id"],
        "strategy": row["strategy"],
        "engine": row["engine"],
        "symbols": row["symbols"],
        "status": row["status"],
        "created_at": row["created_at"],
    }
    _write_json(run_data_dir(run_id) / "run.json", data)


def export_summary_json(run_id: int, dm: DataManager | None = None) -> None:
    """导出品种汇总表（每品种最优回测记录）"""
    dm = _get_dm(dm)
    data = dm.get_run_summary(run_id)
    _write_json(run_data_dir(run_id) / "summary.json", data)


def export_backtests_json(run_id: int, dm: DataManager | None = None) -> None:
    """导出所有回测记录完整信息（含指标、参数、日线数据）"""
    dm = _get_dm(dm)
    result = dm.get_backtests_for_run(run_id)
    _write_json(run_data_dir(run_id) / "backtests.json", result)


def export_equity_json(run_id: int, dm: DataManager | None = None) -> None:
    """导出资金曲线数据（每品种最优回测的日线权益/回撤）"""
    dm = _get_dm(dm)
    summary = dm.get_run_summary(run_id)
    result: dict[str, Any] = {}
    for s in summary:
        s_id = s.get("id")
        if not s_id:
            continue
        equity = dm.get_equity_data(int(s_id))  # type: ignore[call-overload]
        if equity:
            equity["max_ddpercent"] = s.get("max_ddpercent", 0)  # type: ignore[arg-type]
            equity["initial_capital"] = s.get("initial_capital")  # type: ignore[arg-type]
            result[str(s["symbol"])] = equity
    _write_json(run_data_dir(run_id) / "equity.json", result)


def export_kline_json(run_id: int, dm: DataManager | None = None) -> bool:
    """导出 K 线数据 JSON（使用 KlineCache 复用 CSV→JSON 转换结果）

    Returns:
        True if any kline data was written, False if all hit cache
    """
    dm = _get_dm(dm)
    cache = KlineCache()
    summary = dm.get_run_summary(run_id)
    has_changes = False

    for s in summary:
        symbol: str = str(s["symbol"])
        if not s.get("id"):
            continue

        data_src = str(s.get("data_src", ""))
        start_date = str(s.get("start_date")) if s.get("start_date") else None
        end_date = str(s.get("end_date")) if s.get("end_date") else None
        interval: str = str(s.get("kline_interval") or "1m")
        dest = run_data_dir(run_id) / f"kline_{symbol}.{interval}.json"

        if not data_src:
            continue

        if cache.copy_to(symbol, data_src, interval, dest):
            continue

        if not Path(data_src).exists():
            logger.warning("K线数据源不存在: {} → {}", symbol, data_src)
            continue

        kline_dict = build_kline_dict(data_src, symbol, interval, start_date, end_date)
        if kline_dict:
            cache.put(symbol, data_src, interval, kline_dict)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(kline_dict, f, ensure_ascii=False, default=str)
            logger.info("K线已导出: {} → {}", symbol, dest.name)
            has_changes = True

    return has_changes


def export_trades_json(run_id: int, dm: DataManager | None = None) -> None:
    """导出交易记录 JSON（取最优 trial 对应的各品种成交）"""
    from data.models import Backtest, BacktestTrade

    dm = _get_dm(dm)
    from data.optuna_query import get_best_trial_index

    best_trial_index = get_best_trial_index(run_id)

    all_trades: dict[str, list[dict[str, Any]]] = {}
    for bt in Backtest.select(Backtest.id, Backtest.symbol, Backtest.engine_config).where(
        Backtest.run_id == run_id, Backtest.status == "success"
    ):
        ec = bt.engine_config
        if not ec:
            continue
        if isinstance(ec, str):
            try:
                cfg = json.loads(ec)
            except Exception:
                continue
        else:
            cfg = ec
        if cfg.get("trial_index") != best_trial_index:
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
            all_trades[symbol].append(
                {
                    "datetime": t.datetime,
                    "symbol": t.symbol,
                    "direction": direction,
                    "offset": offset,
                    "open_price": t.open_price,
                    "close_price": t.close_price,
                    "quantity": t.quantity,
                    "pnl": t.pnl,
                    "commission": t.commission,
                    "reason": t.reason if hasattr(t, "reason") else "",
                }
            )

    _write_json(run_data_dir(run_id) / "trades.json", all_trades)


def export_optuna_json(run_id: int, dm: DataManager | None = None) -> None:
    """导出 Optuna 优化数据 JSON（含图表配置）。

    非参数搜索 run 没有关联 study，也仍写出一个空 optuna.json，
    保持 report artifact 集合稳定。
    """
    import os

    dm = _get_dm(dm)
    optuna_data = dm.get_optuna_data(run_id)
    if not optuna_data:
        _write_json(
            run_data_dir(run_id) / "optuna.json",
            {
                "study_name": "",
                "trial_count": 0,
                "best_value": None,
                "best_params": [],
                "optimization_history": None,
                "param_importances": None,
                "parallel_coordinate": None,
                "contours": None,
            },
        )
        return

    study_name = str(optuna_data.get("study_name", ""))

    charts_spec: dict[str, Any] = {}
    if study_name:
        try:
            from report.reporter import build_optuna_spec

            study_db_url = f"sqlite:///{os.path.abspath(dm.store.db_path)}"
            charts_spec = build_optuna_spec(study_db_url, study_name)
        except Exception as e:
            logger.warning("Optuna chart spec 生成失败: {}", e)

    best_params_raw = optuna_data.get("best_params") or []
    best_params_from_optuna = charts_spec.get("best_params") or []
    merged_best_params = best_params_from_optuna if best_params_from_optuna else best_params_raw

    result = {
        "study_name": study_name,
        "trial_count": optuna_data.get("trial_count", 0),
        "best_value": charts_spec.get("best_value"),
        "best_params": merged_best_params,
        "optimization_history": charts_spec.get("optimization_history"),
        "param_importances": charts_spec.get("param_importances"),
        "parallel_coordinate": charts_spec.get("parallel_coordinate"),
        "contours": charts_spec.get("contours"),
    }
    _write_json(run_data_dir(run_id) / "optuna.json", result)


def write_nav_json(dm: DataManager | None = None) -> None:
    """导出全局导航数据 JSON（所有运行记录）"""
    dm = _get_dm(dm)
    runs = dm.get_all_runs()
    _write_json(nav_json_path(), runs)


# ── 内部工具函数 ──────────────────────────────────────────────────────────


def _write_json(file_path: Path, data: object) -> None:
    """将数据写入 JSON 文件"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _resample_kline(df: pd.DataFrame, rule: str) -> list[dict]:
    """对 Asia/Shanghai 时区的 DataFrame 重采样为目标周期

    返回 UTC Unix timestamp 的 OHLCV 数据列表。
    """
    df_r = df.copy()
    df_r = df_r.set_index("datetime")
    resampled = (
        df_r.resample(rule)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna()
    )
    resampled.index = pd.DatetimeIndex(resampled.index).tz_convert("UTC")
    return [
        {
            "datetime": int(pd.Timestamp(str(idx)).timestamp()),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": int(row.volume),
        }
        for idx, row in resampled.iterrows()
    ]


# ── 公开工具函数 ──────────────────────────────────────────────────────────


def build_kline_dict(
    csv_path: str,
    symbol: str,
    interval: str,
    start_date: str | None,
    end_date: str | None,
) -> dict | None:
    """从 CSV 构建 K 线 JSON dict（日线 + 原始 + 5m/15m/1h 多周期）

    CSV datetime 为北京时间字符串（无时区标记），处理流程：
    解析为 Asia/Shanghai → 转 UTC → 输出 Unix timestamp（秒）。
    lightweight-charts 接收 UTC timestamp 后自动按浏览器本地时区显示。

    Args:
        csv_path: CSV 文件路径
        symbol: 品种代码
        interval: K线周期
        start_date: 开始日期（YYYY-MM-DD）
        end_date: 结束日期（YYYY-MM-DD）

    Returns:
        K线数据字典，失败返回 None
    """
    try:
        df = pd.read_csv(csv_path)
        if "datetime" not in df.columns:
            if "date" in df.columns:
                df["datetime"] = df["date"]
            else:
                return None

        # 解析 CSV datetime 为 Asia/Shanghai 时区的 Timestamp
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize("Asia/Shanghai")

        # 按日期范围筛选
        if start_date:
            tz_start = pd.Timestamp(start_date, tz="Asia/Shanghai")
            df = df[df["datetime"] >= tz_start]
        if end_date:
            tz_end = pd.Timestamp(end_date, tz="Asia/Shanghai") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            df = df[df["datetime"] <= tz_end]

        if df.empty:
            return None

        # 日线：先转 UTC 再 resample，确保日线分组正确
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

        daily_data = [
            {
                "datetime": int(pd.Timestamp(str(idx)).timestamp()),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": int(row.volume),
            }
            for idx, row in daily_ohlc.iterrows()
        ]

        # 原始数据（转为 UTC Unix 时间戳）
        raw_data = [
            {
                "datetime": int(row["datetime"].tz_convert("UTC").timestamp()),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0)),
            }
            for _, row in df.iterrows()
        ]

        total = len(df)

        # 多周期 K 线（5分钟 / 15分钟 / 1小时）
        timeframes = {
            "5m": "5min",
            "15m": "15min",
            "1h": "1h",
        }
        multi_timeframe: dict[str, list[dict]] = {}
        for tf_name, tf_rule in timeframes.items():
            multi_timeframe[tf_name] = _resample_kline(df, tf_rule)

        return {
            "symbol": symbol,
            "interval": interval,
            "csv_source": csv_path,
            "daily": daily_data,
            "raw": raw_data,
            "raw_count": total,
            "raw_downsampled": False,
            "raw_sample_max": 0,
            "multi_timeframe": multi_timeframe,
        }

    except Exception as e:
        logger.error("K线数据构建失败 [{}]: {}", symbol, e)
        return None
