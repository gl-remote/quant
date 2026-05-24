#!/usr/bin/env python3
"""天勤量化交易系统 - 均线交叉策略，支持数据导出、回测、实盘交易"""

import sys
import argparse
import dataclasses
import logging
import importlib
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import ConfigManager

cm = ConfigManager()
log_cfg = cm.get_system_logging_config()
logging.basicConfig(
    level=getattr(logging, log_cfg.get('level', 'INFO'), logging.INFO),
    format=log_cfg.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
from strategies import TqsdkStrategyBridge
from strategies.core import Strategy, TradingContext, Bar, Fill, Signal
from backtest import VnpyBacktestEngine, scan_csv_files
from backtest.comparison import generate_merged_report, format_merged_report
from data import Database, DBLogHandler, export_csv

logger = logging.getLogger(__name__)


# ============================================================
# 策略动态加载
# ============================================================
def load_strategy(strategy_name: Optional[str]) -> Strategy:
    """根据名称动态加载策略实例

    支持三种传入方式:
      - 简化名: "ma" → 找 strategies/ma_strategy.py
      - 完整名: "ma_strategy" → 找 strategies/ma_strategy.py
      - 带扩展名: "ma_strategy.py" → 找 strategies/ma_strategy.py

    Args:
        strategy_name: 策略名称，None 则默认使用 ma

    Returns:
        Strategy 实例

    Raises:
        FileNotFoundError: 策略文件不存在
    """
    if not strategy_name:
        strategy_name = "ma"

    name = strategy_name
    if name.endswith('.py'):
        name = name[:-3]
    if not name.endswith('_strategy'):
        name = f"{name}_strategy"

    strategies_dir = Path(__file__).parent / 'strategies'
    strategy_file = strategies_dir / f"{name}.py"

    if not strategy_file.exists():
        available = [f.stem for f in strategies_dir.glob('*_strategy.py')]
        raise FileNotFoundError(
            f"策略文件 {name}.py 不存在，可用策略: {', '.join(available)}"
        )

    module = importlib.import_module(f"strategies.{name}")

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (isinstance(attr, type) and
                issubclass(attr, Strategy) and
                attr is not Strategy and
                attr_name != 'Strategy'):
            return attr()

    raise ValueError(f"策略文件 {name}.py 中未找到 Strategy 实现类")


def _get_strategy_class_name(strategy: Strategy) -> str:
    """获取策略类名用于日志显示"""
    return type(strategy).__name__


# ============================================================
# TradingContext 构建
# ============================================================
def _build_context(strategy: Strategy, symbol: str, cm: ConfigManager,
                   capital: float = 100000.0) -> TradingContext:
    """从 ConfigManager 构建统一的 TradingContext

    Args:
        strategy: 策略实例
        symbol: 品种代码
        cm: 配置管理器
        capital: 初始资金 (可被 backtest config 覆盖)

    Returns:
        TradingContext 实例
    """
    bc = cm.get_backtest_config()
    account = cm.get_account_info()

    # 同步资金/合约乘数到 strategy.config，使策略能正确计算手数
    # 使用 dataclasses.fields() 校验字段合法性，避免 hasattr 静默失败
    cfg = strategy.config
    try:
        valid_keys = {f.name for f in dataclasses.fields(cfg)}
    except TypeError:
        valid_keys = set()

    if 'capital' in valid_keys:
        cfg.capital = capital
    elif hasattr(cfg, 'capital'):
        cfg.capital = capital

    if 'contract_size' in valid_keys:
        cfg.contract_size = bc.get('contract_size', 10)
    elif hasattr(cfg, 'contract_size'):
        cfg.contract_size = bc.get('contract_size', 10)

    return TradingContext(
        strategy=strategy,
        symbol=symbol,
        capital=capital,
        kline_period=cm.get_strategy_config().get('kline_period', 5),
        commission_rate=bc.get('commission_rate', 0.0003),
        slippage=bc.get('slippage', 1.0),
        price_tick=bc.get('price_tick', 1.0),
        contract_size=bc.get('contract_size', 10),
        account=account if account else None,
    )


def _apply_strategy_config(strategy: Strategy, cm: ConfigManager):
    """将配置文件中的策略参数应用到策略实例的 config 上

    通过 dataclasses.fields() 校验 YAML 配置键是否对应合法数据类字段，
    避免 hasattr 静默跳过未知键导致的配置未生效问题。
    """
    sc = cm.get_strategy_config(strategy.name)
    cfg = strategy.config
    try:
        valid_keys = {f.name for f in dataclasses.fields(cfg)}
    except TypeError:
        # 非 dataclass，回退到 hasattr 检查
        for key, value in sc.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return

    for key, value in sc.items():
        if key in valid_keys:
            setattr(cfg, key, value)
        else:
            logger.warning(
                f"忽略未识别的策略配置键: '{key}'，"
                f"合法键: {sorted(valid_keys)}"
            )


# ============================================================
# 公共工具
# ============================================================
def _setup_db_logging(db, command: str, symbol: str = None):
    handler = DBLogHandler(db, command=command, symbol=symbol)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(handler)


# ============================================================
# 子命令: export — 数据导出（最高优先级）
# ============================================================
def cmd_export(args):
    cm = ConfigManager()
    db = Database(cm.get_data_config()['db_path'])
    _setup_db_logging(db, 'export', args.symbol)

    logger.info(f"数据导出: {args.symbol} {args.start} ~ {args.end}")
    db.log('export', f"开始: {args.symbol} {args.start}~{args.end}",
           symbol=args.symbol, status='INFO')

    success = export_csv(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        db=db,
        config_manager=cm,
        output_path=args.output,
        force=args.force,
    )
    if success:
        logger.info("导出成功")
    else:
        logger.error("导出失败")
        sys.exit(1)


# ============================================================
# 子命令: test — 策略逻辑测试
# ============================================================
def cmd_test(args):
    cm = ConfigManager()
    db = Database(cm.get_data_config()['db_path'])
    _setup_db_logging(db, 'test')

    strategy = load_strategy(args.strategy or None)
    _apply_strategy_config(strategy, cm)
    cls_name = _get_strategy_class_name(strategy)

    logger.info("=" * 60)
    logger.info(f"测试模式 - 策略: {cls_name}")
    logger.info("=" * 60)
    db.log('test', f"开始: strategy={cls_name}", status='INFO')

    try:
        tc = cm.get_trading_config()
        logger.info(f"策略参数: SMA({tc.get('sma_short', 5)},{tc.get('sma_long', 20)}) "
                    f"止损={tc.get('stop_loss_ratio', 0.03):.0%} "
                    f"止盈={tc.get('take_profit_ratio', 0.05):.0%}")

        # 模拟连续K线: 先空仓→金叉买入→再一根K线触发止损
        bar1 = Bar(symbol="TEST", datetime="2026-01-01",
                   open=10, high=15, low=10, close=15, volume=1000)
        signal1 = strategy.on_bar(bar1)
        logger.info(f"信号1: action={signal1.action} reason={signal1.reason} volume={signal1.volume}")

        if signal1.action == 'buy':
            strategy.on_fill(Fill(
                timestamp=bar1.datetime, symbol=bar1.symbol,
                action='buy', price=bar1.close, volume=signal1.volume,
                reason=signal1.reason))

            bar2 = Bar(symbol="TEST", datetime="2026-01-02",
                       open=15, high=16, low=13, close=13.5, volume=500)
            signal2 = strategy.on_bar(bar2)
            logger.info(f"信号2: action={signal2.action} reason={signal2.reason}")

            if signal2.action == 'sell':
                strategy.on_fill(Fill(
                    timestamp=bar2.datetime, symbol=bar2.symbol,
                    action='sell', price=bar2.close, volume=signal1.volume,
                    reason=signal2.reason))

        p = strategy.performance
        logger.info(f"绩效: 交易{p.total_trades}次 胜{p.winning_trades} "
                    f"胜率{p.win_rate:.0%} 盈亏{p.total_profit:.2f}")
        db.log('test', f"完成: strategy={cls_name}", status='SUCCESS')
        logger.info("\n" + "=" * 60)
        logger.info("测试模式完成")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        db.log('test', f"失败: {e}", status='ERROR')
        raise


# ============================================================
# 子命令: backtest — vn.py 批量回测
# ============================================================
def cmd_backtest(args):
    """vn.py 批量回测 — 对匹配的品种逐一执行完整流水线

    支持两种模式:
      - 单品种: --symbol DCE.m2509 (精确指定一个品种)
      - 批量: --pattern 'DCE\\\\.m' 或省略 --symbol (扫描 data_dir 匹配全部)
    """
    cm = ConfigManager()
    db = Database(cm.get_data_config()['db_path'])
    _setup_db_logging(db, 'backtest', args.symbol or 'multi')

    try:
        bc = cm.get_backtest_config()
        strategy = load_strategy(args.strategy)
        _apply_strategy_config(strategy, cm)

        # 确定品种列表
        if args.symbol and not args.pattern:
            # 明确指定单品种，直接回测
            symbols = [(args.symbol, None)]
            mode = 'single'
        else:
            # 按 pattern 扫描 CSV 目录 (pattern=None 扫描全部)
            symbols = scan_csv_files(bc['data_dir'], args.pattern)
            if not symbols:
                logger.error("未找到匹配的品种数据")
                db.log('backtest', "未找到匹配的品种数据", symbol='multi', status='ERROR')
                return
            mode = 'batch'

        logger.info(f"{'单品种' if mode == 'single' else '批量'}回测: {len(symbols)} 个品种"
                     f" strategy={_get_strategy_class_name(strategy)}")

        all_results = []
        failed = []
        for sym, _ in symbols:
            # 每个品种独立构建 context 和 engine (避免状态污染)
            ctx = _build_context(strategy, sym, cm,
                                 capital=bc.get('initial_capital', 100000.0))
            engine = VnpyBacktestEngine(bc, context=ctx)
            try:
                result = engine.run_full_pipeline(
                    symbol=sym,
                    start_date=args.start or None,
                    end_date=args.end or None,
                )
                all_results.append(result)
                if not result.get('success'):
                    failed.append(sym)
            except Exception as e:
                logger.error(f"{sym} 回测异常: {e}", exc_info=True)
                all_results.append({'success': False, 'symbol': sym, 'error': str(e)})
                failed.append(sym)

        succeeded = [r for r in all_results if r.get('success')]
        logger.info(f"回测完成: {len(succeeded)}/{len(all_results)} 成功"
                     + (f", 失败: {failed}" if failed else ""))

        # 生成合并报告 (仅批量模式且至少一个成功)
        if mode == 'batch' and succeeded:
            merged = generate_merged_report(succeeded, bc.get('report', {}).get(
                'output_dir', '.quant_shared_data/reports'))
            print(format_merged_report(merged))

        if succeeded:
            db.log('backtest',
                   f"{'批量' if mode == 'batch' else ''}回测完成: "
                   f"{len(succeeded)}/{len(all_results)}",
                   symbol='multi' if mode == 'batch' else args.symbol,
                   status='SUCCESS')
        else:
            db.log('backtest', f"回测全部失败", symbol='multi' if mode == 'batch' else args.symbol,
                   status='ERROR')

    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        db.log('backtest', f"失败: {e}", symbol=args.symbol or 'multi', status='ERROR')
        raise


# ============================================================
# 子命令: tq-backtest — TqSdk 回测 (兼容旧版)
# ============================================================
def cmd_tq_backtest(args):
    """天勤SDK回测 — 使用 TQBacktestEngine 配合天勤实时K线数据进行单标的图形化回测

    绩效跟踪统一委托给 Strategy.on_bar + on_fill，避免与 strategy.performance 重复计算。
    """
    from tqsdk import TqApi, TqAuth, TqBacktest, TargetPosTask
    from tqsdk.exceptions import BacktestFinished

    cm = ConfigManager()
    db = Database(cm.get_data_config()['db_path'])
    _setup_db_logging(db, 'backtest', args.symbol)

    api = None
    try:
        tc = cm.get_trading_config()
        account = cm.get_account_info()
        strategy_core = load_strategy(args.strategy)
        _apply_strategy_config(strategy_core, cm)
        strategy_cls = _get_strategy_class_name(strategy_core)

        context = _build_context(strategy_core, args.symbol, cm, capital=args.capital)
        bridge = TqsdkStrategyBridge(context=context)

        logger.info(f"回测: {args.symbol} {args.start}~{args.end} 资金={args.capital} "
                    f"strategy={strategy_cls} GUI={args.gui}")
        db.log('backtest',
               f"开始: {args.symbol} {args.start}~{args.end} 资金={args.capital} "
               f"strategy={strategy_cls}",
               symbol=args.symbol, status='INFO')

        auth = TqAuth(account['api_key'], account['api_secret']) if account.get('api_key') else None
        api = TqApi(
            backtest=TqBacktest(start_dt=datetime.strptime(args.start, '%Y-%m-%d'),
                                end_dt=datetime.strptime(args.end, '%Y-%m-%d')),
            auth=auth, web_gui=args.gui)
        klines = api.get_kline_serial(args.symbol, duration_seconds=tc['kline_period'] * 60)

        bridge.initialize(api)
        target_pos = TargetPosTask(api, args.symbol)

        prev_kline_len = len(klines)
        while True:
            api.wait_update()
            if api.is_changing(klines):
                current_len = len(klines)
                for i in range(prev_kline_len, current_len):
                    signal = bridge.on_bar(klines, idx=i)

                    pos = strategy_core.position
                    if signal.action == 'buy' and pos.direction != 'long':
                        target_pos.set_target_volume(signal.volume)
                        bridge.notify_fill(signal, float(klines.close.iloc[i]))
                    elif signal.action == 'sell' and pos.direction == 'long':
                        target_pos.set_target_volume(0)
                        bridge.notify_fill(signal, float(klines.close.iloc[i]))
                prev_kline_len = current_len

    except BacktestFinished:
        p = strategy_core.performance
        report = (
            f"{'=' * 60}\n"
            f"回测报告\n"
            f"{'=' * 60}\n"
            f"策略: {strategy_cls}\n"
            f"品种: {args.symbol}\n"
            f"区间: {args.start} ~ {args.end}\n"
            f"初始资金: {args.capital:,.2f}\n\n"
            f"交易统计:\n"
            f"  总交易次数: {p.total_trades}\n"
            f"  盈利交易: {p.winning_trades}\n"
            f"  亏损交易: {p.losing_trades}\n"
            f"  胜率: {p.win_rate:.2%}\n"
            f"  总盈亏: {p.total_profit:,.2f}\n"
            f"{'=' * 60}"
        )
        print(report)
        db.log('backtest', f"完成:\n{report}", symbol=args.symbol, status='SUCCESS')

        fills = getattr(strategy_core, 'fills', None)
        if fills:
            logger.info("\n交易记录:")
            for f in fills:
                ts = f.timestamp[:10] if f.timestamp else "N/A"
                tag = "买入" if f.action == 'buy' else "卖出"
                logger.info(f"  {ts} {tag} {f.symbol} @ {f.price:.2f} x {f.volume}  原因: {f.reason}")
        if args.gui:
            logger.info("\n图形界面已启动，关闭浏览器或Ctrl+C退出...")
            try:
                while True:
                    api.wait_update()
            except BacktestFinished:
                pass
    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        db.log('backtest', f"失败: {e}", symbol=args.symbol, status='ERROR')
        raise
    finally:
        if api:
            api.close()


# ============================================================
# 子命令: live — 实盘/模拟交易
# ============================================================
def cmd_live(args):
    cm = ConfigManager(args.config)
    db = Database(cm.get_data_config()['db_path'])
    _setup_db_logging(db, 'live', args.symbol)

    try:
        cm.validate_config()
        account = cm.get_account_info()
        if not account:
            logger.error("请先在 config/conf.local.yaml 中配置天勤账号信息")
            db.log('live', "配置缺失", symbol=args.symbol, status='ERROR')
            sys.exit(1)

        from tqsdk import TqAuth
        auth = TqAuth(account['api_key'], account['api_secret'])
        strategy = load_strategy(args.strategy)
        _apply_strategy_config(strategy, cm)
        strategy_cls = _get_strategy_class_name(strategy)

        context = _build_context(strategy, args.symbol, cm)
        bridge = TqsdkStrategyBridge(context=context)

        logger.info(f"实盘交易: {args.symbol} strategy={strategy_cls} GUI={args.gui}")
        db.log('live', f"开始: {args.symbol} strategy={strategy_cls}",
               symbol=args.symbol, status='INFO')

        (bridge.run_with_gui if args.gui else bridge.run)(symbol=args.symbol, auth=auth)

        db.log('live', f"结束: {args.symbol}", symbol=args.symbol, status='SUCCESS')
    except Exception as e:
        logger.error(f"实盘交易失败: {e}", exc_info=True)
        db.log('live', f"失败: {e}", symbol=args.symbol, status='ERROR')
        raise


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='天勤量化均线交叉策略交易系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例: python main.py backtest --strategy ma --symbol DCE.m2509")
    sub = parser.add_subparsers(dest='command', title='子命令', required=True)

    # ---- export ----
    p = sub.add_parser('export', help='导出Qlib格式CSV数据（含去重合并）',
                       description='从天勤获取K线数据，导出为Qlib标准CSV格式')
    p.add_argument('--symbol', required=True, help='品种代码，如 DCE.m2509')
    p.add_argument('--start', required=True, help='开始日期 YYYY-MM-DD')
    p.add_argument('--end', required=True, help='结束日期 YYYY-MM-DD')
    p.add_argument('--output', default=None, help='自定义输出路径（可选）')
    p.add_argument('--force', action='store_true', help='强制覆盖已有CSV和元数据')

    # ---- test ----
    p = sub.add_parser('test', help='本地策略逻辑测试（不联网）')
    p.add_argument('--strategy', default=None,
                   help='策略名称 (e.g. ma/ma_strategy/ma_strategy.py)，默认 ma')

    # ---- backtest ----
    p = sub.add_parser('backtest', help='vn.py批量回测',
                       description='逐品种执行完整回测流水线: 数据加载→全量回测→报告\n'
                                   '批量模式: python main.py backtest --pattern "DCE\\\\.m" 或省略 --symbol')
    p.add_argument('--symbol', default=None, help='品种代码 (单品种模式)')
    p.add_argument('--pattern', default=None, help='品种代码正则表达式 (批量模式, e.g. "DCE\\\\.m")')
    p.add_argument('--start', default=None, help='开始日期 YYYY-MM-DD (可选)')
    p.add_argument('--end', default=None, help='结束日期 YYYY-MM-DD (可选)')
    p.add_argument('--strategy', default=None,
                   help='策略名称 (e.g. ma/ma_strategy/ma_strategy.py)，默认 ma')

    # ---- tq-backtest ----
    p = sub.add_parser('tq-backtest', help='TqSdk历史数据回测 (旧版兼容)')
    p.add_argument('--symbol', default='DCE.m2109', help='品种代码')
    p.add_argument('--start', default='2024-01-01', help='开始日期')
    p.add_argument('--end', default='2024-12-31', help='结束日期')
    p.add_argument('--capital', type=float, default=100000.0, help='初始资金')
    p.add_argument('--gui', action='store_true', help='启用图形界面')
    p.add_argument('--strategy', default=None,
                   help='策略名称 (e.g. ma/ma_strategy/ma_strategy.py)，默认 ma')

    # ---- live ----
    p = sub.add_parser('live', help='实盘/模拟交易')
    p.add_argument('--symbol', default='DCE.m2109', help='品种代码')
    p.add_argument('--gui', action='store_true', help='启用图形界面')
    p.add_argument('--config', default=None, help='配置文件路径')
    p.add_argument('--strategy', default=None,
                   help='策略名称 (e.g. ma/ma_strategy/ma_strategy.py)，默认 ma')

    args = parser.parse_args()

    try:
        {'export': cmd_export, 'test': cmd_test,
         'backtest': cmd_backtest, 'tq-backtest': cmd_tq_backtest,
         'live': cmd_live}[args.command](args)
    except KeyboardInterrupt:
        logger.info("\n用户中断程序")
    except Exception as e:
        logger.error(f"程序执行错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()