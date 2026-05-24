#!/usr/bin/env python3
"""天勤量化交易系统 - 均线交叉策略，支持数据导出、回测、实盘交易"""

import sys
import argparse
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
from strategies import TqsdkStrategyGateway
from strategies.core import Strategy, TradingContext
from backtest import BacktestEngine, TradeRecord, VnpyBacktestEngine
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

    spec = importlib.util.spec_from_file_location(name, strategy_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

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
    """将配置文件中的策略参数应用到策略实例的 config 上"""
    sc = cm.get_strategy_config(strategy.name)
    cfg = strategy.config
    for key, value in sc.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)


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

    if args.strategy:
        strategy = load_strategy(args.strategy)
        _apply_strategy_config(strategy, cm)
        logger.info("=" * 60)
        logger.info(f"测试模式 - 策略: {_get_strategy_class_name(strategy)}")
        logger.info("=" * 60)
        db.log('test', f"开始: strategy={_get_strategy_class_name(strategy)}", status='INFO')

        try:
            signal, reason = strategy.on_bar_signal(
                [10, 11, 12, 13, 15], 15.0)
            logger.info(f"信号测试: signal={signal} reason={reason}")

            strategy.on_enter(14.0, 10)
            profit = strategy.on_exit(16.0)
            logger.info(f"损益测试: 入场14.0 出场16.0 盈亏={profit:.2f}")

            perf = strategy.get_performance([])
            logger.info(f"绩效接口测试: {perf}")
            db.log('test', f"完成: strategy={_get_strategy_class_name(strategy)}", status='SUCCESS')
            logger.info("\n" + "=" * 60)
            logger.info("测试模式完成")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"测试失败: {e}")
            db.log('test', f"失败: {e}", status='ERROR')
            raise
    else:
        strategy = load_strategy(None)
        _apply_strategy_config(strategy, cm)
        logger.info("=" * 60)
        logger.info(f"测试模式 - 策略逻辑验证 ({_get_strategy_class_name(strategy)})")
        logger.info("=" * 60)
        db.log('test', f"开始: strategy={_get_strategy_class_name(strategy)}", status='INFO')

        try:
            tc = cm.get_trading_config()
            logger.info(f"策略参数: SMA({tc['sma_short']},{tc['sma_long']}) "
                        f"止损={tc['stop_loss_ratio']:.0%} 止盈={tc['take_profit_ratio']:.0%}")

            signal, reason = strategy.on_bar_signal([10, 11, 12, 13, 15], 15.0)
            logger.info(f"信号测试: signal={signal} reason={reason}")

            strategy.on_enter(14.0, 10)
            profit = strategy.on_exit(16.0)
            logger.info(f"损益测试: 入场14.0 出场16.0 盈亏={profit:.2f}")

            perf = strategy.get_performance([])
            logger.info(f"绩效接口测试: {perf}")
            db.log('test', f"完成: strategy={_get_strategy_class_name(strategy)}", status='SUCCESS')
            logger.info("\n" + "=" * 60)
            logger.info("测试模式完成")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"测试失败: {e}")
            db.log('test', f"失败: {e}", status='ERROR')
            raise


# ============================================================
# 子命令: backtest — vn.py 本地回测
# ============================================================
def cmd_backtest(args):
    """vn.py 框架回测 - 从本地CSV加载数据，划分训练/验证/测试集，独立回测并对比

    支持两种模式:
      - 单品种: --symbol DCE.m2509
      - 批量: --pattern 'DCE\\.m' 匹配多个品种，未指定则回测全部
    """
    cm = ConfigManager()
    db = Database(cm.get_data_config()['db_path'])
    _setup_db_logging(db, 'backtest', args.symbol or 'multi')

    try:
        bc = cm.get_backtest_config()
        strategy = load_strategy(args.strategy)
        _apply_strategy_config(strategy, cm)

        context = _build_context(strategy, args.symbol or "", cm,
                                 capital=bc.get('initial_capital', 100000.0))
        engine = VnpyBacktestEngine(bc, context=context)

        if args.pattern is not None or args.symbol is None or args.symbol == 'DCE.m2509':
            pattern = args.pattern
            logger.info(f"多品种回测模式: pattern={pattern or '全部'}, parallel={args.parallel} "
                        f"strategy={_get_strategy_class_name(strategy)}")
            result = engine.run_multi_backtest(
                pattern=pattern,
                start_date=args.start or None,
                end_date=args.end or None,
                max_workers=args.parallel or 1,
            )
            if result.get('success'):
                db.log('backtest',
                       f"批量回测完成: {result.get('succeeded', 0)}/{result.get('total', 0)}",
                       symbol='multi', status='SUCCESS')
            else:
                db.log('backtest', f"批量回测失败: {result.get('error', '')}",
                       symbol='multi', status='ERROR')
        else:
            logger.info(f"vn.py 回测: {args.symbol} 资金={bc['initial_capital']} "
                         f"费率={bc['commission_rate']:.4%} "
                         f"strategy={_get_strategy_class_name(strategy)}")
            result = engine.run_full_pipeline(
                symbol=args.symbol,
                start_date=args.start or None,
                end_date=args.end or None,
            )
            if result.get('success'):
                db.log('backtest', f"完成: {args.symbol} 三阶段回测",
                       symbol=args.symbol, status='SUCCESS')
            else:
                db.log('backtest', f"失败: {result.get('error', '')}",
                       symbol=args.symbol, status='ERROR')

    except Exception as e:
        logger.error(f"回测执行失败: {e}", exc_info=True)
        db.log('backtest', f"失败: {e}", symbol=args.symbol or 'multi', status='ERROR')
        raise


# ============================================================
# 子命令: tq-backtest — TqSdk 回测 (兼容旧版)
# ============================================================
def cmd_tq_backtest(args):
    """天勤SDK回测 (旧版兼容) - 使用天勤实时K线数据进行回测"""
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
        gateway = TqsdkStrategyGateway(context=context)

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

        gateway.initialize(api)

        engine = BacktestEngine(initial_capital=args.capital)
        target_pos = TargetPosTask(api, args.symbol)

        while True:
            api.wait_update()
            if api.is_changing(klines):
                bar = {
                    'datetime': datetime.fromtimestamp(klines['datetime'].iloc[-1] / 10 ** 9),
                    'close': float(klines['close'].iloc[-1]),
                    'open': float(klines['open'].iloc[-1]),
                    'high': float(klines['high'].iloc[-1]),
                    'low': float(klines['low'].iloc[-1]),
                    'volume': int(klines['volume'].iloc[-1]),
                }
                gateway.on_bar(klines)

                if gateway.signal == 'buy' and engine.current_position == 0:
                    qty = int((engine.current_capital * gateway.config.position_ratio) / bar['close'])
                    if qty > 0:
                        engine.add_trade(TradeRecord(
                            timestamp=bar['datetime'], symbol=args.symbol, direction='buy',
                            price=bar['close'], quantity=qty, reason="金叉买入"))
                        target_pos.set_target_volume(qty)
                        gateway.signal = None
                elif gateway.signal == 'sell' and engine.current_position > 0:
                    profit = (bar['close'] - engine.entry_price) * engine.current_position
                    engine.add_trade(TradeRecord(
                        timestamp=bar['datetime'], symbol=args.symbol, direction='sell',
                        price=bar['close'], quantity=engine.current_position,
                        profit=profit, reason=gateway.signal_reason))
                    target_pos.set_target_volume(0)
                    gateway.signal = None

    except BacktestFinished:
        report = engine.generate_report()
        print(report)
        db.log('backtest', f"完成:\n{report}", symbol=args.symbol, status='SUCCESS')
        if engine.trade_history:
            logger.info("\n交易记录:")
            for t in engine.trade_history:
                ts = t.timestamp.strftime('%Y-%m-%d')
                tag = "买入" if t.direction == 'buy' else "卖出"
                extra = f" 盈亏: {t.profit:.2f}" if t.direction == 'sell' else ""
                logger.info(f"  {ts} {tag} {t.symbol} @ {t.price:.2f} x {t.quantity}{extra}")
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
        gateway = TqsdkStrategyGateway(context=context)

        logger.info(f"实盘交易: {args.symbol} strategy={strategy_cls} GUI={args.gui}")
        db.log('live', f"开始: {args.symbol} strategy={strategy_cls}",
               symbol=args.symbol, status='INFO')

        (gateway.run_with_gui if args.gui else gateway.run)(symbol=args.symbol, auth=auth)

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
    p = sub.add_parser('backtest', help='vn.py本地历史数据回测 (训练/验证/测试三阶段)',
                       description='从本地CSV加载数据，划分训练/验证/测试集，独立回测并对比\n'
                                   '批量模式: python main.py backtest --pattern "DCE\\\\.m" 或省略 --symbol')
    p.add_argument('--symbol', default=None, help='品种代码 (单品种模式)')
    p.add_argument('--pattern', default=None, help='品种代码正则表达式 (批量模式, e.g. "DCE\\\\.m")')
    p.add_argument('--parallel', type=int, default=1, help='并行线程数 (批量模式, 默认=1顺序)')
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