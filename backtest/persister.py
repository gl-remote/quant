"""背测域持久化服务（阶段 4：从 workflow 中拆出）

提供三个 Persister 类，负责回测结果的数据库写入：
  - BacktestResultPersister:  基础 CRUD + daily/trades/一致性校验
  - SearchResultPersister:    参数搜索结果的持久化（含 trial_data 遍历）
  - WalkForwardPersister:     Walk-Forward 结果持久化

设计说明：
  - persister 放在 backtest/ 域而非 data/ 层，因为它理解 SearchResult、
    WalkForwardResult 等背测领域对象。
  - persister 内部仍持 DataManager 引用调 CRUD，但 workflow 不再直接
    接触 dm.store.*。
  - 这是一个中期铺板子措施。远期目标中 persister 被纯 JSON + 适配器替代，
    backtest 域不再依赖 data/ 任何模块。
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from common.types import BacktestResult

from .optimizer import SearchResult

# ── 状态常量（与 workflow 共享，避免跨层 import 冲突） ────────
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"


class BacktestResultPersister:
    """基础背测结果持久化：单条/批量写入 + daily + trades + 校验

    所有方法有独立的 try/except，失败不阻断后续操作。
    """

    def __init__(self, dm: Any) -> None:
        self._dm = dm

    def persist_result(
        self,
        result: BacktestResult,
        run_id: int | None = None,
        data_src: str | None = None,
    ) -> int:
        """写入单条背测记录，返回 backtest_id"""
        return self._dm.insert_backtest(result, run_id=run_id, data_src=data_src)  # type: ignore[no-any-return]

    def persist_results(
        self,
        results: list[BacktestResult],
        run_id: int | None = None,
        data_src: str | None = None,
    ) -> list[int]:
        """批量写入背测记录，返回 backtest_id 列表"""
        ids: list[int] = []
        for r in results:
            ids.append(self._dm.insert_backtest(r, run_id=run_id, data_src=data_src))
        return ids

    def persist_daily(self, backtest_id: int, daily: list[dict[str, object]]) -> None:
        """写入每日资金曲线，失败仅打日志"""
        if not daily:
            return
        try:
            self._dm.insert_backtest_daily(backtest_id, daily)
        except Exception:
            logger.exception("每日资金曲线持久化失败 [bt={}]", backtest_id)

    def persist_trades(self, backtest_id: int, trades: list[dict[str, object]]) -> None:
        """写入交易明细，失败仅打日志"""
        if not trades:
            return
        try:
            self._dm.insert_backtest_trades(backtest_id, trades)
        except Exception:
            logger.exception("交易记录持久化失败 [bt={}]", backtest_id)

    def validate_consistency(self, backtest_id: int) -> None:
        """校验数据一致性，失败仅打日志"""
        try:
            errors = self._dm.validate_consistency(backtest_id)
            if errors:
                for err in errors:
                    logger.warning("数据一致性警告: {}", err)
        except Exception:
            logger.exception("数据一致性校验失败 [bt={}]", backtest_id)


class SearchResultPersister:
    """参数搜索结果的持久化

    遍历 SearchResult.trial_data，为每个 trial 的每个品种写入
    backtest/daily/trades 记录，并校验一致性。
    """

    def __init__(self, dm: Any) -> None:
        self._bt_persister = BacktestResultPersister(dm)
        self._dm = dm

    def persist_search_result(
        self,
        result: SearchResult,
        datasets: list[tuple[str, pd.DataFrame, str]],
        search_type: str,
        study_name: str,
        git_hash: str | None,
        run_id: int | None = None,
    ) -> list[int]:
        """将 SearchResult 的 trial_data 统一持久化到数据库

        Args:
            result: SearchResult（来自串行或并行搜索）
            datasets: [(symbol, DataFrame, data_src), ...]
            search_type: "grid" 或 "bayesian"
            study_name: Optuna study 名称
            git_hash: Git 提交哈希
            run_id: 运行记录 ID

        Returns:
            成功写入的 backtest_id 列表
        """
        engine_cfg = {
            "type": "vnpy",
            "optimizer": search_type,
            "study_name": study_name,
            "study_db": self._dm.store.db_path,  # noqa: phase-6-only
        }
        all_ids: list[int] = []
        for i, trial in enumerate(result.trial_data):
            trial_cfg = {**engine_cfg, "trial_index": i}
            for er in trial.get("engine_results", []):
                er.engine_config = trial_cfg
                er.strategy_params = trial.get("strategy_params", {})
                er.git_hash = git_hash

                if not er.success:
                    er.status = STATUS_FAILED
                    self._bt_persister.persist_result(
                        er,
                        run_id=run_id,
                        data_src=next((f for s, _, f in datasets if s == er.symbol), None),
                    )
                    continue

                sym = er.symbol
                data_src = next((f for s, _, f in datasets if s == sym), None)
                er.status = STATUS_SUCCESS
                bt_id = self._bt_persister.persist_result(er, run_id=run_id, data_src=data_src)
                all_ids.append(bt_id)

                self._bt_persister.persist_daily(bt_id, er.daily_results)
                self._bt_persister.persist_trades(bt_id, er.fills)
                self._bt_persister.validate_consistency(bt_id)

        return all_ids


class WalkForwardPersister:
    """Walk-Forward 结果的持久化

    将 wf_result（dict）转为 BacktestResult，写入主记录 + daily + trades。
    """

    def __init__(self, dm: Any) -> None:
        self._bt_persister = BacktestResultPersister(dm)

    def persist_walk_forward(
        self,
        wf_result: dict[str, Any],
        symbol: str,
        strategy: str,
        strategy_params: dict[str, Any],
        strategy_version: str | None,
        git_hash: str | None,
        start_date: str | None,
        end_date: str | None,
        data_src: str,
    ) -> int:
        """持久化 Walk-Forward 结果，返回 backtest_id"""
        wf_result_data = wf_result.get("aggregate", {})
        result = BacktestResult(
            symbol=symbol,
            strategy=strategy,
            status=STATUS_SUCCESS,
            strategy_version=strategy_version,
            git_hash=git_hash,
            strategy_params=strategy_params,
            start_date=start_date,
            end_date=end_date,
            engine_config={
                "type": "vnpy",
                "mode": "walk-forward",
                "windows": wf_result.get("windows", 0),
            },
            sharpe_ratio=wf_result_data.get("sharpe_mean"),
            max_drawdown=wf_result_data.get("max_drawdown_mean"),
            total_return=wf_result_data.get("return_mean"),
            daily_std=wf_result_data.get("return_std"),
        )
        bt_id = self._bt_persister.persist_result(result, data_src=data_src)

        all_daily: list[dict[str, object]] = []
        all_trades: list[dict[str, object]] = []
        for wr in wf_result.get("window_results", []):
            all_daily.extend(wr.get("daily_results", []))
            all_trades.extend(wr.get("trades", []))

        self._bt_persister.persist_daily(bt_id, all_daily)
        self._bt_persister.persist_trades(bt_id, all_trades)

        return bt_id
