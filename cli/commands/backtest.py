# -*- coding: utf-8 -*-
"""
统一回测命令模块

提供基于 vn.py 和 TqSdk 的统一回测功能，根据标的数量自动选择回测引擎。

功能特点:
    - 单标的模式: 使用 TqSdk 进行图形化回测，支持 GUI 展示
    - 批量模式: 使用 vn.py 进行批量回测，生成文字报告并落地数据
    - 无缝切换: 根据标的数量自动选择合适的回测引擎
    - 数据落地: 回测结果统一持久化到数据库
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

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
    DEFAULT_INITIAL_CAPITAL,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
)
from strategies.core import (
    load_strategy,
    get_strategy_class_name,
    serialize_strategy_params,
)
from common.formulas import calculate_fifo_profit

logger = logging.getLogger(__name__)


def get_git_hash() -> Optional[str]:
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


def cmd_backtest(args):
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
            strategy: 策略名称（可选）
            capital: 初始资金（默认 100000）
            gui: 是否启用图形界面（仅单标的模式生效）
    """
    cm = ConfigManager()
    dm = DataManager(cm)

    is_single_mode = args.symbol and not args.pattern
    if is_single_mode:
        _run_tq_backtest(args, cm, dm)
    else:
        _run_vnpy_backtest(args, cm, dm)


def _run_tq_backtest(args, cm, dm):
    """使用 TqSdk 执行单标的回测"""
    from tqsdk import TqApi, TqAuth, TqBacktest
    from tqsdk.exceptions import BacktestFinished
    from strategies import TqsdkStrategyBridge

    api = None
    try:
        sc = cm.get_trading_config(args.strategy)
        account = cm.get_account_info()
        bc = cm.get_backtest_config()
        strategy_params = sc.model_dump(exclude={"name", "enabled"})
        capital = args.capital if args.capital else bc.initial_capital
        strategy_core = load_strategy(
            args.strategy,
            strategy_params=strategy_params,
            capital=capital,
            contract_size=bc.contract_size,
        )
        strategy_cls = get_strategy_class_name(strategy_core)

        bridge = TqsdkStrategyBridge(strategy=strategy_core, symbol=args.symbol)

        logger.info(
            f"回测: {args.symbol} {args.start}~{args.end} 资金={args.capital} "
            f"strategy={strategy_cls} GUI={args.gui}"
        )
        dm.store.log('backtest',
               f"开始: {args.symbol} {args.start}~{args.end} 资金={args.capital} "
               f"strategy={strategy_cls}",
               symbol=args.symbol, status=LOG_STATUS_INFO)

        auth = TqAuth(account.api_key, account.api_secret) if account else None
        api = TqApi(
            backtest=TqBacktest(
                start_dt=datetime.strptime(args.start, '%Y-%m-%d'),
                end_dt=datetime.strptime(args.end, '%Y-%m-%d')
            ),
            auth=auth, web_gui=args.gui
        )
        klines = api.get_kline_serial(args.symbol, duration_seconds=sc.kline_period * 60)

        bridge.initialize(api)
        bridge._watch_klines(api, klines, args.symbol)

    except BacktestFinished:
        fills = getattr(strategy_core, 'fills', [])

        total_profit = calculate_fifo_profit(fills)
        total_trades = len([f for f in fills if f.action == TRADE_ACTION_SELL])

        report = (
            f"{'=' * 60}\n"
            f"回测报告\n"
            f"{'=' * 60}\n"
            f"策略: {strategy_cls}\n"
            f"品种: {args.symbol}\n"
            f"区间: {args.start} ~ {args.end}\n"
            f"初始资金: {args.capital:,.2f}\n\n"
            f"交易统计:\n"
            f"  总交易次数: {total_trades}\n"
            f"  总盈亏: {total_profit:,.2f}\n"
            f"{'=' * 60}"
        )
        print(report)

        bt_id = dm.insert_backtest(
            symbol=args.symbol,
            strategy=strategy_cls,
            status=STATUS_SUCCESS,
            error_message=None,
            statistics={
                'total_trades': total_trades,
                'total_profit': total_profit,
            },
            engine_config={'type': 'tqsdk', 'gui': args.gui},
            params_json=serialize_strategy_params(strategy_core),
            start_date=args.start,
            end_date=args.end,
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

        dm.store.log('backtest', f"完成:\n{report}", symbol=args.symbol, status=LOG_STATUS_SUCCESS)
        print(f"\n💡 查看详细报告: python main.py report --id {bt_id}")

        if args.gui:
            logger.info("\n图形界面已启动，关闭浏览器或Ctrl+C退出...")
            try:
                while True:
                    api.wait_update()
            except BacktestFinished:
                pass
    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        dm.store.log('backtest', f"失败: {e}", symbol=args.symbol, status=LOG_STATUS_ERROR)
        dm.insert_backtest(
            symbol=args.symbol,
            strategy=get_strategy_class_name(strategy_core) if 'strategy_core' in locals() else 'unknown',
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


def _run_vnpy_backtest(args, cm, dm):
    """使用 vn.py 执行批量回测"""
    from backtest import VnpyBacktestEngine

    try:
        bc = cm.get_backtest_config()

        if args.symbol and not args.pattern:
            symbols = [(args.symbol, None)]
            mode = MODE_SINGLE
        else:
            symbols = [(sym, None) for sym in dm.search_symbols(args.pattern)]
            if not symbols:
                logger.error("未找到匹配的品种数据")
                dm.store.log('backtest', "未找到匹配的品种数据", symbol=MODE_MULTI, status=LOG_STATUS_ERROR)
                return
            mode = MODE_BATCH

        logger.info(
            f"{'单品种' if mode == MODE_SINGLE else '批量'}回测: {len(symbols)} 个品种"
            f" strategy={args.strategy or 'ma'}"
        )

        all_results = []
        failed = []
        for sym, _ in symbols:
            sc = cm.get_trading_config(args.strategy)
            strategy_params = sc.model_dump(exclude={"name", "enabled"})
            capital = args.capital if args.capital else bc.initial_capital
            strategy = load_strategy(
                args.strategy,
                strategy_params=strategy_params,
                capital=capital,
                contract_size=bc.contract_size,
            )
            params_json = serialize_strategy_params(strategy)
            strategy_name = get_strategy_class_name(strategy)
            strategy_version = getattr(strategy, 'VERSION', None)

            engine = VnpyBacktestEngine(bc)
            try:
                result = engine.run_full_pipeline(
                    symbol=sym,
                    start_date=args.start or None,
                    end_date=args.end or None,
                    strategy=strategy,
                )
                all_results.append(result)
                if not result.get('success'):
                    failed.append(sym)
            except Exception as e:
                logger.error(f"{sym} 回测异常: {e}", exc_info=True)
                all_results.append({'success': False, 'symbol': sym, 'error': str(e)})
                failed.append(sym)

        succeeded = [r for r in all_results if r.get('success')]
        logger.info(
            f"回测完成: {len(succeeded)}/{len(all_results)} 成功"
            + (f", 失败: {failed}" if failed else "")
        )

        bt_ids: List[int] = []
        for i, r in enumerate(all_results):
            if r.get('success'):
                st = r['result'].get('statistics', {})
                dr = r['result'].get('daily_results', [])
                ec = r.get('engine_config', {})
                bt_id = dm.insert_backtest(
                    symbol=r['symbol'],
                    strategy=strategy_name,
                    status=STATUS_SUCCESS,
                    error_message=None,
                    statistics=st,
                    engine_config=ec,
                    params_json=params_json,
                    start_date=r.get('start_date'),
                    end_date=r.get('end_date'),
                    strategy_version=strategy_version,
                    git_hash=git_hash,
                )
                bt_ids.append(bt_id)
                
                if dr:
                    # 1. 保存交易明细（从 daily_results 中提取 trades）
                    trades = []
                    for daily in dr:
                        if 'trades' in daily:
                            trades.extend(daily.get('trades', []))
                    if trades:
                        trade_count = dm.insert_backtest_trades(bt_id, trades)
                        logger.debug(f"  {r['symbol']}: 写入 {trade_count} 条交易明细")
                    
                    # 2. 保存每日资金曲线
                    daily_count = dm.insert_backtest_daily(bt_id, dr)
                    logger.debug(f"  {r['symbol']}: 写入 {daily_count} 条每日资金曲线")
                
                logger.info(f"\n>>> [{r['symbol']}] 回测完成 id={bt_id}")

                # 输出回测摘要
                st = r['result'].get('statistics', {})
                total_return = st.get('total_return', 0)
                sharpe = st.get('sharpe_ratio', 0)
                trades_count = st.get('total_trades', 0)
                print(f"\n  [{r['symbol']}] 收益率={total_return:.2%}  夏普={sharpe:.2f}  交易={trades_count}次")
            else:
                dm.insert_backtest(
                    symbol=r.get('symbol', 'unknown'),
                    strategy=strategy_name,
                    status=STATUS_FAILED,
                    error_message=r.get('error'),
                    statistics={},
                    engine_config={},
                    params_json=params_json,
                    start_date=None,
                    end_date=None,
                )

        persisted = len(bt_ids)
        if persisted > 0:
            logger.info(f"回测结果已写入数据库: {persisted} 条成功")
            if mode == MODE_BATCH:
                ids_str = ', '.join(str(i) for i in bt_ids)
                print(f"\n💡 查看报告: python main.py report --id <ID>  (可用 ID: {ids_str})")
            else:
                print(f"\n💡 查看详细报告: python main.py report --id {bt_ids[0]}")

        if succeeded:
            dm.store.log('backtest',
                   f"{'批量' if mode == MODE_BATCH else ''}回测完成: "
                   f"{len(succeeded)}/{len(all_results)}, "
                   f"已写入 {persisted} 条 DB 记录",
                   symbol=MODE_MULTI if mode == MODE_BATCH else args.symbol,
                   status=LOG_STATUS_SUCCESS)
        else:
            dm.store.log('backtest', f"回测全部失败",
                   symbol=MODE_MULTI if mode == MODE_BATCH else args.symbol,
                   status=LOG_STATUS_ERROR)

    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        dm.store.log('backtest', f"失败: {e}", symbol=args.symbol or MODE_MULTI, status=LOG_STATUS_ERROR)
        raise