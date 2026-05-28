"""JSON 数据写入器

提供各类数据的 JSON 导出功能
"""

import json
import logging
from pathlib import Path
from typing import Any

from data import get_data_manager
from report.cache import KlineCache
from report.utils import _build_kline_dict, _write_json

logger = logging.getLogger(__name__)


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
            result[str(s["symbol"])] = equity
    _write_json(output_dir, f"r{run_id}/data/equity.json", result)


def export_kline_json(output_dir: str, run_id: int) -> None:
    """
    导出 K 线数据 JSON（使用 KlineCache 避免重复转换）

    从最优回测记录获取各品种的 CSV 路径和日期范围，
    按品种独立生成 kline_{symbol}.json。
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
        dest = Path(output_dir) / f"r{run_id}/data" / f"kline_{symbol}.json"

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

    study_name = str(optuna_data.get("study_name", ""))
    
    charts_spec: dict[str, Any] = {}
    if study_name:
        try:
            from report.optimizer_report import build_optuna_spec
            study_db_url = f"sqlite:///{os.path.abspath(dm.store.db_path)}"
            charts_spec = build_optuna_spec(study_db_url, study_name)
        except Exception as e:
            logger.warning("Optuna chart spec 生成失败: %s", e)

    best_params_raw = optuna_data.get("best_params") or []
    best_params_from_optuna = charts_spec.get("best_params") or []
    merged_best_params = best_params_from_optuna if best_params_from_optuna else best_params_raw

    result = {
        "study_name": study_name,
        "trial_count": optuna_data.get("trial_count", 0),
        "best_value": optuna_data.get("best_value"),
        "best_params": merged_best_params,
        "trials": optuna_data.get("trials", []),
        "param_names": optuna_data.get("param_names", []),
        "charts": charts_spec.get("charts", {}),
        "param_scatter": charts_spec.get("param_scatter"),
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