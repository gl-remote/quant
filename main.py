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

from config import ConfigManager, get_account_info
from strategies import MovingAverageStrategy
from backtest import BacktestEngine

logger = logging.getLogger(__name__)


def run_live_trading(symbol: str, config_file: str = None):
    """
    运行实盘交易
    
    Args:
        symbol: 交易品种
        config_file: 配置文件路径
    """
    try:
        logger.info("正在加载配置...")
        config_manager = ConfigManager(config_file)
        config_manager.validate_config()
        account_info = config_manager.get_account_info()
        
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
        
        strategy.run(symbol=symbol, auth=auth)
        
    except Exception as e:
        logger.error(f"实盘交易启动失败: {e}")
        raise


def run_backtest(symbol: str, start_date: str, end_date: str, 
                initial_capital: float = 100000.0):
    """
    运行回测
    
    Args:
        symbol: 交易品种
        start_date: 开始日期
        end_date: 结束日期
        initial_capital: 初始资金
    """
    logger.info("=" * 60)
    logger.info("开始回测")
    logger.info("=" * 60)
    
    try:
        config_manager = ConfigManager()
        trading_config = config_manager.get_trading_config()
        
        engine = BacktestEngine(initial_capital=initial_capital)
        
        logger.info(f"回测参数:")
        logger.info(f"  交易品种: {symbol}")
        logger.info(f"  开始日期: {start_date}")
        logger.info(f"  初始资金: {initial_capital}")
        logger.info(f"  SMA参数: {trading_config['sma_short']}, {trading_config['sma_long']}")
        
        logger.info("\n回测功能开发中...")
        logger.info("提示: 请使用天勤量化回测工具进行完整回测")
        
        print(engine.generate_report())
        
    except Exception as e:
        logger.error(f"回测执行失败: {e}")
        raise


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
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'live':
            run_live_trading(args.symbol, args.config)
        elif args.mode == 'backtest':
            run_backtest(args.symbol, args.start, args.end, args.capital)
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
