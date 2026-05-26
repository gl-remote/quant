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
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

import pandas as pd

from config import ConfigManager
from data import DataManager

if TYPE_CHECKING:
    from backtest import VnpyBacktestEngine
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
from strategies.core import (
    load_strategy,
    get_strategy_class_name,
    serialize_strategy_params,
)
from optimizer import OptunaOptimizer
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
        _run_vnpy_backtest(args, cm, dm)


def _run_tq_backtest(args: argparse.Namespace, cm: ConfigManager, dm: "DataManager") -> None:
    """使用 TqSdk 执行单标的回测"""
    from tqsdk import TqApi, TqAuth, TqBacktest  # pyright: ignore[reportMissingTypeStubs]
    from tqsdk.exceptions import BacktestFinished  # pyright: ignore[reportMissingTypeStubs]
    from strategies import TqsdkStrategyBridge

    strategy: str = args.strategy  # pyright: ignore[reportAny]
    symbol: str = args.symbol  # pyright: ignore[reportAny]
    start_date_str: str = args.start  # pyright: ignore[reportAny]
    end_date_str: str = args.end  # pyright: ignore[reportAny]
    gui_flag: bool = args.gui  # pyright: ignore[reportAny]
    capital_arg: float | None = args.capital  # pyright: ignore[reportAny]

    api: TqApi | None = None
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

        auth = TqAuth(account.api_key, account.api_secret) if account else None
        api = TqApi(
            backtest=TqBacktest(
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
            params_json=serialize_strategy_params(strategy_core),  # pyright: ignore[reportPossiblyUnboundVariable]
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
            except BacktestFinished:
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
            params_json='{}',
            start_date=None,
            end_date=None,
        )
        raise
    finally:
        if api:
            api.close()


def _run_vnpy_backtest(args: argparse.Namespace, cm: ConfigManager, dm: "DataManager") -> None:
    """使用 vn.py 执行批量回测

    编排 data → optimizer → backtest 三层，结果持久化到数据库。

    模式:
      - search:  参数搜索，多策略 × 多品种
      - walk-forward: 单策略滚动验证
    """
    from backtest import VnpyBacktestEngine

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

        # ── 数据加载 ──
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

        datasets: list[tuple[str, pd.DataFrame]] = []
        for sym in symbol_list:
            df = dm.load_kline_safe(sym, start_arg, end_arg, bc.interval)
            if df is None or df.empty:
                logger.warning(f"跳过 {sym}: 数据加载失败")
                continue
            datasets.append((sym, df))

        if not datasets:
            logger.error("所有品种数据加载失败")
            return

        # ── 策略配置 ──
        sc = cm.get_trading_config(strategy_name)
        strategy_params = sc.model_dump(exclude={"name", "enabled"})
        capital = capital_arg if capital_arg else bc.initial_capital
        contract_size = contract_size_arg if contract_size_arg else bc.contract_size

        # ── 引擎执行 ──
        engine = VnpyBacktestEngine(bc, dm)
        git_hash = get_git_hash()

        if mode == "walk-forward":
            # W-F: 单策略 × 单品种，内部切窗口
            strategy = load_strategy(
                strategy_name,
                strategy_params=strategy_params,
                capital=capital,
                contract_size=contract_size,
            )
            sym = datasets[0][0]
            df = datasets[0][1]
            wf_result = engine.run_walk_forward(data=df, symbol=sym, strategy=strategy)

            if wf_result.get('success'):
                # 将 W-F 聚合结果作为一条回测记录落地
                bt_id = dm.insert_backtest(
                    symbol=sym,
                    strategy=get_strategy_class_name(strategy),
                    status=STATUS_SUCCESS,
                    error_message=None,
                    statistics=wf_result.get('aggregate', {}),
                    engine_config={'type': 'vnpy', 'mode': 'walk-forward',
                                   'windows': wf_result.get('windows', 0)},
                    params_json=serialize_strategy_params(strategy),
                    start_date=start_arg,
                    end_date=end_arg,
                    strategy_version=getattr(strategy, 'VERSION', None),
                    git_hash=git_hash,
                )
                logger.info(f"Walk-Forward 完成: id={bt_id}, "
                            f"窗口={wf_result.get('windows', 0)}")
                print(f"\n💡 查看报告: python main.py report --id {bt_id}")
                dm.store.log('backtest',
                             f"Walk-Forward 完成: {sym} {wf_result.get('windows', 0)} 窗口",
                             symbol=sym, status=LOG_STATUS_SUCCESS)
            else:
                logger.error(f"Walk-Forward 失败: {wf_result.get('error')}")
                dm.store.log('backtest',
                             f"Walk-Forward 失败: {wf_result.get('error')}",
                             symbol=sym, status=LOG_STATUS_ERROR)
        else:
            # ── search 模式: optimizer 调度 engine ──
            optimizer_cfg = cm._config.optimizer  # pyright: ignore[reportPrivateUsage]
            # CLI 参数优先，其次 TOML engine 字段
            opt_engine = optimizer_arg or optimizer_cfg.engine or "grid"
            n_trials = trials_arg if trials_arg else optimizer_cfg.n_trials

            # 优先使用策略专属搜索空间 (sc.search_space)，其次使用 optimizer 配置
            search_space = sc.search_space or optimizer_cfg.strategy_spaces.get(strategy_name, {}) or optimizer_cfg.search_space
            
            if search_space:
                if opt_engine == "optuna":
                    _run_optuna_search(
                        engine=engine, datasets=datasets,
                        strategy_name=strategy_name,
                        search_space=search_space,
                        strategy_params=strategy_params,
                        capital=capital,
                        contract_size=contract_size,
                        n_trials=n_trials,
                        dm=dm, git_hash=git_hash,
                        table_prefix=optimizer_cfg.table_prefix,
                    )
                else:
                    # 使用 Optuna GridSampler 进行网格搜索
                    _run_grid_search(
                        engine=engine, datasets=datasets,
                        strategy_name=strategy_name,
                        param_grid={k: v.get("choices", list(range(v.get("low", 0), v.get("high", 10)+1, v.get("step", 1)))) 
                                  for k, v in search_space.items()},
                        strategy_params=strategy_params,
                        capital=capital,
                        contract_size=contract_size,
                        optimizer_enabled=optimizer_cfg.enabled,
                        dm=dm, git_hash=git_hash,
                        n_trials=n_trials,
                    )

    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        dm.store.log('backtest', f"失败: {e}",
                     symbol=symbol_arg or MODE_MULTI, status=LOG_STATUS_ERROR)
        raise


def _persist_results(
    dm: DataManager,
    results: list[dict[str, Any]],
    git_hash: str | None,
) -> list[int]:
    """将引擎返回的结构化回测结果持久化到数据库

    每个 result dict 自包含 strategy_name / strategy_params_json /
    strategy_version，不再需要外部统一传入。

    Args:
        dm: 数据管理器
        results: engine.run() 返回的结果列表
        git_hash: Git 提交哈希

    Returns:
        成功写入的 backtest ID 列表
    """
    bt_ids: list[int] = []
    for r in results:
        if r.get('success'):
            st = r.get('statistics', {})
            dr = r.get('daily_results', [])
            ec = r.get('engine_config', {})

            bt_id = dm.insert_backtest(
                symbol=r['symbol'],
                strategy=r.get('strategy_name', ''),
                status=STATUS_SUCCESS,
                error_message=None,
                statistics=st,
                engine_config=ec,
                params_json=r.get('strategy_params_json', '{}'),
                start_date=r.get('start_date'),
                end_date=r.get('end_date'),
                strategy_version=r.get('strategy_version'),
                git_hash=git_hash,
            )
            bt_ids.append(bt_id)

            if dr:
                # 1. 保存交易明细 (vnpy TradeData dataclass → dict)
                trades = []
                for daily in dr:
                    if 'trades' in daily:
                        trades.extend(vars(t) if hasattr(t, '__dataclass_fields__') else t
                                      for t in daily.get('trades', []))
                if trades:
                    dm.insert_backtest_trades(bt_id, trades)

                # 2. 保存每日资金曲线
                dm.insert_backtest_daily(bt_id, dr)

            logger.info(f"[{r['symbol']}] 回测完成 id={bt_id}")

            # 输出回测摘要
            total_return = st.get('total_return', 0)
            sharpe = st.get('sharpe_ratio', 0)
            trades_count = st.get('total_trades', 0)
            print(f"  [{r['symbol']}] {r.get('strategy_name', '')} "
                  f"收益率={total_return:.2%}  夏普={sharpe:.2f}  交易={trades_count}次")
        else:
            _ = dm.insert_backtest(
                symbol=r.get('symbol', 'unknown'),
                strategy=r.get('strategy_name', ''),
                status=STATUS_FAILED,
                error_message=r.get('error'),
                statistics={},
                engine_config={},
                params_json=r.get('strategy_params_json', '{}'),
                start_date=None,
                end_date=None,
            )

    persisted = len(bt_ids)
    if persisted > 0:
        logger.info(f"回测结果已写入数据库: {persisted} 条成功")
        if persisted == 1:
            print(f"\n💡 查看详细报告: python main.py report --id {bt_ids[0]}")
        else:
            ids_str = ', '.join(str(i) for i in bt_ids)
            print(f"\n💡 查看报告: python main.py report --id <ID>  (可用 ID: {ids_str})")

    return bt_ids


# ──────────────────────────────────────────────────────────────
# search 模式辅助函数
# ──────────────────────────────────────────────────────────────


def _run_grid_search(
    engine: VnpyBacktestEngine,
    datasets: list[tuple[str, pd.DataFrame]],
    strategy_name: str,
    param_grid: dict[str, list[Any]],
    strategy_params: dict[str, Any],
    capital: float,
    contract_size: int,
    optimizer_enabled: bool,
    dm: DataManager,
    git_hash: str | None,
    n_trials: int = 100,
) -> None:
    """网格搜索：使用 Optuna GridSampler 穷举所有参数组合"""

    if optimizer_enabled and param_grid:
        # 将 param_grid 转换为 search_space 格式
        search_space = {}
        for param_name, values in param_grid.items():
            if values:
                search_space[param_name] = {
                    "type": "categorical",
                    "choices": values
                }
        
        # 使用 OptunaOptimizer + GridSampler
        opt = OptunaOptimizer(
            engine=engine,
            datasets=datasets,
            strategy_name=strategy_name,
            search_space=search_space,
            strategy_params=strategy_params,
            capital=capital,
            contract_size=contract_size,
            n_trials=n_trials,
            search_type="grid",
        )
        result = opt.optimize()
        # 从 trial_data 提取 engine_results
        results = []
        for trial in result.trial_data:
            results.extend(trial.get('engine_results', []))
        logger.info("Grid Search: %d 试验, %d 结果",
                    len(result.trial_data), len(results))
    else:
        # 未启用或空 param_grid → 单策略回退
        s = load_strategy(strategy_name,
                          strategy_params=strategy_params,
                          capital=capital, contract_size=contract_size)
        pairs = [(sym, df, s) for sym, df in datasets]
        results = engine.run(pairs)

    _persist_results(dm, results, git_hash)

    succeeded = [r for r in results if r['success']]
    if succeeded:
        dm.store.log('backtest',
                     f"回测完成: {len(succeeded)}/{len(results)}",
                     symbol='_batch_', status=LOG_STATUS_SUCCESS)


def _run_optuna_search(
    engine: VnpyBacktestEngine,
    datasets: list[tuple[str, pd.DataFrame]],
    strategy_name: str,
    search_space: dict[str, dict[str, Any]],
    strategy_params: dict[str, Any],
    capital: float,
    contract_size: int,
    n_trials: int,
    dm: DataManager,
    git_hash: str | None,
    table_prefix: str = "optuna_",
) -> None:
    """Optuna 贝叶斯优化：optimizer 调度 engine，持久化全部 trial 结果"""

    # 构建带表名前缀的数据库 URL
    optuna_db_url = f"sqlite:///{os.path.abspath(dm._store.db_path)}?table_prefix={table_prefix}"

    opt = OptunaOptimizer(
        engine=engine,
        datasets=datasets,
        strategy_name=strategy_name,
        search_space=search_space,
        strategy_params=strategy_params,
        capital=capital,
        contract_size=contract_size,
        n_trials=n_trials,
        study_db_path=optuna_db_url,
    )
    result = opt.optimize()

    # ── 持久化全部 trial ──
    engine_cfg = {
        'type': 'vnpy',
        'optimizer': 'optuna',
        'study_name': opt.study_name,
        'study_db': dm._store.db_path,  # 共享主数据库
    }
    all_ids: list[int] = []
    for i, trial_entry in enumerate(result.trial_data):
        trial_cfg = {**engine_cfg, 'trial_index': i}
        for engine_result in trial_entry['engine_results']:
            if engine_result.get('success'):
                bt_id = dm.insert_backtest(
                    symbol=engine_result['symbol'],
                    strategy=engine_result.get('strategy_name', strategy_name),
                    status=STATUS_SUCCESS,
                    error_message=None,
                    statistics=engine_result.get('statistics', {}),
                    engine_config=trial_cfg,  # pyright: ignore[reportArgumentType]
                    params_json=trial_entry.get('params_json', '{}'),
                    start_date=engine_result.get('start_date'),
                    end_date=engine_result.get('end_date'),
                    strategy_version=engine_result.get('strategy_version'),
                    git_hash=git_hash,
                )
                all_ids.append(bt_id)

                dr = engine_result.get('daily_results', [])
                if dr:
                    trades: list[dict[str, Any]] = []
                    for daily in dr:
                        if 'trades' in daily:
                            trades.extend(vars(t) if hasattr(t, '__dataclass_fields__') else t
                                          for t in daily.get('trades', []))  # pyright: ignore[reportUnknownArgumentType]
                    if trades:
                        dm.insert_backtest_trades(bt_id, trades)  # pyright: ignore[reportUnknownArgumentType]
                    dm.insert_backtest_daily(bt_id, dr)  # pyright: ignore[reportUnknownArgumentType]

    result.backtest_ids = all_ids

    # ── 输出摘要 + 日志 ──
    logger.info("Optuna 优化完成: best_value=%.4f best_params=%s trials=%d",
                result.best_value, result.best_params, len(result.trial_data))
    print("\n============ Optuna 优化结果 ============")
    print(f"  最优得分:  {result.best_value:.4f}")
    print(f"  最优参数:  {result.best_params}")
    print(f"  总试验数:  {len(result.trial_data)}")
    print(f"  回测ID:    {all_ids[:10]}{'...' if len(all_ids) > 10 else ''}")
    print(f"  Study:     {opt.study_name}")
    print("===========================================\n")

    # ── 生成优化报告 ──
    study_db_url = f"sqlite:///{os.path.abspath(dm._store.db_path)}"
    _build_optimization_report(
        result, all_ids, study_db_url, dm
    )

    dm.store.log('backtest',
                 f"Optuna 优化完成: best={result.best_value:.4f} "
                 f"params={result.best_params} trials={len(result.trial_data)}",
                 symbol='_optuna_', status=LOG_STATUS_SUCCESS)


def _build_optimization_report(
    result: Any,
    backtest_ids: list[int],
    study_db_url: str,
    dm: DataManager,
) -> None:
    """生成 Optuna 优化报告 HTML 文件"""
    # 忽略 dm 参数（预留给后续扩展）
    _ = dm

    from pathlib import Path
    from report import build_optimizer_report

    output_dir = "output"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        html = build_optimizer_report(
            study_db_url=study_db_url,
            study_name=result.study.study_name,
            best_params=result.best_params,
            best_value=result.best_value,
            backtest_ids=backtest_ids,
        )
        report_path = os.path.join(
            output_dir, f"optimization_{result.study.study_name}.html"
        )
        Path(report_path).write_text(html, encoding='utf-8')
        logger.info(f"优化报告已生成: {report_path}")
        print(f"\n💡 Optuna 优化报告: {report_path}")
    except Exception as e:
        logger.warning(f"优化报告生成失败: {e}", exc_info=True)
