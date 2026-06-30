"""报告数据导出

负责把数据库中的回测数据导出为前端可读的 JSON 文件，
支持基于数据指纹的增量检查（通过 BuildCache）。

本模块不感知前端构建和 HTML 打包。
"""

from __future__ import annotations

from collections.abc import Callable

from data import DataManager
from loguru import logger

from ..cache import BuildCache
from ..output_paths import run_data_dir
from ..writer import (
    export_backtests_json,
    export_clearing_diagnostics_json,
    export_equity_json,
    export_kline_json,
    export_optuna_json,
    export_run_json,
    export_summary_json,
    export_trades_json,
    write_nav_json,
)


def run_data_exports(
    output_dir: str,
    run_id: int,
    incremental: bool = True,
    dm: DataManager | None = None,
) -> tuple[int, int]:
    """执行所有数据导出任务，返回 (实际导出数, 跳过数)

    任务分两类：
    - 通用类型（run/summary/backtests/optuna）: 基于指纹的增量检查
    - 自定义类型（equity/kline/trades/nav）: 有特殊的增量检查逻辑
    """
    dm = dm or DataManager()
    cache = BuildCache() if incremental else None

    # 任务描述符: (类型名, 指纹收集函数, 全量导出函数)
    export_tasks: list[tuple[str, Callable[[DataManager, int], object], Callable[..., object]]] = [
        ("run", lambda d, rid: d.get_run_info(rid), lambda rid, d: export_run_json(rid, d)),
        ("summary", lambda d, rid: d.get_run_summary(rid), lambda rid, d: export_summary_json(rid, d)),
        (
            "backtests",
            lambda d, rid: d.get_backtests_for_run(rid),
            lambda rid, d: export_backtests_json(rid, d),
        ),
        ("equity", _collect_equity_fingerprint, lambda rid, d: export_equity_json(rid, d)),
        ("kline", _collect_kline_fingerprint, lambda rid, d: export_kline_json(rid, d)),
        ("optuna", lambda d, rid: d.get_optuna_data(rid), lambda rid, d: export_optuna_json(rid, d)),
        (
            "clearing_diagnostics",
            lambda d, rid: d.get_clearing_diagnostics_for_run(rid),
            lambda rid, d: export_clearing_diagnostics_json(rid, d),
        ),
        ("trades", _collect_trades_fingerprint, lambda rid, d: export_trades_json(rid, d)),
        ("nav", lambda d, _rid: d.get_all_runs(), lambda _rid, d: write_nav_json(d)),
    ]

    exported = 0
    skipped = 0

    for data_type, getter, exporter in export_tasks:
        if cache and data_type == "kline":
            # K线有独立的 KlineCache，直接调用自定义增量导出
            executed = _export_kline_with_incremental(cache, dm, output_dir, run_id)
        elif cache and data_type == "equity":
            executed = _export_equity_with_incremental(cache, dm, output_dir, run_id)
        elif cache and data_type == "trades":
            executed = _export_trades_with_incremental(cache, dm, output_dir, run_id)
        elif cache and data_type == "nav":
            executed = _export_nav_with_incremental(cache, dm, output_dir)
        elif cache:
            # 通用增量检查: 基于指纹/缓存哈希对比
            new_data = getter(dm, run_id)
            if cache.needs_update(data_type, run_id, new_data) or _artifact_missing(run_id, data_type):
                exporter(run_id, dm)
                cache.update_fingerprint(data_type, run_id, new_data)
                logger.info("→ 导出 {}（数据已变更）", data_type)
                executed = True
            else:
                logger.info("○ 跳过 {}（数据未变更）", data_type)
                executed = False
        else:
            # 全量导出: 不检查缓存，直接写入
            exporter(run_id, dm)
            logger.info("→ 导出 {}", data_type)
            executed = True

        if executed:
            exported += 1
        else:
            skipped += 1

    return exported, skipped


# ── 指纹收集函数 ─────────────────────────────────────────────────────────


def _artifact_missing(run_id: int, data_type: str) -> bool:
    """增量缓存命中时仍确保对应 artifact 文件真实存在。"""
    return not (run_data_dir(run_id) / f"{data_type}.json").is_file()


def _collect_equity_fingerprint(dm: DataManager, run_id: int) -> dict[str, object]:
    """收集 equity 指纹用于增量检查"""
    summary = dm.get_run_summary(run_id)
    result: dict[str, object] = {}
    for s in summary:
        s_id = s.get("id")
        if not s_id:
            continue
        equity = dm.get_equity_data(int(s_id))  # type: ignore[call-overload]
        if equity:
            result[str(s["symbol"])] = equity
    return result


def _collect_kline_fingerprint(dm: DataManager, run_id: int) -> dict[str, object]:
    """收集 kline 指纹用于增量检查（仅记录 symbol+interval 级元数据）"""
    summary = dm.get_run_summary(run_id)
    return {str(s["symbol"]): s.get("data_src") for s in summary if s.get("id")}


def _collect_trades_fingerprint(dm: DataManager, run_id: int) -> dict[str, object]:
    """收集 trades 指纹用于增量检查"""
    summary = dm.get_run_summary(run_id)
    result: dict[str, object] = {}
    for s in summary:
        s_id = s.get("id")
        if not s_id:
            continue
        symbol = str(s.get("symbol", ""))
        trades = dm.query_trades(int(str(s_id)))
        result[symbol] = {
            "count": len(trades),
            "total_net_pnl": s.get("total_net_pnl"),
            "total_commission": s.get("total_commission"),
            "total_slippage": s.get("total_slippage"),
        }
    return result


# ── 自定义增量检查 ─────────────────────────────────────────────────────


def _export_equity_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> bool:
    """导出 equity 数据（带增量检查）"""
    equity_data = _collect_equity_fingerprint(dm, run_id)

    if cache.needs_update("equity", run_id, equity_data):
        logger.info("→ 导出 equity（数据已变更）")
        export_equity_json(run_id, dm)
        cache.update_fingerprint("equity", run_id, equity_data)
        return True
    logger.info("○ 跳过 equity（数据未变更）")
    return False


def _export_kline_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> bool:
    """导出 K 线数据（带增量检查）"""
    kline_data = _collect_kline_fingerprint(dm, run_id)

    if cache.needs_update("kline", run_id, kline_data):
        logger.info("→ 导出 kline（数据已变更）")
        has_changes = export_kline_json(run_id, dm)
        cache.update_fingerprint("kline", run_id, kline_data)
        return has_changes
    logger.info("○ 跳过 kline（数据未变更）")
    return False


def _export_trades_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
    run_id: int,
) -> bool:
    """导出 trades 数据（带增量检查）"""
    trades_data = _collect_trades_fingerprint(dm, run_id)

    if cache.needs_update("trades", run_id, trades_data):
        logger.info("→ 导出 trades（数据已变更）")
        export_trades_json(run_id, dm)
        cache.update_fingerprint("trades", run_id, trades_data)
        return True
    logger.info("○ 跳过 trades（数据未变更）")
    return False


def _export_nav_with_incremental(
    cache: BuildCache,
    dm: DataManager,
    output_dir: str,
) -> bool:
    """导出 nav 数据（带增量检查）"""
    runs = dm.get_all_runs()
    if cache.needs_update("nav", None, runs):
        logger.info("→ 导出 nav（数据已变更）")
        write_nav_json(dm)
        cache.update_fingerprint("nav", None, runs)
        return True
    logger.info("○ 跳过 nav（数据未变更）")
    return False
