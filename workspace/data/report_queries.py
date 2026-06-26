"""报表视图查询层

封装报告生成所需的业务聚合查询（按 run 聚合品种最优记录、回测明细、资金曲线），
从 DataStore 中拆出，让 DataStore 回归数据库基础 CRUD 操作。

DataManager.get_run_summary / get_backtests_for_run / get_equity_data 委托到此模块。

设计原则：
- 只做"读 DB → 聚合 → 返回 dict/list"，不写库、不做缓存。
- 复用 DataStore 的基础查询（query_daily）通过传入 store 实例完成，避免重复实现。
- 最优 trial 过滤复用 data.optuna_query.get_best_trial_index。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loguru import logger

from .models import Backtest, BacktestParam
from .optuna_query import get_best_trial_index

if TYPE_CHECKING:
    from .store import DataStore

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportArgumentType=false
# pyright: reportAttributeAccessIssue=false
# 注: peewee ORM 缺少类型存根，方法链与字段描述符访问会产生误报。


def _f(val: Any) -> float:
    """安全转换 → float"""
    return float(val) if val is not None else 0.0


def _i(val: Any) -> int:
    """安全转换 → int"""
    return int(val) if val is not None else 0


def _filter_by_best_trial(backtests: list[dict[str, Any]], run_id: int) -> list[dict[str, Any]]:
    """过滤出全局最优 trial 对应的回测记录

    【设计意图】
    一个 run 通常会跑多组参数（Optuna trial），报告应展示"最优参数在各品种上的表现"。
    通过读取 Backtest.engine_config 中的 trial_index，筛选出 trial 编号等于 get_best_trial_index() 的记录。

    【回退策略 — 重要】
    - 若 best_trial <= 0（未找到优化记录）→ 原样返回全部（退化为"每个品种取自己最优"）
    - 若过滤后得到空列表 → 原样返回全部（避免报告空白），但记录一条 warning 方便排查
    """
    best_trial = get_best_trial_index(run_id)
    if best_trial <= 0:
        return backtests

    filtered: list[dict[str, Any]] = []
    for bt in backtests:
        ec = bt.get("engine_config")
        if isinstance(ec, str):
            try:
                cfg = json.loads(ec)
            except Exception:
                continue
        else:
            cfg = ec
        if cfg.get("trial_index") == best_trial:
            filtered.append(bt)

    if not filtered:
        logger.warning(
            "run=%d 最优 trial=%d 在回测记录中找不到匹配，将展示全部记录（可能是 engine_config 未写入 trial_index）",
            run_id,
            best_trial,
        )
        return backtests
    return filtered


def get_run_summary(run_id: int) -> list[dict[str, object]]:
    """获取每品种最优回测记录（仅全局最优参数组合）"""
    rows = list(
        Backtest.select(
            Backtest.id,
            Backtest.symbol,
            Backtest.total_return,
            Backtest.total_trades,
            Backtest.win_rate,
            Backtest.win_loss_ratio,
            Backtest.annual_return,
            Backtest.max_drawdown,
            Backtest.max_ddpercent,
            Backtest.sharpe_ratio,
            Backtest.end_balance,
            Backtest.total_net_pnl,
            Backtest.total_commission,
            Backtest.total_slippage,
            Backtest.profit_days,
            Backtest.loss_days,
            Backtest.ewm_sharpe,
            Backtest.rgr_ratio,
            Backtest.data_src,
            Backtest.start_date,
            Backtest.end_date,
            Backtest.kline_interval,
            Backtest.engine_config,
        )
        .where(Backtest.run_id == run_id, Backtest.status == "success")
        .order_by(Backtest.symbol, Backtest.total_return.desc())
        .dicts()
    )

    rows = _filter_by_best_trial(rows, run_id)

    best: dict[str, dict[str, object]] = {}
    for r in rows:
        _update_best_for_symbol(best, r)
    return [best[s] for s in sorted(best)]


def _update_best_for_symbol(best: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    """为单个品种维护最高收益的回测摘要

    作为 `get_run_summary` 中的循环体抽离，便于阅读和测试。
    """
    sym = str(row["symbol"])
    total_return = _f(row["total_return"] or 0)
    if sym not in best or total_return > _f(best[sym].get("total_return") or 0):
        best[sym] = {
            "id": row["id"],
            "symbol": sym,
            "total_return": total_return,
            "total_trades": row["total_trades"] or 0,
            "win_rate": _f(row["win_rate"] or 0) * 100,
            "win_loss_ratio": _f(row["win_loss_ratio"] or 0),
            "annual_return": _f(row["annual_return"] or 0),
            "max_drawdown": _f(row["max_drawdown"] or 0),
            "max_ddpercent": _f(row["max_ddpercent"] or 0),
            "sharpe": _f(row["sharpe_ratio"] or 0),
            "end_balance": _f(row["end_balance"] or 0),
            "total_net_pnl": _f(row["total_net_pnl"] or 0),
            "total_commission": _f(row["total_commission"] or 0),
            "total_slippage": _f(row["total_slippage"] or 0),
            "profit_days": row["profit_days"] or 0,
            "loss_days": row["loss_days"] or 0,
            "ewm_sharpe": _f(row["ewm_sharpe"] or 0),
            "rgr_ratio": _f(row["rgr_ratio"] or 0),
            "ret_cls": "badge-green" if total_return > 0 else "badge-red",
            "sr_cls": "badge-green" if _f(row["sharpe_ratio"] or 0) > 0 else "badge-red",
            "data_src": row["data_src"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "kline_interval": row["kline_interval"],
        }


def get_backtests_for_run(store: DataStore, run_id: int) -> list[dict[str, object]]:
    """获取某 run 下所有回测记录（含参数和日线数据，仅全局最优参数组合）"""
    backtests = list(Backtest.select().where(Backtest.run_id == run_id, Backtest.status == "success").dicts())

    backtests = _filter_by_best_trial(backtests, run_id)

    result = []
    for bt in backtests:
        bt_id = _i(bt["id"])

        params = list(
            BacktestParam.select(
                BacktestParam.param_name,
                BacktestParam.param_value,
                BacktestParam.param_type,
                BacktestParam.param_text,
            )
            .where(BacktestParam.backtest == bt_id)
            .order_by(BacktestParam.param_name)
            .dicts()
        )

        daily = store.query_daily(bt_id)

        result.append(
            {
                "id": bt_id,
                "symbol": bt["symbol"],
                "strategy": bt["strategy"],
                "status": bt["status"],
                "start_date": bt["start_date"],
                "end_date": bt["end_date"],
                "initial_capital": bt["initial_capital"],
                "end_balance": bt["end_balance"],
                "total_return": _f(bt["total_return"] or 0),
                "sharpe_ratio": _f(bt["sharpe_ratio"] or 0),
                "max_drawdown": _f(bt["max_drawdown"] or 0),
                "max_ddpercent": _f(bt["max_ddpercent"] or 0),
                "win_rate": _f(bt["win_rate"] or 0) * 100,
                "total_trades": bt["total_trades"] or 0,
                "total_net_pnl": _f(bt["total_net_pnl"] or 0),
                "daily_net_pnl": _f(bt["daily_net_pnl"] or 0),
                "total_commission": _f(bt["total_commission"] or 0),
                "daily_commission": _f(bt["daily_commission"] or 0),
                "total_slippage": _f(bt["total_slippage"] or 0),
                "daily_slippage": _f(bt["daily_slippage"] or 0),
                "total_turnover": _f(bt["total_turnover"] or 0),
                "daily_turnover": _f(bt["daily_turnover"] or 0),
                "profit_days": bt["profit_days"] or 0,
                "loss_days": bt["loss_days"] or 0,
                "daily_trade_count": _f(bt["daily_trade_count"] or 0),
                "daily_return_pct": _f(bt["daily_return_pct"] or 0),
                "ewm_sharpe": _f(bt["ewm_sharpe"] or 0),
                "rgr_ratio": _f(bt["rgr_ratio"] or 0),
                "data_src": bt["data_src"],
                "kline_interval": bt["kline_interval"],
                "strategy_version": bt["strategy_version"],
                "git_hash": bt["git_hash"],
                "params": [
                    {
                        "name": p["param_name"],
                        "value": p["param_value"] if p["param_value"] is not None else p["param_text"],
                        "type": p["param_type"],
                    }
                    for p in params
                ],
                "daily": daily,
            }
        )
    return result


def get_equity_data(store: DataStore, backtest_id: int) -> dict[str, object] | None:
    """获取指定回测记录的资金曲线数据"""
    rows = store.query_daily(backtest_id)
    if not rows:
        return None

    return {
        "dates": [r["date"] for r in rows],
        "equity": [_f(r["equity"]) for r in rows],
        "drawdown": [_f(r["drawdown"]) for r in rows],
    }
