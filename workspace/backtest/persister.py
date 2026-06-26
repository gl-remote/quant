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
from common.types import BacktestResult
from loguru import logger

from .optimizer import SearchResult
from .results import WalkForwardResult

# ── 状态常量（与 workflow 共享，避免跨层 import 冲突） ────────
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"


class BacktestResultPersister:
    """背测结果持久化

    将所有调用方的模型字段注入 / 失败分支 / 明细写入 / 一致性校验
    统一收进 persist_result，外部无需关心内部表结构。

    历史遗留的 3 个底层写方法（persist_daily / persist_trades /
    validate_consistency）降为私有，仅 WalkForwardPersister 这种
    需要手动构造明细的特殊场景可直接调用。
    """

    def __init__(self, dm: Any) -> None:
        self._dm = dm

    def _persist_daily(self, backtest_id: int, daily: list[dict[str, object]]) -> None:
        """写入每日资金曲线

        fail-fast（阶段 9）：写入失败直接上抛，让整个 run 终止。
        """
        if not daily:
            return
        self._dm.insert_backtest_daily(backtest_id, daily)

    def _persist_trades(self, backtest_id: int, trades: list[dict[str, object]]) -> None:
        """写入交易明细

        fail-fast（阶段 9）：写入失败直接上抛，让整个 run 终止。
        """
        if not trades:
            return
        self._dm.insert_backtest_trades(backtest_id, trades)

    def _validate_consistency(self, backtest_id: int) -> None:
        """校验数据一致性，发现不一致仅打 warning（非异常路径）

        fail-fast（阶段 9）：校验过程本身若抛异常（如 DB 读取失败）直接上抛；
        而"数据不一致"是业务告警，保留 warning 不中断。
        """
        errors = self._dm.validate_consistency(backtest_id)
        if errors:
            for err in errors:
                logger.warning("数据一致性警告: {}", err)

    def persist_result(
        self,
        result: BacktestResult,
        *,
        run_id: int | None = None,
        data_src: str | None = None,
        skip_validation: bool = False,
        strategy_params: dict[str, Any] | None = None,
        git_hash: str | None = None,
    ) -> int:
        """写入完整的背测结果

        封装以下步骤：
        - 设置 strategy_params / git_hash（若传入）
        - 根据 result.success 自动设置 status
        - 失败的只写主记录，成功的全量写入（daily/trades/校验）
        """
        if strategy_params is not None:
            result.strategy_params = {
                key: value for key, value in strategy_params.items() if isinstance(value, bool | int | float)
            }
        if git_hash is not None:
            result.git_hash = git_hash
        result.status = STATUS_SUCCESS if result.success else STATUS_FAILED

        bt_id: int = self._dm.insert_backtest(result, run_id=run_id, data_src=data_src)

        if not result.success:
            return bt_id

        if result.daily_results:
            self._persist_daily(bt_id, result.daily_results)
        if result.fills:
            self._persist_trades(bt_id, result.fills)
        if not skip_validation:
            self._validate_consistency(bt_id)
        return bt_id


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
            "study_db": self._dm.store.db_path,
        }
        all_ids: list[int] = []
        for i, trial in enumerate(result.trial_data):
            trial_cfg = {**engine_cfg, "trial_index": i}
            for er in trial.get("engine_results", []):
                er.engine_config = trial_cfg

                sym = er.symbol
                data_src = next((f for s, _, f in datasets if s == sym), None)
                bt_id = self._bt_persister.persist_result(
                    er,
                    run_id=run_id,
                    data_src=data_src,
                    strategy_params=trial.get("strategy_params", {}),
                    git_hash=git_hash,
                )
                if er.success:
                    all_ids.append(bt_id)

        return all_ids


class WalkForwardPersister:
    """Walk-Forward 结果的持久化

    将 wf_result（WalkForwardResult）转为 BacktestResult，写入主记录 + daily + trades。
    """

    def __init__(self, dm: Any) -> None:
        self._bt_persister = BacktestResultPersister(dm)

    def persist_walk_forward(
        self,
        wf_result: WalkForwardResult,
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
        aggregate = wf_result.aggregate
        if aggregate is None:
            raise ValueError("Walk-Forward 结果缺少 aggregate，无法持久化")
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
                "windows": wf_result.windows,
            },
            sharpe_ratio=aggregate.sharpe_mean,
            max_drawdown=aggregate.max_drawdown_mean,
            total_return=aggregate.return_mean,
            daily_std=aggregate.return_std,
        )
        result.success = True

        # 从各 window 聚合 daily_results / fills 写入明细表
        all_daily: list[dict[str, object]] = []
        all_trades: list[dict[str, object]] = []
        for wr in wf_result.window_results:
            all_daily.extend(wr.daily_results)
            all_trades.extend(wr.trades)
        result.daily_results = all_daily
        result.fills = all_trades  # BacktestResult.fills 承载 trades

        bt_id = self._bt_persister.persist_result(
            result,
            data_src=data_src,
            # 跳过一致性校验：WalkForward 的 BacktestResult 仅包含聚合指标，
            # 没有 total_trades/total_days/total_commission 等 summary 字段，
            # 校验会因 total_trades=0 vs 实际 trade 记录 >0 产生假阳性告警。
            skip_validation=True,
        )
        return bt_id
