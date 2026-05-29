# -*- coding: utf-8 -*-
"""
统一回测命令模块

提供基于 vn.py 和 TqSdk 的统一回测功能，根据标的数量自动选择回测引擎。

功能特点:
  - 单标的模式: 使用 TqSdk 进行图形化回测，支持 GUI 展示
  - 批量模式: 使用 vn.py 进行批量回测，生成文字报告并落地数据
  - 无缝切换: 根据标的数量自动选择合适的回测引擎
  - 数据落地: 回测结果统一持久化到数据库

模式:
  - search (默认): 参数搜索回测，optimizer 产多策略 × 多品种
  - walk-forward: 单策略滚动验证，评估稳健性

架构设计:
  CLI 层：负责 orchestrate、持久化回测结果
  backtest.runners: 批量回测编排 (数据加载、Walk-Forward、参数搜索)
  Optimizer 层：负责参数搜索逻辑，不做持久化
  Engine 层：负责运行单个回测

主要函数:
  cmd_backtest(): 主命令入口，解析参数并分发
  _run_tq_backtest(): 单品种回测，TqSdk 引擎
  _run_batch_backtest(): 批量回测，vn.py 引擎
  _persist_search_results(): 统一持久化
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import ConfigManager
from data import DataManager

from common.constants import (
    STATUS_SUCCESS,
    STATUS_FAILED,
    LOG_STATUS_INFO,
    LOG_STATUS_SUCCESS,
    LOG_STATUS_ERROR,
    MODE_SINGLE,
    MODE_BATCH,
    MODE_MULTI,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
)
from strategies.utils import (
    load_strategy,
    get_strategy_class_name,
    serialize_strategy_params,
)
from backtest import (
    VnpyBacktestEngine,
    load_batch_datasets,
    execute_walk_forward,
    execute_parameter_search,
    SearchResult,
)
from report import build_all as build_dashboard
from common.formulas import calculate_fifo_profit

logger = logging.getLogger(__name__)


def get_git_hash() -> str | None:
    """获取当前 Git 提交的短哈希值（7位）

    Returns:
        Git 提交哈希，如果不在 git 仓库中则返回 None
    """
    try:
        repo_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
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


def cmd_backtest(args: argparse.Namespace) -> None:
    """执行统一回测命令

    根据标的数量自动选择回测引擎:
      - 单标的 (--symbol 指定): 使用 TqSdk 回测，支持 GUI
      - 多标的 (--pattern 或省略 --symbol): 使用 vn.py 批量回测

    Args:
        args: argparse.Namespace 对象，包含:
            symbol: 品种代码（单品种模式）
            pattern: 品种代码正则表达式（批量模式）
            start: 开始日期（可选）
            end: 结束日期（可选）
            strategy: 策略名称（必填）
            capital: 初始资金（默认从配置文件读取）
            gui: 是否启用图形界面（仅单标的模式生效）
            mode: 回测模式 search|walk-forward (默认 search)
    """
    cm = ConfigManager()
    dm = DataManager(cm)

    symbol_arg: str | None = args.symbol  # pyright: ignore[reportAny]
    pattern_arg: str | None = args.pattern  # pyright: ignore[reportAny]
    is_single_mode = symbol_arg and not pattern_arg
    if is_single_mode:
        _run_tq_backtest(args, cm, dm)
    else:
        _run_batch_backtest(args, cm, dm)


def _run_tq_backtest(args: argparse.Namespace, cm: ConfigManager, dm: "DataManager") -> None:
    """使用 TqSdk 执行单标的回测

    Args:
        args: 命令行参数
        cm: ConfigManager 实例
        dm: DataManager 实例
    """
    from strategies import TqsdkStrategyBridge
    from common.tqsdk_imports import tqsdk

    strategy: str = args.strategy  # pyright: ignore[reportAny]
    symbol: str = args.symbol  # pyright: ignore[reportAny]
    start_date_str: str = args.start  # pyright: ignore[reportAny]
    end_date_str: str = args.end  # pyright: ignore[reportAny]
    gui_flag: bool = args.gui  # pyright: ignore[reportAny]
    capital_arg: float | None = args.capital  # pyright: ignore[reportAny]

    api = None
    strategy_cls = ""
    try:
        sc = cm.get_trading_config(strategy)
        account = cm.get_account_info()
        bc = cm.get_backtest_config()
        strategy_params = sc.model_dump(exclude={"name", "enabled"})
        capital = capital_arg if capital_arg else bc.initial_capital
        strategy_core = load_strategy(
            strategy,
            strategy_params=strategy_params,
            capital=capital,
            contract_size=bc.contract_size,
        )
        strategy_cls = get_strategy_class_name(strategy_core)

        bridge = TqsdkStrategyBridge(strategy=strategy_core, symbol=symbol)

        capital_val = capital_arg
        logger.info(
            "回测: %s %s~%s 资金=%s strategy=%s GUI=%s",
            symbol, start_date_str, end_date_str, capital_val, strategy_cls, gui_flag,
        )
        dm.store.log('backtest',
                     "开始: %s %s~%s 资金=%s strategy=%s" % (
                         symbol, start_date_str, end_date_str,
                         capital_val, strategy_cls,
                     ),
                     symbol=symbol, status=LOG_STATUS_INFO)

        auth = tqsdk.TqAuth(account.api_key, account.api_secret) if account else None
        api = tqsdk.TqApi(
            backtest=tqsdk.TqBacktest(
                start_dt=datetime.strptime(start_date_str, '%Y-%m-%d'),
                end_dt=datetime.strptime(end_date_str, '%Y-%m-%d')
            ),
            auth=auth, web_gui=gui_flag
        )
        klines = api.get_kline_serial(symbol, duration_seconds=sc.kline_period * 60)

        bridge.initialize(api)
        bridge._watch_klines(api, klines, symbol)  # pyright: ignore[reportPrivateUsage]

    except BacktestFinished:
        fills = getattr(strategy_core, 'fills', [])  # pyright: ignore[reportPossiblyUnboundVariable]

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

        bt_id = dm.insert_backtest(
            symbol=symbol,
            strategy=strategy_cls,
            status=STATUS_SUCCESS,
            error_message=None,
            statistics={
                'total_trades': total_trades,
                'total_profit': total_profit,
            },
            engine_config={'type': 'tqsdk', 'gui': gui_flag},
            params=serialize_strategy_params(strategy_core),  # pyright: ignore[reportPossiblyUnboundVariable]
            start_date=start_date_str,
            end_date=end_date_str,
        )

        if fills:
            trade_dicts = []
            for f in fills:
                trade_dicts.append({
                    'datetime': f.timestamp,
                    'action': f.action,
                    'price': f.price,
                    'volume': f.volume,
                    'reason': f.reason,
                })
            dm.insert_backtest_trades(bt_id, trade_dicts)

            logger.info("\n交易记录:")
            for f in fills:
                ts = f.timestamp[:10] if f.timestamp else "N/A"
                tag = "买入" if f.action == TRADE_ACTION_BUY else "卖出"
                logger.info(f"  {ts} {tag} {f.symbol} @ {f.price:.2f} x {f.volume}  原因: {f.reason}")

        dm.store.log('backtest', f"完成:\n{report}", symbol=symbol, status=LOG_STATUS_SUCCESS)
        print(f"\n💡 查看详细报告: python main.py report --id {bt_id}")

        if gui_flag and api is not None:
            logger.info("\n图形界面已启动，关闭浏览器或Ctrl+C退出...")
            try:
                while True:
                    api.wait_update()
except tqsdk.BacktestFinished:
                pass
    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        dm.store.log('backtest', f"失败: {e}", symbol=symbol, status=LOG_STATUS_ERROR)
        _ = dm.insert_backtest(
            symbol=symbol,
            strategy=strategy_cls or 'unknown',
            status=STATUS_FAILED,
            error_message=str(e),
            statistics={},
            engine_config={'type': 'tqsdk'},
            params={},
            start_date=None,
            end_date=None,
        )
        raise
    finally:
        if api:
            api.close()


def _run_batch_backtest(args: argparse.Namespace, cm: ConfigManager, dm: "DataManager") -> None:
    """使用 vn.py 执行批量回测或参数搜索

    编排数据加载、策略配置、引擎执行、结果持久化的完整工作流。
    支持两种模式:
      - search: 参数搜索，多品种
      - walk-forward: Walk-Forward 滚动验证

    Args:
        args: argparse.Namespace 命令行参数
        cm: ConfigManager 配置管理器
        dm: DataManager 数据管理器
    """
    strategy_name: str = args.strategy  # pyright: ignore[reportAny]
    symbol_arg: str | None = args.symbol  # pyright: ignore[reportAny]
    pattern_arg: str | None = args.pattern  # pyright: ignore[reportAny]
    start_arg: str | None = args.start  # pyright: ignore[reportAny]
    end_arg: str | None = args.end  # pyright: ignore[reportAny]
    capital_arg: float | None = args.capital  # pyright: ignore[reportAny]
    contract_size_arg: int | None = args.contract_size  # pyright: ignore[reportAny]
    trials_arg: int | None = args.trials  # pyright: ignore[reportAny]
    mode: str = args.mode  # pyright: ignore[reportAny]
    optimizer_arg: str | None = args.optimizer  # pyright: ignore[reportAny]

    try:
        bc = cm.get_backtest_config()

        # ── 步骤 1: 确定品种列表 ──
        if symbol_arg and not pattern_arg:
            symbol_list = [symbol_arg]
            mode_label = MODE_SINGLE
        else:
            symbol_list = dm.search_symbols(pattern_arg or "")
            if not symbol_list:
                logger.error("未找到匹配的品种数据")
                dm.store.log('backtest', "未找到匹配的品种数据",
                             symbol=MODE_MULTI, status=LOG_STATUS_ERROR)
                return
            mode_label = MODE_BATCH

        mode_name = "参数搜索" if mode == "search" else "Walk-Forward"
        logger.info("%s回测: %d 个品种 strategy=%s mode=%s",
                    "批量" if mode_label == MODE_BATCH else "单品种",
                    len(symbol_list), strategy_name, mode_name)

        # ── 步骤 2: 加载批量数据 ──
        datasets = load_batch_datasets(dm, symbol_list, start_arg, end_arg, bc.interval)
        if not datasets:
            logger.error("所有品种数据加载失败")
            return

        # ── 步骤 3: 加载策略配置 ──
        sc = cm.get_trading_config(strategy_name)
        strategy_params = sc.model_dump(exclude={"name", "enabled"})
        capital = capital_arg if capital_arg else bc.initial_capital
        contract_size = contract_size_arg if contract_size_arg else bc.contract_size

        # ── 步骤 4: 初始化引擎和 Git 信息 ──
        engine = VnpyBacktestEngine(bc, dm)
        git_hash = get_git_hash()

        # 创建运行记录
        run_engine = optimizer_arg or cm._config.optimizer.engine or "grid"
        run_id = dm.store.create_run(
            strategy=strategy_name,
            engine=run_engine if mode == "search" else "walk-forward",
            symbols=len(datasets),
        )

        # ── 步骤 5: 根据模式执行相应工作流 ──
        if mode == "walk-forward":
            wf_result, strategy, sym = execute_walk_forward(
                engine=engine,
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                capital=capital,
                contract_size=contract_size,
                datasets=datasets,
            )
            bt_id = None
            if wf_result.get('success'):
                bt_id = dm.insert_backtest(
                    symbol=sym,
                    strategy=get_strategy_class_name(strategy),
                    status=STATUS_SUCCESS,
                    error_message=None,
                    statistics=wf_result.get('aggregate', {}),
                    engine_config={'type': 'vnpy', 'mode': 'walk-forward',
                                   'windows': wf_result.get('windows', 0)},
                    params=serialize_strategy_params(strategy),
                    start_date=start_arg,
                    end_date=end_arg,
                    strategy_version=getattr(strategy, 'VERSION', None),
                    git_hash=git_hash,
                    run_id=run_id,
                    data_src=datasets[0][2],
                )
                logger.info(f"Walk-Forward 完成: id={bt_id}, "
                           f"窗口={wf_result.get('windows', 0)}")
                if bt_id:
                    print(f"\n💡 查看报告: python main.py report --id {bt_id}")
                    dm.store.log('backtest',
                                f"Walk-Forward 完成: {sym}",
                                symbol=sym, status=LOG_STATUS_SUCCESS)
            else:
                logger.error(f"Walk-Forward 失败: {wf_result.get('error')}")
        else:
            optimizer_cfg = cm._config.optimizer  # pyright: ignore[reportPrivateUsage]
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
            if result:
                # CLI 统一持久化
                bt_ids = _persist_search_results(
                    dm=dm,
                    result=result,
                    datasets=datasets,
                    search_type=optimizer_arg or cm._config.optimizer.engine or "grid",
                    study_name=result.study_name,
                    git_hash=git_hash,
                    run_id=run_id,
                )

                # 自动生成回测看板
                dm.store.finish_run(run_id)
                build_dashboard(
                    output_dir="output",
                    run_id=run_id,
                )

    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        dm.store.log('backtest', f"失败: {e}",
                     symbol=symbol_arg or MODE_MULTI, status=LOG_STATUS_ERROR)
        raise


def _persist_search_results(
    dm: DataManager,
    result: SearchResult,
    datasets: list[tuple[str, pd.DataFrame, str]],
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
        'type': 'vnpy',
        'optimizer': search_type,
        'study_name': study_name,
        'study_db': dm.store.db_path,
    }
    all_ids: list[int] = []
    for i, trial in enumerate(result.trial_data):
        trial_cfg = {**engine_cfg, 'trial_index': i}
        for er in trial.get('engine_results', []):
            if not er.get('success'):
                # 失败的 engine_result 仍然持久化，标记为失败
                dm.insert_backtest(
                    symbol=er.get('symbol', 'unknown'),
                    strategy=er.get('strategy_name', ''),
                    status=STATUS_FAILED,
                    error_message=er.get('error'),
                    engine_config=trial_cfg,
                    params=trial.get('search_params', {}),
                    run_id=run_id,
                    data_src=next(
                        (f for s, _, f in datasets if s == er.get('symbol')),
                        None,
                    ),
                )
                continue

            sym = er['symbol']
            data_src = next((f for s, _, f in datasets if s == sym), None)

            bt_id = dm.insert_backtest(
                symbol=sym,
                strategy=er.get('strategy_name', ''),
                status=STATUS_SUCCESS,
                error_message=None,
                statistics=er.get('statistics', {}),
                engine_config=trial_cfg,
                params=trial.get('search_params', {}),
                start_date=er.get('start_date'),
                end_date=er.get('end_date'),
                strategy_version=er.get('strategy_version'),
                git_hash=git_hash,
                run_id=run_id,
                data_src=data_src,
            )
            all_ids.append(bt_id)

            # 保存交易明细 + 每日资金曲线
            daily = er.get('daily_results', [])
            if daily:
                trades = []
                for d in daily:
                    if 'trades' in d:
                        trades.extend(
                            vars(t) if hasattr(t, '__dataclass_fields__') else t
                            for t in d.get('trades', [])
                        )
                if trades:
                    dm.insert_backtest_trades(bt_id, trades)
                dm.insert_backtest_daily(bt_id, daily)

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
            ids_str = ', '.join(str(i) for i in all_ids[:10])
            print(f"\n💡 查看报告: python main.py report --id <ID>  (可用 ID: {ids_str})")

    return all_ids
