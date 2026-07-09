"""回测命令级编排（阶段 3.5：多入口拆分）

提供三种独立工作流，每个工作流的请求对象字段最小化：

- `run_vnpy_search(req: VnpySearchRequest)`：vnpy 批量参数搜索
- `run_vnpy_walk_forward(req: VnpyWalkForwardRequest)`：vnpy Walk-Forward 滚动验证
- `run_tqsdk(req: TqsdkRequest)`：TqSdk 单标的回测

设计要点：
- workflow 不感知 `engine` / `mode` 字段（CLI 概念，不是业务概念）
- 每个 *Request 字段最小化、类型自洽（如 `TqsdkRequest.symbol: str` 而非 `str | None`）
- 引擎选择 / 参数校验 / argparse Namespace 翻译由 commands 层负责

不在本阶段范围（移交后续阶段）：
- `_persist_search_results` 拆分（阶段 4）
- engine 状态注入清理（阶段 5）
- TqSdk 接入 RunLogHelper / RunFinalizer / 持久化服务（阶段 10）
"""

from __future__ import annotations

import cProfile
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from backtest import (
    BacktestResultPersister,
    SearchResult,
    SearchResultPersister,
    VnpyBacktestEngine,
    WalkForwardPersister,
    load_strategy_and_config,
)
from common.constants import (
    LOG_STATUS_ERROR,
    LOG_STATUS_INFO,
    LOG_STATUS_SUCCESS,
    MODE_MULTI,
    MODE_SINGLE,
    STATUS_FAILED,
    STATUS_SUCCESS,
)
from common.schemas import KlineDataFrame
from common.types import BacktestResult
from config import ConfigManager
from config.schemas import BacktestConfig
from data import DataManager
from loguru import logger
from strategies.core import Strategy
from strategies.runtime.aggregate import parse_period_minutes
from strategies.runtime.data_feed import DataFeed
from strategies.utils import (
    apply_strategy_config,
    get_strategy_class_name,
    load_strategy,
    serialize_strategy_params,
)

from cli.workflows.backtests_lifecycle import RunFinalizer, RunLogHelper

# ── 请求对象（每个工作流字段最小化） ──────────────────────


@dataclass(frozen=True)
class VnpySearchRequest:
    """vnpy 批量参数搜索请求"""

    strategy: str
    capital: float | None
    contract_size: int | None
    symbol: str | None  # 标的过滤
    pattern: str | None  # 标的过滤
    start: str | None
    end: str | None
    optimizer: str | None
    trials: int | None
    parallel: bool
    workers: int | None
    profile: bool = False
    no_search: bool = False
    dump_indicators: bool = False
    early_stop_patience: int | None = None
    strategy_param_overrides: dict[str, Any] | None = None
    no_report: bool = False


@dataclass(frozen=True)
class VnpyWalkForwardRequest:
    """vnpy Walk-Forward 滚动验证请求"""

    strategy: str
    capital: float | None
    contract_size: int | None
    symbol: str | None
    pattern: str | None
    start: str | None
    end: str | None
    no_report: bool = False
    # 阶段 7 在此扩展窗口参数


@dataclass(frozen=True)
class TqsdkRequest:
    """TqSdk 单标的回测请求

    `symbol` / `start` / `end` 由 commands 层校验后传入，类型上必填。
    """

    strategy: str
    symbol: str  # 必需
    start: str  # 必需
    end: str  # 必需
    capital: float | None
    gui: bool


# ── Workflow ─────────────────────────────────────────────


class BacktestRunWorkflow:
    """命令级回测编排者。

    提供三个公开入口：
      - `run_vnpy_search(req)`：vnpy 批量参数搜索
      - `run_vnpy_walk_forward(req)`：vnpy Walk-Forward
      - `run_tqsdk(req)`：TqSdk 单标的回测

    workflow 不感知 `engine` / `mode` 等 CLI 字段，路由由 commands 层完成。
    workflow 自持 `RunLogHelper` / `RunFinalizer`，CLI 不再手动管理日志。
    """

    def __init__(self, cm: ConfigManager | None = None, dm: DataManager | None = None) -> None:
        self._cm = cm or ConfigManager(env="backtest")
        self._dm = dm or DataManager(self._cm)

    # ── vnpy 参数搜索 ──────────────────────────────────

    def run_vnpy_search(self, req: VnpySearchRequest) -> None:
        """vnpy 批量参数搜索（含串行 / 并行）"""
        bc = self._cm.get_backtest_config()
        strategy_params = self._strategy_params(req.strategy, req.strategy_param_overrides)
        interval = self._strategy_required_interval(req.strategy, strategy_params, bc.interval)
        bc = bc.model_copy(update={"interval": interval})

        datasets = self._load_datasets(req.symbol, req.pattern, req.start, req.end, bc.interval)
        if datasets is None:
            return

        self._log_run_header(MODE_MULTI, datasets, req.strategy, "参数搜索", req.symbol, req.pattern)

        engine = VnpyBacktestEngine(bc)
        git_hash = get_git_hash()
        engine.set_git_hash(git_hash)

        run_engine_label = req.optimizer or self._cm.get_optimizer_config().engine or "grid"
        run_id = self._dm.store.create_run(
            strategy=req.strategy,
            engine=run_engine_label,
            symbols=len(datasets),
        )
        engine.set_run_id(run_id)

        log_helper = RunLogHelper()
        finalizer = RunFinalizer(self._dm, log_helper, skip_report_build=req.no_report)
        log_helper.attach(run_id)

        try:
            self._do_vnpy_search(
                engine=engine,
                req=req,
                bc=bc,
                strategy_params=strategy_params,
                datasets=datasets,
                git_hash=git_hash,
                run_id=run_id,
                finalizer=finalizer,
            )
        except Exception as e:
            self._handle_vnpy_failure(req.symbol, e, run_id, finalizer)
            raise
        finally:
            log_helper.detach()

    # ── vnpy Walk-Forward ─────────────────────────────

    def run_vnpy_walk_forward(self, req: VnpyWalkForwardRequest) -> None:
        """vnpy Walk-Forward 滚动验证"""
        bc = self._cm.get_backtest_config()
        strategy_params = self._strategy_params(req.strategy)
        interval = self._strategy_required_interval(req.strategy, strategy_params, bc.interval)
        bc = bc.model_copy(update={"interval": interval})

        datasets = self._load_datasets(req.symbol, req.pattern, req.start, req.end, bc.interval)
        if datasets is None:
            return

        self._log_run_header(MODE_MULTI, datasets, req.strategy, "Walk-Forward", req.symbol, req.pattern)

        engine = VnpyBacktestEngine(bc)
        git_hash = get_git_hash()
        engine.set_git_hash(git_hash)

        run_id = self._dm.store.create_run(
            strategy=req.strategy,
            engine="walk-forward",
            symbols=len(datasets),
        )
        engine.set_run_id(run_id)

        log_helper = RunLogHelper()
        finalizer = RunFinalizer(self._dm, log_helper, skip_report_build=req.no_report)
        log_helper.attach(run_id)

        try:
            self._do_vnpy_walk_forward(
                engine=engine,
                req=req,
                bc=bc,
                strategy_params=strategy_params,
                datasets=datasets,
                git_hash=git_hash,
                run_id=run_id,
                finalizer=finalizer,
            )
        except Exception as e:
            self._handle_vnpy_failure(req.symbol, e, run_id, finalizer)
            raise
        finally:
            log_helper.detach()

    # ── TqSdk 单标的 ──────────────────────────────────

    def run_tqsdk(self, req: TqsdkRequest) -> None:
        """TqSdk 单标的回测（阶段 3 仅搬迁，未接 run 生命周期）

        阶段 10 将统一接入 RunLogHelper / RunFinalizer / 前端 JSON。
        """
        from common.tqsdk_imports import tqsdk
        from strategies.bridges.tqsdk_bridge import TqsdkStrategyBridge

        bc = self._cm.get_backtest_config()
        strategy_params = self._strategy_params(req.strategy)
        account = self._cm.get_account_info()
        git_hash = get_git_hash()

        # ── 加载策略核心 + 计算总天数 ──────
        strategy_core = load_strategy(req.strategy)
        strategy_cls = get_strategy_class_name(strategy_core)
        strategy_version = getattr(type(strategy_core), "VERSION", None)
        total_days = _calc_total_days(req.start, req.end)

        # ── 应用策略配置 ──────────────────
        from strategies.ma_strategy import MACrossParams

        strategy_config = MACrossParams()
        apply_strategy_config(strategy_config, self._cm)

        # ── 创建 State + 桥接 ────────────
        from strategies.core.state import State

        effective_capital = float(req.capital) if req.capital else float(bc.initial_capital)
        state = State(
            symbol=req.symbol,
            period=f"{strategy_params.get('kline_period', bc.interval)}m",
            strategy_config=strategy_config,
            capital=effective_capital,
            contract_size=int(bc.contract_size),
            margin=0.1,
        )
        bridge: TqsdkStrategyBridge[Any] = TqsdkStrategyBridge(strategy=cast(Strategy[Any], strategy_core), state=state)

        logger.info(
            "回测: {} {}~{} 资金={} strategy={} GUI={}",
            req.symbol,
            req.start,
            req.end,
            req.capital,
            strategy_cls,
            req.gui,
        )
        self._dm.store.log(
            "backtest",
            f"开始: {req.symbol} {req.start}~{req.end} 资金={req.capital} strategy={strategy_cls}",
            symbol=req.symbol,
            status=LOG_STATUS_INFO,
        )

        # ── 创建 TqApi 并执行 ────────────
        api = None
        try:
            auth = tqsdk.TqAuth(account.api_key, account.api_secret) if account else None
            api = tqsdk.TqApi(
                backtest=tqsdk.TqBacktest(
                    start_dt=datetime.strptime(req.start, "%Y-%m-%d"),
                    end_dt=datetime.strptime(req.end, "%Y-%m-%d"),
                ),
                auth=auth,
                web_gui=req.gui,
            )
            cast(Any, bridge).initialize(api)
            bridge.run(symbol=req.symbol)  # BacktestFinished 会正常传播
        except tqsdk.BacktestFinished:
            self._persist_tq_backtest_result(
                bridge=bridge,
                req=req,
                effective_capital=effective_capital,
                strategy_cls=strategy_cls,
                strategy_version=strategy_version,
                total_days=total_days,
                bc=bc,
                strategy_core=strategy_core,
                git_hash=git_hash,
            )
            if req.gui and api is not None:
                _tq_backtest_gui_loop(api)
        except Exception as e:
            logger.exception(f"回测执行失败: {e}")
            self._dm.store.log("backtest", f"失败: {e}", symbol=req.symbol, status=LOG_STATUS_ERROR)
            self._persist_tq_failure(
                req=req,
                effective_capital=effective_capital,
                strategy_cls=strategy_cls,
                strategy_version=strategy_version,
                total_days=total_days,
                bc=bc,
                git_hash=git_hash,
                error=str(e),
            )
            raise
        finally:
            if api:
                api.close()

    # ── vnpy 公共部分 ──────────────────────────────────

    def _strategy_params(self, strategy_name: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        sc = self._cm.get_strategy_config(strategy_name or "ma")
        params = sc.model_dump(exclude={"name", "enabled", "kline_period", "search_space"})
        if overrides:
            params.update(overrides)
        return params

    @staticmethod
    def _strategy_required_interval(strategy_name: str, strategy_params: dict[str, Any], default_interval: str) -> str:
        strategy_cls, strategy_config = load_strategy_and_config(strategy_name, strategy_params)
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
            logger.info(
                "策略 {} 需要最小周期 {}，覆盖回测配置周期 {}",
                strategy_name,
                required_interval,
                default_interval,
            )
            return required_interval
        return default_interval

    def _load_datasets(
        self,
        symbol: str | None,
        pattern: str | None,
        start: str | None,
        end: str | None,
        interval: str,
    ) -> list[tuple[str, KlineDataFrame, str]] | None:
        """按 symbol/pattern 加载数据集；失败时打印日志并返回 None"""
        if symbol and not pattern:
            datasets = self._dm.load_kline([symbol], start, end, interval)
            if not datasets:
                logger.error("品种数据加载失败")
                return None
            return datasets

        datasets = self._dm.search_and_load(pattern or "", start, end, interval)
        if not datasets:
            logger.error("所有品种数据加载失败")
            return None
        return datasets

    @staticmethod
    def _log_run_header(
        mode_label: str,
        datasets: list[tuple[str, KlineDataFrame, str]],
        strategy: str,
        mode_name: str,
        symbol: str | None,
        pattern: str | None,
    ) -> None:
        is_single = bool(symbol) and not pattern
        actual_label = MODE_SINGLE if is_single else mode_label
        logger.info(
            "{}回测: {} 个品种 strategy={} mode={}",
            "批量" if actual_label == MODE_MULTI else "单品种",
            len(datasets),
            strategy,
            mode_name,
        )

    def _handle_vnpy_failure(
        self,
        symbol: str | None,
        error: Exception,
        run_id: int,
        finalizer: RunFinalizer,
    ) -> None:
        logger.exception(f"回测执行失败: {error}")
        finalizer.finish_failed(run_id, str(error))
        self._dm.store.log(
            "backtest",
            f"失败: {error}",
            symbol=symbol or MODE_MULTI,
            status=LOG_STATUS_ERROR,
        )

    # ── vnpy 参数搜索：内部步骤 ─────────────────────────

    def _do_vnpy_search(
        self,
        *,
        engine: VnpyBacktestEngine,
        req: VnpySearchRequest,
        bc: BacktestConfig,
        strategy_params: dict[str, Any],
        datasets: list[tuple[str, KlineDataFrame, str]],
        git_hash: str | None,
        run_id: int,
        finalizer: RunFinalizer,
    ) -> None:
        optimizer_cfg = self._cm.get_optimizer_config()
        n_trials = req.trials if req.trials else optimizer_cfg.n_trials
        early_stop_patience = (
            req.early_stop_patience if req.early_stop_patience is not None else optimizer_cfg.early_stop_patience
        )
        run_engine = req.optimizer or optimizer_cfg.engine or "grid"

        # 命令行 --no-search 覆盖配置 optimizer.enabled（单向：仅能关闭）
        search_enabled = optimizer_cfg.enabled and not req.no_search

        if not search_enabled:
            logger.info("参数搜索已关闭，降级为单次回测（用默认策略参数）")
            self._run_single_backtest(
                engine=engine,
                req=req,
                strategy_params=strategy_params,
                datasets=datasets,
                git_hash=git_hash,
                run_id=run_id,
                finalizer=finalizer,
            )
            return

        sc = self._cm.get_trading_config(req.strategy)
        search_space = (
            sc.search_space or optimizer_cfg.strategy_spaces.get(req.strategy, {}) or optimizer_cfg.search_space
        )
        if not search_space:
            logger.warning("搜索空间为空，跳过参数搜索")
            finalizer.finish_skipped(run_id)
            return

        capital = req.capital if req.capital else bc.initial_capital
        contract_size = req.contract_size if req.contract_size else bc.contract_size

        result = self._run_search(
            engine=engine,
            req=req,
            bc=bc,
            strategy_params=strategy_params,
            datasets=datasets,
            run_id=run_id,
            search_space=search_space,
            n_trials=n_trials,
            run_engine=run_engine,
            capital=capital,
            contract_size=contract_size,
            optimizer_cfg=optimizer_cfg,
            early_stop_patience=early_stop_patience,
        )
        if not result:
            finalizer.finish_no_result(run_id)
            return

        self._dm.store.update_run_seed(
            run_id=run_id,
            use_fixed_seed=optimizer_cfg.use_fixed_seed,
            random_seed=result.actual_seed,
        )

        # fail-fast（阶段 9）：持久化失败直接上抛，由顶层 _handle_vnpy_failure
        # 标记 run=failed + 落日志后非零退出，不再吞错继续收尾。
        search_persister = SearchResultPersister(self._dm)
        all_ids = search_persister.persist_search_result(
            result=result,
            datasets=cast(list[tuple[str, Any, str]], datasets),
            search_type=run_engine,
            study_name=result.study_name,
            git_hash=git_hash,
            run_id=run_id,
        )

        print(f"\n============ {run_engine.upper()} 优化结果 ============")
        print(f"  最优得分:  {result.best_value:.4f}")
        print(f"  最优参数:  {result.best_params}")
        print(f"  总试验数:  {result.n_trials}")
        print(f"  回测ID:    {all_ids[:10]}{'...' if len(all_ids) > 10 else ''}")
        print(f"  Study:     {result.study_name}")
        print("===========================================\n")
        if all_ids:
            if len(all_ids) == 1:
                print(f"\n💡 查看详细报告: python main.py report --id {all_ids[0]}")
            else:
                ids_str = ", ".join(str(i) for i in all_ids[:10])
                print(f"\n💡 查看报告: python main.py report --id <ID>  (可用 ID: {ids_str})")

        finalizer.finish_success(run_id)

    def _run_single_backtest(
        self,
        *,
        engine: VnpyBacktestEngine,
        req: VnpySearchRequest,
        strategy_params: dict[str, Any],
        datasets: list[tuple[str, KlineDataFrame, str]],
        git_hash: str | None,
        run_id: int,
        finalizer: RunFinalizer,
    ) -> None:
        """不搜索参数，用默认策略参数跑单次回测（支持 --profile / --dump-indicators）"""
        DataFeed.dump_indicators_default = req.dump_indicators
        pairs = [(s, d, req.strategy, strategy_params) for s, d, _ in datasets]
        if req.profile:
            from data.output_paths import profiles_dir

            profile_path = profiles_dir() / f"backtest_{req.strategy}_{datetime.now():%Y%m%d_%H%M%S}.prof"
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profiler = cProfile.Profile()
            engine_results = profiler.runcall(cast(Any, engine.run), cast(Any, pairs))
            profiler.dump_stats(str(profile_path))
            logger.info("性能分析结果已保存: {}", profile_path)
            logger.info("查看方式: snakeviz {}", profile_path)
        else:
            engine_results = engine.run(cast(Any, pairs))

        bt_persister = BacktestResultPersister(self._dm)
        for er in engine_results:
            data_src = next((f for s, _, f in datasets if s == er.symbol), None)
            bt_persister.persist_result(
                er,
                run_id=run_id,
                data_src=data_src,
                strategy_params=strategy_params,
                git_hash=git_hash,
            )

        finalizer.finish_success(run_id)

    def _run_search(
        self,
        *,
        engine: VnpyBacktestEngine,
        req: VnpySearchRequest,
        bc: BacktestConfig,
        strategy_params: dict[str, Any],
        datasets: list[tuple[str, KlineDataFrame, str]],
        run_id: int,
        search_space: dict[str, Any],
        n_trials: int,
        run_engine: str,
        capital: float,
        contract_size: int,
        optimizer_cfg: Any,
        early_stop_patience: int = 0,
    ) -> SearchResult | None:
        """实际执行串行 / 并行搜索的分发

        _do_vnpy_search 已做完前置校验（搜索空间非空 + optimizer.enabled）。
        """
        from backtest.optuna_study import link_study, make_study_name

        study_name = make_study_name(req.strategy, run_engine, run_id)
        link_study(run_id, study_name)

        if req.parallel:
            from backtest.parallel import run_param_search_parallel

            datasets_simple = cast(list[tuple[str, Any]], [(s, d) for s, d, _ in datasets])

            return run_param_search_parallel(
                datasets=datasets_simple,
                strategy_name=req.strategy,
                search_space=search_space,
                strategy_params=strategy_params,
                backtest_config=bc,
                data_env=self._cm.get_data_config().environment,
                run_id=run_id,
                n_trials=n_trials,
                search_type=run_engine,
                n_workers=req.workers,
                study_name=study_name,
                random_seed=optimizer_cfg.random_seed,
                use_fixed_seed=optimizer_cfg.use_fixed_seed,
                early_stop_patience=early_stop_patience,
            )

        # 串行路径：直接调 optimizer.py 的 run_param_search
        from backtest.optimizer import run_param_search

        return run_param_search(
            engine=engine,
            datasets=[(s, d) for s, d, _ in datasets],
            strategy_name=req.strategy,
            search_space=search_space,
            strategy_params=strategy_params,
            capital=capital,
            contract_size=contract_size,
            n_trials=n_trials,
            search_type=run_engine,
            study_name=study_name,
            random_seed=optimizer_cfg.random_seed,
            use_fixed_seed=optimizer_cfg.use_fixed_seed,
        )

    # ── vnpy Walk-Forward：内部步骤 ─────────────────────

    def _do_vnpy_walk_forward(
        self,
        *,
        engine: VnpyBacktestEngine,
        req: VnpyWalkForwardRequest,
        bc: BacktestConfig,
        strategy_params: dict[str, Any],
        datasets: list[tuple[str, KlineDataFrame, str]],
        git_hash: str | None,
        run_id: int,
        finalizer: RunFinalizer,
    ) -> None:
        sym = datasets[0][0]
        df = datasets[0][1]
        wf_result = engine.run_walk_forward(
            data=df,
            symbol=sym,
            strategy_name=req.strategy,
            strategy_params=strategy_params,
        )

        if wf_result.success:
            strategy = load_strategy(req.strategy)
            wf_persister = WalkForwardPersister(self._dm)
            bt_id = wf_persister.persist_walk_forward(
                wf_result=wf_result,
                symbol=sym,
                strategy=get_strategy_class_name(strategy),
                strategy_params=serialize_strategy_params(strategy),
                strategy_version=getattr(type(strategy), "VERSION", None),
                git_hash=git_hash,
                start_date=req.start,
                end_date=req.end,
                data_src=datasets[0][2],
            )
            logger.info(f"Walk-Forward 完成: id={bt_id}, 窗口={wf_result.windows}")
            print(f"\n💡 查看报告: python main.py report --id {bt_id}")
            self._dm.store.log("backtest", f"Walk-Forward 完成: {sym}", symbol=sym, status=LOG_STATUS_SUCCESS)
        else:
            logger.error(f"Walk-Forward 失败: {wf_result.error}")

        finalizer.finish_success(run_id)

    # ── TqSdk 持久化 ──────────────────────────────────

    def _persist_tq_backtest_result(
        self,
        *,
        bridge: Any,
        req: TqsdkRequest,
        effective_capital: float,
        strategy_cls: str,
        strategy_version: str | None,
        total_days: int | None,
        bc: BacktestConfig,
        strategy_core: Any,
        git_hash: str | None,
    ) -> None:
        """TqSdk 结果持久化：FIFO 计算盈亏 → 写入数据库 → 输出日志"""
        from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL
        from common.formulas import calculate_fifo_profit

        fills = bridge.fills
        total_profit = calculate_fifo_profit(fills)
        total_trades = len([f for f in fills if f.action == TRADE_ACTION_SELL])

        report = (
            f"{'=' * 60}\n"
            f"回测报告\n"
            f"{'=' * 60}\n"
            f"策略: {strategy_cls}\n"
            f"品种: {req.symbol}\n"
            f"区间: {req.start} ~ {req.end}\n"
            f"初始资金: {effective_capital:,.2f}\n\n"
            f"交易统计:\n"
            f"  总交易次数: {total_trades}\n"
            f"  总盈亏: {total_profit:,.2f}\n"
            f"{'=' * 60}"
        )
        print(report)

        bt_id = self._dm.insert_backtest(
            BacktestResult(
                symbol=req.symbol,
                strategy=strategy_cls,
                strategy_version=strategy_version,
                git_hash=git_hash,
                status=STATUS_SUCCESS,
                total_trades=total_trades,
                total_return=total_profit,
                end_balance=effective_capital + total_profit,
                start_date=req.start,
                end_date=req.end,
                total_days=total_days,
                initial_capital=effective_capital,
                commission_rate=bc.commission_rate,
                slippage=bc.slippage,
                price_tick=bc.price_tick,
                contract_size=bc.contract_size,
                kline_interval=bc.interval,
                strategy_params=serialize_strategy_params(strategy_core),
                engine_config={"type": "tqsdk", "gui": False},
            )
        )

        if fills:
            trade_dicts = [
                {
                    "datetime": f.timestamp,
                    "symbol": f.symbol,
                    "direction": "long" if f.action == TRADE_ACTION_BUY else "short",
                    "offset": "open",
                    "open_price": f.price,
                    "close_price": f.price,
                    "quantity": f.volume,
                    "pnl": 0.0,
                    "commission": 0.0,
                    "reason": f.reason,
                    "decision_payload_json": json.dumps(f.decision_payload, ensure_ascii=False)
                    if f.decision_payload
                    else None,
                }
                for f in fills
            ]
            self._dm.insert_backtest_trades(bt_id, trade_dicts)

            logger.info("\n交易记录:")
            for f in fills:
                ts = f.timestamp[:10] if f.timestamp else "N/A"
                tag = "买入" if f.action == TRADE_ACTION_BUY else "卖出"
                logger.info(f"  {ts} {tag} {f.symbol} @ {f.price:.2f} x {f.volume}  原因: {f.reason}")

        self._dm.store.log("backtest", f"完成:\n{report}", symbol=req.symbol, status=LOG_STATUS_SUCCESS)
        print(f"\n💡 查看详细报告: python main.py report --id {bt_id}")

    def _persist_tq_failure(
        self,
        *,
        req: TqsdkRequest,
        effective_capital: float,
        strategy_cls: str,
        strategy_version: str | None,
        total_days: int | None,
        bc: BacktestConfig,
        git_hash: str | None,
        error: str,
    ) -> None:
        """TqSdk 失败路径占位记录"""
        result = BacktestResult(
            symbol=req.symbol,
            strategy=strategy_cls or "unknown",
            strategy_version=strategy_version,
            git_hash=git_hash,
            status=STATUS_FAILED,
            error_message=error,
            start_date=req.start,
            end_date=req.end,
            total_days=total_days,
            initial_capital=effective_capital,
            commission_rate=bc.commission_rate,
            slippage=bc.slippage,
            price_tick=bc.price_tick,
            contract_size=bc.contract_size,
            kline_interval=bc.interval,
            engine_config={"type": "tqsdk"},
        )
        self._dm.insert_backtest(result)


# ── 模块级辅助 ──────────────────────────────────────────


def get_git_hash() -> str | None:
    """获取当前 Git 提交的短哈希值（7位）"""
    try:
        repo_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.warning(f"获取 Git 哈希失败: {e}")
    return None


def _calc_total_days(start: str, end: str) -> int | None:
    """根据日期字符串计算总天数；解析失败返回 None"""
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        return (end_dt - start_dt).days + 1
    except (ValueError, TypeError):
        return None


def _tq_backtest_gui_loop(api: Any) -> None:
    """GUI 模式下的等待循环（阻塞直到用户关闭浏览器）"""
    logger.info("\n图形界面已启动，关闭浏览器或Ctrl+C退出...")
    try:
        while True:
            api.wait_update()
    except Exception:
        pass
