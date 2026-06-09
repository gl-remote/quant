"""统一回测命令模块

提供基于 vn.py 和 TqSdk 的统一回测功能，根据标的数量自动选择回测引擎。

模式:
  - search (默认): 参数搜索回测，optimizer 产多策略 × 多品种
  - walk-forward: 单策略滚动验证，评估稳健性

架构:
  CLI 层: 负责 orchestrate、持久化回测结果
  backtest.runners: 批量回测编排（数据加载、Walk-Forward、参数搜索）
  Optimizer 层: 负责参数搜索逻辑，不做持久化
  Engine 层: 负责运行单个回测

重构说明（2026-06-06）：
  - 原 `_run_tq_backtest` / `_run_batch_backtest` 均为 150+ 行的过程式函数
  - 拆分为准备阶段、执行阶段、持久化阶段三类辅助函数
  - 新增 `_prepare_backtest_config` / `_persist_results` 等公共辅助，消除重复逻辑
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from backtest import (
    SearchResult,
    VnpyBacktestEngine,
    execute_parameter_search,
    execute_walk_forward,
)
from common.constants import (
    LOG_STATUS_ERROR,
    LOG_STATUS_INFO,
    LOG_STATUS_SUCCESS,
    MODE_BATCH,
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
from report import build_all as build_dashboard
from strategies.utils import (
    apply_strategy_config,
    get_strategy_class_name,
    load_strategy,
    serialize_strategy_params,
)

# ── 公共辅助 ─────────────────────────────────────────────


def get_git_hash() -> str | None:
    """获取当前 Git 提交的短哈希值（7位）"""
    try:
        repo_root = Path(__file__).parent.parent.parent
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


def _prepare_backtest_config(
    args: argparse.Namespace,
    cm: ConfigManager,
) -> tuple[BacktestConfig, dict[str, Any], str | None, float | None, int | None]:
    """从命令行参数 + 配置中心抽取公共回测配置项

    Returns:
        (bc, strategy_params, mode_override, capital_arg, contract_size_arg)
    """
    bc = cm.get_backtest_config()
    sc = cm.get_strategy_config(getattr(args, "strategy", "ma") or "ma")
    strategy_params = sc.model_dump(exclude={"name", "enabled", "kline_period", "search_space"})
    mode_arg: str = getattr(args, "mode", "search") or "search"
    capital_arg: float | None = getattr(args, "capital", None)
    contract_size_arg: int | None = getattr(args, "contract_size", None)
    return bc, strategy_params, mode_arg, capital_arg, contract_size_arg


def _persist_results(
    dm: DataManager,
    results: list[BacktestResult] | BacktestResult,
    run_id: int | None = None,
    data_src: str | None = None,
) -> None:
    """通用持久化：将 BacktestResult 写入数据库（单条或批量）

    为 TqSdk 单标的场景提供简洁持久化。
    """
    if isinstance(results, BacktestResult):
        results = [results]
    for r in results:
        dm.insert_backtest(r, run_id=run_id, data_src=data_src)


# ── 命令入口 ────────────────────────────────────────────


def cmd_backtest(args: argparse.Namespace) -> None:
    """执行统一回测命令

    根据标的数量自动选择回测引擎:
      - 单标的 (--symbol 指定): 使用 TqSdk 回测，支持 GUI
      - 多标的 (--pattern 或省略 --symbol): 使用 vn.py 批量回测
    """
    cm = ConfigManager()
    dm = DataManager(cm)

    symbol_arg: str | None = args.symbol  # pyright: ignore[reportAny]
    pattern_arg: str | None = args.pattern  # pyright: ignore[reportAny]
    is_single_mode = bool(symbol_arg) and not pattern_arg
    if is_single_mode:
        _run_tq_backtest(args, cm, dm)
    else:
        _run_batch_backtest(args, cm, dm)


# ── TqSdk 单标的回测 ──────────────────────────────────


def _run_tq_backtest(
    args: argparse.Namespace,
    cm: ConfigManager,
    dm: DataManager,
) -> None:
    """使用 TqSdk 执行单标的回测

    流程: 配置解析 → 创建 TqApi + 策略桥 → 运行 → 提取结果 → 持久化
    """
    from common.tqsdk_imports import tqsdk
    from strategies import TqsdkStrategyBridge

    strategy: str = args.strategy  # pyright: ignore[reportAny]
    symbol: str = args.symbol  # pyright: ignore[reportAny]
    start_date_str: str = args.start  # pyright: ignore[reportAny]
    end_date_str: str = args.end  # pyright: ignore[reportAny]
    gui_flag: bool = args.gui  # pyright: ignore[reportAny]
    capital_arg: float | None = args.capital  # pyright: ignore[reportAny]

    bc, strategy_params, _, _, _ = _prepare_backtest_config(args, cm)
    account = cm.get_account_info()
    git_hash = get_git_hash()

    # ── 步骤 1: 加载策略核心 ────────────────────────────
    strategy_core = load_strategy(strategy)
    strategy_cls = get_strategy_class_name(strategy_core)
    strategy_version = getattr(type(strategy_core), "VERSION", None)

    # ── 步骤 2: 应用策略配置 ────────────────────────────
    from strategies.ma_strategy import MACrossParams

    strategy_config = MACrossParams()
    apply_strategy_config(strategy_config, cm)

    # ── 步骤 3: 计算总天数 ────────────────────────────
    try:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        total_days = (end_dt - start_dt).days + 1
    except (ValueError, TypeError):
        total_days = None

    # ── 步骤 4: 创建 State + 桥接 ─────────────────────
    from strategies.core.state import State

    state = State(
        symbol=symbol,
        period=f"{strategy_params.get('kline_period', bc.interval)}m",
        strategy_config=strategy_config,
        capital=float(capital_arg) if capital_arg else float(bc.initial_capital),
        contract_size=int(bc.contract_size),
        margin=0.1,
    )

    bridge = TqsdkStrategyBridge(strategy=strategy_core, state=state)

    logger.info(
        "回测: %s %s~%s 资金=%s strategy=%s GUI=%s",
        symbol,
        start_date_str,
        end_date_str,
        capital_arg,
        strategy_cls,
        gui_flag,
    )
    dm.store.log(
        "backtest",
        f"开始: {symbol} {start_date_str}~{end_date_str} 资金={capital_arg} strategy={strategy_cls}",
        symbol=symbol,
        status=LOG_STATUS_INFO,
    )

    # ── 步骤 5: 创建 TqApi 并执行 ────────────────────
    api = None
    try:
        auth = tqsdk.TqAuth(account.api_key, account.api_secret) if account else None
        api = tqsdk.TqApi(
            backtest=tqsdk.TqBacktest(
                start_dt=datetime.strptime(start_date_str, "%Y-%m-%d"),
                end_dt=datetime.strptime(end_date_str, "%Y-%m-%d"),
            ),
            auth=auth,
            web_gui=gui_flag,
        )
        bridge.initialize(api)
        bridge.run(symbol=symbol)  # BacktestFinished 会正常传播

    except tqsdk.BacktestFinished:
        _persist_tq_backtest_result(
            dm=dm,
            bridge=bridge,
            symbol=symbol,
            strategy_cls=strategy_cls,
            strategy_version=strategy_version,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            total_days=total_days,
            capital_arg=capital_arg,
            bc=bc,
            strategy_core=strategy_core,
            git_hash=git_hash,
        )

        if gui_flag and api is not None:
            _tq_backtest_gui_loop(api, bridge, cm)

    except Exception as e:
        logger.exception(f"回测执行失败: {e}")
        dm.store.log("backtest", f"失败: {e}", symbol=symbol, status=LOG_STATUS_ERROR)
        # 记录失败的占位记录
        dm.insert_backtest(
            BacktestResult(
                symbol=symbol,
                strategy=strategy_cls or "unknown",
                strategy_version=strategy_version,
                git_hash=git_hash,
                status=STATUS_FAILED,
                error_message=str(e),
                start_date=start_date_str,
                end_date=end_date_str,
                total_days=total_days,
                initial_capital=capital_arg or bc.initial_capital,
                commission_rate=bc.commission_rate,
                slippage=bc.slippage,
                price_tick=bc.price_tick,
                contract_size=bc.contract_size,
                kline_interval=bc.interval,
                engine_config={"type": "tqsdk"},
            )
        )
        raise
    finally:
        if api:
            api.close()


def _persist_tq_backtest_result(
    dm: DataManager,
    bridge: Any,
    symbol: str,
    strategy_cls: str,
    strategy_version: str | None,
    start_date_str: str,
    end_date_str: str,
    total_days: int | None,
    capital_arg: float | None,
    bc: BacktestConfig,
    strategy_core: Any,
    git_hash: str | None,
) -> None:
    """TqSdk 结果持久化：计算盈亏 → 写入数据库 → 输出日志

    从 bridge.fills 提取成交记录，按 FIFO 计算总盈亏。
    """
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
        f"品种: {symbol}\n"
        f"区间: {start_date_str} ~ {end_date_str}\n"
        f"初始资金: {capital_arg:,.2f}\n\n"
        f"交易统计:\n"
        f"  总交易次数: {total_trades}\n"
        f"  总盈亏: {total_profit:,.2f}\n"
        f"{'=' * 60}"
    )
    print(report)

    # 主结果记录
    bt_id = dm.insert_backtest(
        BacktestResult(
            symbol=symbol,
            strategy=strategy_cls,
            strategy_version=strategy_version,
            git_hash=git_hash,
            status=STATUS_SUCCESS,
            total_trades=total_trades,
            total_return=total_profit,
            end_balance=capital_arg + total_profit if capital_arg else 0,
            start_date=start_date_str,
            end_date=end_date_str,
            total_days=total_days,
            initial_capital=capital_arg or bc.initial_capital,
            commission_rate=bc.commission_rate,
            slippage=bc.slippage,
            price_tick=bc.price_tick,
            contract_size=bc.contract_size,
            kline_interval=bc.interval,
            strategy_params=serialize_strategy_params(strategy_core),
            engine_config={"type": "tqsdk", "gui": False},
        )
    )

    # 成交记录
    if fills:
        trade_dicts = []
        for f in fills:
            direction = "long" if f.action == TRADE_ACTION_BUY else "short"
            trade_dicts.append(
                {
                    "datetime": f.timestamp,
                    "symbol": f.symbol,
                    "direction": direction,
                    "offset": "open",
                    "open_price": f.price,
                    "close_price": f.price,
                    "quantity": f.volume,
                    "pnl": 0.0,
                    "commission": 0.0,
                    "reason": f.reason,
                }
            )
        dm.insert_backtest_trades(bt_id, trade_dicts)

        logger.info("\n交易记录:")
        for f in fills:
            ts = f.timestamp[:10] if f.timestamp else "N/A"
            tag = "买入" if f.action == TRADE_ACTION_BUY else "卖出"
            logger.info(f"  {ts} {tag} {f.symbol} @ {f.price:.2f} x {f.volume}  原因: {f.reason}")

    dm.store.log("backtest", f"完成:\n{report}", symbol=symbol, status=LOG_STATUS_SUCCESS)
    print(f"\n💡 查看详细报告: python main.py report --id {bt_id}")


def _tq_backtest_gui_loop(api: Any, bridge: Any, cm: ConfigManager) -> None:
    """GUI 模式下的等待循环（阻塞直到用户关闭浏览器）"""
    logger.info("\n图形界面已启动，关闭浏览器或Ctrl+C退出...")
    try:
        while True:
            api.wait_update()
    except Exception:
        pass


# ── vn.py 批量回测 ─────────────────────────────────────


def _run_batch_backtest(
    args: argparse.Namespace,
    cm: ConfigManager,
    dm: DataManager,
) -> None:
    """使用 vn.py 执行批量回测或参数搜索

    流程: 解析参数 → 确定品种 → 加载数据 → 根据模式选择搜索/滚动 → 持久化
    """
    strategy_name: str = args.strategy  # pyright: ignore[reportAny]
    symbol_arg: str | None = args.symbol  # pyright: ignore[reportAny]
    pattern_arg: str | None = args.pattern  # pyright: ignore[reportAny]
    start_arg: str | None = args.start  # pyright: ignore[reportAny]
    end_arg: str | None = args.end  # pyright: ignore[reportAny]
    capital_arg: float | None = args.capital  # pyright: ignore[reportAny]
    contract_size_arg: int | None = args.contract_size  # pyright: ignore[reportAny]
    trials_arg: int | None = args.trials  # pyright: ignore[reportAny]
    optimizer_arg: str | None = args.optimizer  # pyright: ignore[reportAny]
    mode_arg: str = args.mode  # pyright: ignore[reportAny]

    try:
        bc, strategy_params, _, _, _ = _prepare_backtest_config(args, cm)

        # ── 步骤 1: 确定品种列表 ─────────────────────
        if symbol_arg and not pattern_arg:
            symbol_list = [symbol_arg]
            mode_label = MODE_SINGLE
        else:
            symbol_list = dm.search_symbols(pattern_arg or "")
            if not symbol_list:
                logger.error("未找到匹配的品种数据")
                dm.store.log(
                    "backtest",
                    "未找到匹配的品种数据",
                    symbol=MODE_MULTI,
                    status=LOG_STATUS_ERROR,
                )
                return
            mode_label = MODE_BATCH

        mode_name = "参数搜索" if mode_arg == "search" else "Walk-Forward"
        logger.info(
            "{}回测: {} 个品种 strategy={} mode={}",
            "批量" if mode_label == MODE_BATCH else "单品种",
            len(symbol_list),
            strategy_name,
            mode_name,
        )

        # ── 步骤 2: 加载批量数据 ─────────────────────
        datasets = dm.load_kline(symbol_list, start_arg, end_arg, bc.interval)
        if not datasets:
            logger.error("所有品种数据加载失败")
            return

        # ── 步骤 3: 初始化引擎 ───────────────────────
        engine = VnpyBacktestEngine(bc, dm)
        git_hash = get_git_hash()
        engine.set_git_hash(git_hash)

        # 创建运行记录
        run_engine_label = optimizer_arg or cm.get_optimizer_config().engine or "grid"
        run_id = dm.store.create_run(
            strategy=strategy_name,
            engine=run_engine_label if mode_arg == "search" else "walk-forward",
            symbols=len(datasets),
        )
        engine._run_id = run_id

        # 挂实时日志文件：DEBUG 全量 → output/r{run_id}/data/run.log
        _attach_run_logger(dm, run_id)

        # ── 步骤 4: 根据模式执行 ────────────────────
        if mode_arg == "walk-forward":
            _execute_walk_forward_mode(
                engine=engine,
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                capital=capital_arg if capital_arg else bc.initial_capital,
                contract_size=contract_size_arg if contract_size_arg else bc.contract_size,
                datasets=datasets,
                dm=dm,
                git_hash=git_hash,
                start_arg=start_arg,
                end_arg=end_arg,
            )
        else:
            _execute_search_mode(
                engine=engine,
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                capital=capital_arg if capital_arg else bc.initial_capital,
                contract_size=contract_size_arg if contract_size_arg else bc.contract_size,
                datasets=datasets,
                cm=cm,
                optimizer_arg=optimizer_arg,
                trials_arg=trials_arg,
                git_hash=git_hash,
                dm=dm,
                run_id=run_id,
            )

    except Exception as e:
        logger.exception(f"回测执行失败: {e}")
        dm.store.log(
            "backtest",
            f"失败: {e}",
            symbol=symbol_arg or MODE_MULTI,
            status=LOG_STATUS_ERROR,
        )
        raise
    finally:
        _detach_run_logger(dm)


def _attach_run_logger(dm: DataManager, run_id: int) -> None:
    """将 DEBUG 级别日志重定向到 output/r{run_id}/data/run.log"""
    from common.log_config import get_stderr_sink_id

    logs_dir = Path("output") / f"r{run_id}" / "data"
    logs_dir.mkdir(parents=True, exist_ok=True)
    fmt = (
        f"{{time:YYYY-MM-DD HH:mm:ss.SSS}} | [r{run_id}{{extra[bt_id]}}] "
        "{level: <8} | {name}:{function}:{line} | {message}"
    )
    _sink_ids = getattr(dm, "_sink_ids", [])
    _sink_ids.append(
        logger.add(
            logs_dir / "run.log",
            level="DEBUG",
            format=fmt,
        )
    )
    dm._sink_ids = _sink_ids  # pyright: ignore[reportPrivateUsage]

    stderr_id = get_stderr_sink_id()
    if stderr_id is not None:
        logger.remove(stderr_id)


def _detach_run_logger(dm: DataManager) -> None:
    """移除临时日志 sink，恢复 stderr"""
    for sid in getattr(dm, "_sink_ids", []):
        logger.remove(sid)
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        colorize=True,
    )


def _execute_walk_forward_mode(
    engine: VnpyBacktestEngine,
    strategy_name: str,
    strategy_params: dict[str, Any],
    capital: float,
    contract_size: int,
    datasets: list[tuple[str, KlineDataFrame, str]],
    dm: DataManager,
    git_hash: str | None,
    start_arg: str | None,
    end_arg: str | None,
) -> None:
    """Walk-Forward 模式执行与持久化"""
    wf_result, strategy, sym = execute_walk_forward(
        engine=engine,
        strategy_name=strategy_name,
        strategy_params=strategy_params,
        capital=capital,
        contract_size=contract_size,
        datasets=datasets,
    )
    bt_id = None
    if wf_result.get("success"):
        bt_id = dm.insert_backtest(
            BacktestResult(
                symbol=sym,
                strategy=get_strategy_class_name(strategy),
                status=STATUS_SUCCESS,
                strategy_version=getattr(strategy, "VERSION", None),
                git_hash=git_hash,
                strategy_params=serialize_strategy_params(strategy),
                start_date=start_arg,
                end_date=end_arg,
                engine_config={
                    "type": "vnpy",
                    "mode": "walk-forward",
                    "windows": wf_result.get("windows", 0),
                },
                sharpe_ratio=wf_result.get("aggregate", {}).get("sharpe_mean"),
                max_drawdown=wf_result.get("aggregate", {}).get("max_drawdown_mean"),
                total_return=wf_result.get("aggregate", {}).get("return_mean"),
                daily_std=wf_result.get("aggregate", {}).get("return_std"),
            ),
            data_src=datasets[0][2],
        )
        logger.info(f"Walk-Forward 完成: id={bt_id}, 窗口={wf_result.get('windows', 0)}")
        if bt_id:
            print(f"\n💡 查看报告: python main.py report --id {bt_id}")
            dm.store.log("backtest", f"Walk-Forward 完成: {sym}", symbol=sym, status=LOG_STATUS_SUCCESS)
    else:
        logger.error(f"Walk-Forward 失败: {wf_result.get('error')}")


def _execute_search_mode(
    engine: VnpyBacktestEngine,
    strategy_name: str,
    strategy_params: dict[str, Any],
    capital: float,
    contract_size: int,
    datasets: list[tuple[str, KlineDataFrame, str]],
    cm: ConfigManager,
    optimizer_arg: str | None,
    trials_arg: int | None,
    git_hash: str | None,
    dm: DataManager,
    run_id: int,
) -> None:
    """参数搜索模式执行与持久化"""
    optimizer_cfg = cm.get_optimizer_config()
    n_trials = trials_arg if trials_arg else optimizer_cfg.n_trials

    result = execute_parameter_search(
        engine=engine,
        strategy_name=strategy_name,
        strategy_params=strategy_params,
        capital=capital,
        contract_size=contract_size,
        datasets=datasets,
        n_trials=n_trials,
        optimizer_cfg=optimizer_cfg,
        cm=cm,
        optimizer_arg=optimizer_arg,
        git_hash=git_hash,
        dm=dm,
        run_id=run_id,
    )
    if not result:
        return

    # 保存实际使用的随机种子
    dm.store.update_run_seed(
        run_id=run_id,
        use_fixed_seed=optimizer_cfg.use_fixed_seed,
        random_seed=result.actual_seed,
    )

    # CLI 统一持久化
    _persist_search_results(
        dm=dm,
        result=result,
        datasets=datasets,
        search_type=optimizer_arg or cm.get_optimizer_config().engine or "grid",
        study_name=result.study_name,
        git_hash=git_hash,
        run_id=run_id,
    )

    # run.log → logs.json
    log_file = Path("output") / f"r{run_id}" / "data" / "run.log"
    if log_file.exists():
        with open(log_file, encoding="utf-8") as f:
            text = f.read()
        json_file = Path("output") / f"r{run_id}" / "data" / "logs.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(text, f, ensure_ascii=False)

    # 自动生成回测看板
    dm.store.finish_run(run_id)
    build_dashboard(output_dir="output", run_id=run_id)


# ── 参数搜索结果持久化 ───────────────────────────────


def _persist_search_results(
    dm: DataManager,
    result: SearchResult,
    datasets: list[tuple[str, KlineDataFrame, str]],
    search_type: str,
    study_name: str,
    git_hash: str | None,
    run_id: int | None = None,
) -> list[int]:
    """将 SearchResult 的 trial_data 统一持久化到数据库

    Args:
        dm: DataManager 实例
        result: run_param_search() 返回的搜索结果
        datasets: 原始 datasets（含 filepath），用于匹配 data_src
        search_type: "grid" 或 "bayesian"
        study_name: optuna study 名称
        git_hash: Git 提交哈希
        run_id: 运行记录 ID
    Returns:
        backtest_ids 列表
    """
    engine_cfg = {
        "type": "vnpy",
        "optimizer": search_type,
        "study_name": study_name,
        "study_db": dm.store.db_path,
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
                dm.insert_backtest(
                    er,
                    run_id=run_id,
                    data_src=next((f for s, _, f in datasets if s == er.symbol), None),
                )
                continue

            sym = er.symbol
            data_src = next((f for s, _, f in datasets if s == sym), None)
            er.status = STATUS_SUCCESS
            bt_id = dm.insert_backtest(er, run_id=run_id, data_src=data_src)
            all_ids.append(bt_id)

            daily = er.daily_results
            if daily:
                dm.insert_backtest_daily(bt_id, daily)

            if er.fills:
                dm.insert_backtest_trades(bt_id, er.fills)

            errors = dm.validate_consistency(bt_id)
            if errors:
                for err in errors:
                    logger.warning(f"数据一致性警告: {err}")

    # 输出摘要
    print(f"\n============ {search_type.upper()} 优化结果 ============")
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

    return all_ids
