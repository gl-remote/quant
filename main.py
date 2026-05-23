#!/usr/bin/env python3
"""天勤量化交易系统 - 均线交叉策略回测与实盘交易入口"""

import sys
import argparse
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from config import ConfigManager
from strategies import MovingAverageStrategy
from backtest import BacktestEngine, TradeRecord

logger = logging.getLogger(__name__)


def _apply_trading_config(strategy, trading_config, symbol):
    """将交易配置应用到策略对象"""
    cfg = strategy.config
    cfg.symbol = symbol
    cfg.sma_short_period = trading_config['sma_short']
    cfg.sma_long_period = trading_config['sma_long']
    cfg.stop_loss_ratio = trading_config['stop_loss_ratio']
    cfg.take_profit_ratio = trading_config['take_profit_ratio']
    cfg.position_ratio = trading_config['position_ratio']


def run_live_trading(symbol: str, config_file: str = None, show_gui: bool = False):
    try:
        cm = ConfigManager(config_file)
        cm.validate_config()
        account = cm.get_account_info()
        if not account:
            logger.error("请先在 conf.local.yaml 中配置天勤账号信息"); return

        from tqsdk import TqAuth
        auth = TqAuth(account['api_key'], account['api_secret'])

        strategy = MovingAverageStrategy()
        _apply_trading_config(strategy, cm.get_trading_config(), symbol)
        (strategy.run_with_gui if show_gui else strategy.run)(symbol=symbol, auth=auth)
    except Exception as e:
        logger.error(f"实盘交易启动失败: {e}")
        import traceback; traceback.print_exc()
        raise


def run_backtest(symbol: str, start_date: str, end_date: str,
                 initial_capital: float = 100000.0, show_gui: bool = False):
    from tqsdk import TqApi, TqAuth, TqBacktest, TargetPosTask
    from tqsdk.exceptions import BacktestFinished

    api = None
    try:
        cm = ConfigManager()
        tc = cm.get_trading_config()
        account = cm.get_account_info()

        kline_duration = tc['kline_period'] * 60
        logger.info(f"回测: {symbol} {start_date}~{end_date} 资金={initial_capital} "
                    f"K线={tc['kline_period']}min SMA=({tc['sma_short']},{tc['sma_long']}) GUI={show_gui}")

        auth = TqAuth(account['api_key'], account['api_secret']) if account.get('api_key') else None
        api = TqApi(backtest=TqBacktest(start_dt=datetime.strptime(start_date, '%Y-%m-%d'),
                                         end_dt=datetime.strptime(end_date, '%Y-%m-%d')),
                    auth=auth, web_gui=show_gui)
        klines = api.get_kline_serial(symbol, duration_seconds=kline_duration)

        strategy = MovingAverageStrategy()
        _apply_trading_config(strategy, tc, symbol)
        engine = BacktestEngine(initial_capital=initial_capital)
        target_pos = TargetPosTask(api, symbol)

        while True:
            api.wait_update()
            if api.is_changing(klines):
                bar = {
                    'datetime': datetime.fromtimestamp(klines['datetime'].iloc[-1] / 10**9),
                    'close': float(klines['close'].iloc[-1]),
                    'open': float(klines['open'].iloc[-1]),
                    'high': float(klines['high'].iloc[-1]),
                    'low': float(klines['low'].iloc[-1]),
                    'volume': int(klines['volume'].iloc[-1])
                }
                strategy.on_bar(klines)

                if strategy.signal == 'buy' and engine.current_position == 0:
                    qty = int((engine.current_capital * strategy.config.position_ratio) / bar['close'])
                    if qty > 0:
                        engine.add_trade(TradeRecord(
                            timestamp=bar['datetime'], symbol=symbol, direction='buy',
                            price=bar['close'], quantity=qty, reason="金叉买入"))
                        target_pos.set_target_volume(qty)
                        strategy.signal = None
                elif strategy.signal == 'sell' and engine.current_position > 0:
                    profit = (bar['close'] - engine.entry_price) * engine.current_position
                    engine.add_trade(TradeRecord(
                        timestamp=bar['datetime'], symbol=symbol, direction='sell',
                        price=bar['close'], quantity=engine.current_position,
                        profit=profit, reason=strategy.signal_reason))
                    target_pos.set_target_volume(0)
                    strategy.signal = None

    except BacktestFinished:
        print(engine.generate_report())
        if engine.trade_history:
            logger.info("\n交易记录:")
            for t in engine.trade_history:
                ts = t.timestamp.strftime('%Y-%m-%d')
                if t.direction == 'buy':
                    logger.info(f"  {ts} 买入 {t.symbol} @ {t.price:.2f} x {t.quantity}")
                else:
                    logger.info(f"  {ts} 卖出 {t.symbol} @ {t.price:.2f} x {t.quantity} 盈亏: {t.profit:.2f}")
        if show_gui:
            logger.info("\n图形界面已启动，关闭浏览器或Ctrl+C退出...")
            try:
                while True: api.wait_update()
            except BacktestFinished:
                pass
    except Exception as e:
        logger.error(f"回测执行失败: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        if api: api.close()


def run_test_mode():
    logger.info("=" * 60)
    logger.info("测试模式 - 策略逻辑验证")
    logger.info("=" * 60)
    try:
        cm = ConfigManager()
        tc = cm.get_trading_config()
        strategy = MovingAverageStrategy()
        _apply_trading_config(strategy, tc, 'DCE.m2109')
        logger.info(f"策略参数: SMA({tc['sma_short']},{tc['sma_long']}) "
                    f"止损={tc['stop_loss_ratio']:.0%} 止盈={tc['take_profit_ratio']:.0%} 仓位={tc['position_ratio']:.0%}")

        sma_short = strategy.calculate_sma([10, 11, 12, 13, 15], 5)
        sma_long = strategy.calculate_sma([12, 12, 12, 12, 12], 5)
        logger.info(f"SMA5={sma_short:.2f} SMA20={sma_long:.2f}")

        crossover = strategy.check_crossover(sma_short, sma_long, 11.0, 12.0)
        if crossover == 'golden_cross':
            strategy.execute_buy('TEST.SYMBOL', 14.0, 10, "测试金叉买入")
            logger.info(f"止损价={strategy.state.entry_price * (1 - tc['stop_loss_ratio']):.2f} "
                        f"止盈价={strategy.state.entry_price * (1 + tc['take_profit_ratio']):.2f}")
            strategy.state.current_position = 10
            strategy.execute_sell('TEST.SYMBOL',
                                  strategy.state.entry_price * (1 + tc['take_profit_ratio']),
                                  10, "测试止盈")
            logger.info(f"测试盈亏: {strategy.state.trade_records[-1].profit:.2f}")

        logger.info(f"绩效摘要: {strategy.get_performance_summary()}")
        logger.info("\n" + "=" * 60)
        logger.info("测试模式完成")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description='天勤量化均线交叉策略交易系统')
    parser.add_argument('--mode', choices=['live', 'backtest', 'test'], default='test')
    parser.add_argument('--symbol', default='DCE.m2109')
    parser.add_argument('--config', default=None)
    parser.add_argument('--start', default='2024-01-01')
    parser.add_argument('--end', default='2024-12-31')
    parser.add_argument('--capital', type=float, default=100000.0)
    parser.add_argument('--gui', action='store_true', default=False)

    args = parser.parse_args()
    try:
        if args.mode == 'live':
            run_live_trading(args.symbol, args.config, args.gui)
        elif args.mode == 'backtest':
            run_backtest(args.symbol, args.start, args.end, args.capital, args.gui)
        else:
            run_test_mode()
    except KeyboardInterrupt:
        logger.info("\n用户中断程序")
    except Exception as e:
        logger.error(f"程序执行错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()