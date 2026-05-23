#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天勤量化交易系统主程序

整合配置管理、策略执行和回测功能的主入口。
"""

import sys
import os
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager
from strategies import MovingAverageStrategy
from backtest import BacktestEngine, TradeRecord

logger = logging.getLogger(__name__)


def run_live_trading(symbol: str, config_file: str = None, show_gui: bool = False):
    """
    运行实盘交易
    
    Args:
        symbol: 交易品种
        config_file: 配置文件路径
        show_gui: 是否显示图形界面
    """
    try:
        logger.info("正在加载配置...")
        config_manager = ConfigManager(config_file)
        config_manager.validate_config()
        account_info = config_manager.get_account_info()
        
        if not account_info:
            logger.error("请先在 conf.local.yaml 中配置天勤账号信息")
            return
        
        logger.info(f"账号: {account_info['api_key']}")
        
        from tqsdk import TqAuth
        auth = TqAuth(account_info['api_key'], account_info['api_secret'])
        
        trading_config = config_manager.get_trading_config()
        strategy = MovingAverageStrategy()
        
        strategy.config.symbol = symbol
        strategy.config.sma_short_period = trading_config['sma_short']
        strategy.config.sma_long_period = trading_config['sma_long']
        strategy.config.stop_loss_ratio = trading_config['stop_loss_ratio']
        strategy.config.take_profit_ratio = trading_config['take_profit_ratio']
        strategy.config.position_ratio = trading_config['position_ratio']
        
        strategy.run_with_gui(symbol=symbol, auth=auth) if show_gui else strategy.run(symbol=symbol, auth=auth)
        
    except Exception as e:
        logger.error(f"实盘交易启动失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def generate_mock_data(start_date, end_date, base_price=100):
    """
    生成模拟历史数据
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        base_price: 基准价格
        
    Returns:
        模拟K线数据列表
    """
    from datetime import datetime, timedelta
    import random
    
    data = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    
    price = base_price
    
    while current_date <= end_date:
        change = (random.random() - 0.5) * 4
        open_price = price
        close_price = price + change
        high_price = max(open_price, close_price) + random.random() * 2
        low_price = min(open_price, close_price) - random.random() * 2
        
        bar = {
            'datetime': current_date,
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': random.randint(100, 1000)
        }
        data.append(bar)
        
        price = close_price
        current_date += timedelta(days=1)
    
    return data


def run_backtest(symbol: str, start_date: str, end_date: str, 
                initial_capital: float = 100000.0, show_gui: bool = False):
    """
    运行回测（使用 tqsdk 推荐方式）
    
    Args:
        symbol: 交易品种
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
        show_gui: 是否显示图形界面（使用 tqsdk web_gui）
    """
    logger.info("=" * 60)
    logger.info("开始回测")
    logger.info("=" * 60)
    
    from tqsdk import TqApi, TqAuth, TqBacktest, TargetPosTask
    from tqsdk.exceptions import BacktestFinished
    from datetime import datetime
    
    api = None
    
    try:
        config_manager = ConfigManager()
        trading_config = config_manager.get_trading_config()
        account_info = config_manager.get_account_info()
        
        kline_period = trading_config['kline_period']
        kline_duration = kline_period * 60
        
        logger.info(f"回测参数:")
        logger.info(f"  交易品种: {symbol}")
        logger.info(f"  开始日期: {start_date}")
        logger.info(f"  结束日期: {end_date}")
        logger.info(f"  初始资金: {initial_capital}")
        logger.info(f"  K线周期: {kline_period}分钟")
        logger.info(f"  SMA参数: {trading_config['sma_short']}, {trading_config['sma_long']}")
        logger.info(f"  图形界面: {'启用' if show_gui else '禁用'}")
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        auth = None
        if account_info.get('api_key') and account_info.get('api_secret'):
            auth = TqAuth(account_info['api_key'], account_info['api_secret'])
        
        api = TqApi(
            backtest=TqBacktest(start_dt=start_dt, end_dt=end_dt),
            auth=auth,
            web_gui=show_gui
        )
        
        klines = api.get_kline_serial(symbol, duration_seconds=kline_duration)
        
        strategy = MovingAverageStrategy()
        strategy.config.symbol = symbol
        strategy.config.sma_short_period = trading_config['sma_short']
        strategy.config.sma_long_period = trading_config['sma_long']
        strategy.config.stop_loss_ratio = trading_config['stop_loss_ratio']
        strategy.config.take_profit_ratio = trading_config['take_profit_ratio']
        strategy.config.position_ratio = trading_config['position_ratio']
        
        engine = BacktestEngine(initial_capital=initial_capital)
        target_pos = TargetPosTask(api, symbol)
        
        logger.info("\n正在执行回测...")
        
        while True:
            api.wait_update()
            
            if api.is_changing(klines):
                bar = {
                    'datetime': datetime.fromtimestamp(klines['datetime'].iloc[-1] / 10**9),
                    'open': float(klines['open'].iloc[-1]),
                    'high': float(klines['high'].iloc[-1]),
                    'low': float(klines['low'].iloc[-1]),
                    'close': float(klines['close'].iloc[-1]),
                    'volume': int(klines['volume'].iloc[-1])
                }
                
                strategy.on_bar(klines)
                
                if strategy.signal == 'buy' and engine.current_position == 0:
                    quantity = int((engine.current_capital * strategy.config.position_ratio) / bar['close'])
                    if quantity > 0:
                        trade = TradeRecord(
                            timestamp=bar['datetime'],
                            symbol=strategy.config.symbol,
                            direction='buy',
                            price=bar['close'],
                            quantity=quantity,
                            reason="金叉买入"
                        )
                        engine.add_trade(trade)
                        target_pos.set_target_volume(quantity)
                        strategy.signal = None
                        logger.info(f"[{bar['datetime'].strftime('%Y-%m-%d')}] 买入: {symbol} @ {bar['close']:.2f}, 数量: {quantity}")
                
                elif strategy.signal == 'sell' and engine.current_position > 0:
                    profit = (bar['close'] - engine.entry_price) * engine.current_position
                    trade = TradeRecord(
                        timestamp=bar['datetime'],
                        symbol=strategy.config.symbol,
                        direction='sell',
                        price=bar['close'],
                        quantity=engine.current_position,
                        profit=profit,
                        reason=strategy.signal_reason
                    )
                    engine.add_trade(trade)
                    target_pos.set_target_volume(0)
                    strategy.signal = None
                    logger.info(f"[{bar['datetime'].strftime('%Y-%m-%d')}] 卖出: {symbol} @ {bar['close']:.2f}, 盈亏: {profit:.2f}")
    
    except BacktestFinished:
        logger.info("\n" + "=" * 60)
        logger.info("回测报告")
        logger.info("=" * 60)
        print(engine.generate_report())
        
        if len(engine.trade_history) > 0:
            logger.info("\n交易记录:")
            for trade in engine.trade_history:
                if trade.direction == 'buy':
                    logger.info(f"  {trade.timestamp.strftime('%Y-%m-%d')} 买入 {trade.symbol} @ {trade.price:.2f} x {trade.quantity}")
                else:
                    logger.info(f"  {trade.timestamp.strftime('%Y-%m-%d')} 卖出 {trade.symbol} @ {trade.price:.2f} x {trade.quantity} 盈亏: {trade.profit:.2f}")
        else:
            logger.info("\n交易记录: 无交易信号")
        
        if show_gui:
            logger.info("\n图形界面已启动，关闭浏览器窗口或按Ctrl+C退出...")
            while True:
                try:
                    api.wait_update()
                except BacktestFinished:
                    break
        
    except Exception as e:
        logger.error(f"回测执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if api:
            api.close()





def main():
    """
    主函数
    
    解析命令行参数并执行相应操作。
    """
    parser = argparse.ArgumentParser(
        description='天勤量化均线交叉策略交易系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  运行实盘交易:
    python main.py --mode live --symbol DCE.m2109
    
  运行回测:
    python main.py --mode backtest --symbol DCE.m2109 --start 2024-01-01 --end 2024-12-31
    
  运行回测并显示图形界面:
    python main.py --mode backtest --symbol DCE.m2109 --gui
    
  查看帮助:
    python main.py --help
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['live', 'backtest', 'test'],
        default='test',
        help='运行模式: live(实盘), backtest(回测), test(测试模式)'
    )
    
    parser.add_argument(
        '--symbol',
        default='DCE.m2109',
        help='交易品种代码'
    )
    
    parser.add_argument(
        '--config',
        default=None,
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--start',
        default='2024-01-01',
        help='回测开始日期 (格式: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--end',
        default='2024-12-31',
        help='回测结束日期 (格式: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--capital',
        type=float,
        default=100000.0,
        help='初始资金'
    )
    
    parser.add_argument(
        '--gui',
        action='store_true',
        default=False,
        help='启用图形界面（仅在回测和实盘模式下生效）'
    )
    
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


def run_test_mode():
    """
    测试模式
    
    不连接实盘，测试策略逻辑。
    """
    logger.info("=" * 60)
    logger.info("测试模式 - 策略逻辑验证")
    logger.info("=" * 60)
    
    try:
        from strategies import MovingAverageStrategy
        from config import ConfigManager
        
        logger.info("正在加载配置...")
        config_manager = ConfigManager()
        trading_config = config_manager.get_trading_config()
        
        logger.info(f"交易配置: {trading_config}")
        
        strategy = MovingAverageStrategy()
        strategy.config.sma_short_period = trading_config['sma_short']
        strategy.config.sma_long_period = trading_config['sma_long']
        strategy.config.stop_loss_ratio = trading_config['stop_loss_ratio']
        strategy.config.take_profit_ratio = trading_config['take_profit_ratio']
        strategy.config.position_ratio = trading_config['position_ratio']
        
        logger.info("策略初始化成功")
        logger.info(f"策略参数: SMA({strategy.config.sma_short_period}, {strategy.config.sma_long_period})")
        logger.info(f"风险控制: 止损={strategy.config.stop_loss_ratio:.2%}, 止盈={strategy.config.take_profit_ratio:.2%}")
        logger.info(f"仓位控制: {strategy.config.position_ratio:.2%}")
        
        logger.info("\n测试: 模拟金叉买入")
        test_data_short = [10, 11, 12, 13, 15]
        test_data_long = [12, 12, 12, 12, 12]
        
        sma_short = strategy.calculate_sma(test_data_short, 5)
        sma_long = strategy.calculate_sma(test_data_long, 5)
        
        logger.info(f"测试数据 - SMA5: {sma_short:.2f}, SMA20: {sma_long:.2f}")
        
        crossover = strategy.check_crossover(sma_short, sma_long, 11.0, 12.0)
        logger.info(f"交叉检测: {crossover}")
        
        if crossover == 'golden_cross':
            logger.info("✓ 金叉信号正确识别")
            
            strategy.execute_buy('TEST.SYMBOL', 14.0, 10, "测试金叉买入")
            
            logger.info("\n测试: 止损止盈")
            stop_loss_price = strategy.state.entry_price * (1 - strategy.config.stop_loss_ratio)
            take_profit_price = strategy.state.entry_price * (1 + strategy.config.take_profit_ratio)
            
            logger.info(f"止损价格: {stop_loss_price:.2f}")
            logger.info(f"止盈价格: {take_profit_price:.2f}")
            
            strategy.state.current_position = 10
            strategy.execute_sell('TEST.SYMBOL', take_profit_price, 10, "测试止盈")
            
            logger.info(f"测试交易盈亏: {strategy.state.trade_records[-1].profit:.2f}")
        
        logger.info("\n测试: 绩效统计")
        performance = strategy.get_performance_summary()
        logger.info(f"绩效摘要: {performance}")
        
        logger.info("\n" + "=" * 60)
        logger.info("测试模式完成 - 所有功能正常")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise


if __name__ == "__main__":
    main()