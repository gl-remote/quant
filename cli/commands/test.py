# -*- coding: utf-8 -*-
"""
策略测试命令模块

提供本地策略逻辑测试功能，无需联网即可验证策略基本行为。

功能特点:
    - 模拟 K 线数据进行策略测试
    - 支持金叉买入、止损卖出等信号测试
    - 输出交易记录和绩效统计
"""

import argparse
import logging

from config import ConfigManager
from data import DataManager
from strategies.core import Bar, Fill, load_strategy, apply_strategy_config, get_strategy_class_name
from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    LOG_STATUS_INFO,
    LOG_STATUS_SUCCESS,
    LOG_STATUS_ERROR,
    DEFAULT_SMA_SHORT,
    DEFAULT_SMA_LONG,
    DEFAULT_STOP_LOSS_RATIO,
    DEFAULT_TAKE_PROFIT_RATIO,
)

logger = logging.getLogger(__name__)


def cmd_test(args: argparse.Namespace):
    """执行策略测试命令

    在本地模拟环境中测试策略逻辑，验证信号生成和交易处理流程。

    Args:
        args: argparse.Namespace 对象，包含:
            strategy: 策略名称（必填）
    """
    cm = ConfigManager()
    dm = DataManager(cm)

    strategy = load_strategy(args.strategy)
    apply_strategy_config(strategy, cm)
    cls_name = get_strategy_class_name(strategy)

    logger.info("=" * 60)
    logger.info(f"测试模式 - 策略: {cls_name}")
    logger.info("=" * 60)
    dm.store.log('test', f"开始: strategy={cls_name}", status=LOG_STATUS_INFO)

    try:
        tc = cm.get_trading_config()
        logger.info(
            f"策略参数: SMA({tc.get('sma_short', DEFAULT_SMA_SHORT)},"
            f"{tc.get('sma_long', DEFAULT_SMA_LONG)}) "
            f"止损={tc.get('stop_loss_ratio', DEFAULT_STOP_LOSS_RATIO):.0%} "
            f"止盈={tc.get('take_profit_ratio', DEFAULT_TAKE_PROFIT_RATIO):.0%}"
        )

        bar1 = Bar(symbol="TEST", datetime="2026-01-01",
                   open=10, high=15, low=10, close=15, volume=1000)
        signal1 = strategy.on_bar(bar1)
        logger.info(
            f"信号1: action={signal1.action} reason={signal1.reason} "
            f"volume={signal1.volume}"
        )

        if signal1.action == TRADE_ACTION_BUY:
            strategy.on_fill(Fill(
                timestamp=bar1.datetime, symbol=bar1.symbol,
                action=TRADE_ACTION_BUY, price=bar1.close, volume=signal1.volume,
                reason=signal1.reason))

            bar2 = Bar(symbol="TEST", datetime="2026-01-02",
                       open=15, high=16, low=13, close=13.5, volume=500)
            signal2 = strategy.on_bar(bar2)
            logger.info(f"信号2: action={signal2.action} reason={signal2.reason}")

            if signal2.action == TRADE_ACTION_SELL:
                strategy.on_fill(Fill(
                    timestamp=bar2.datetime, symbol=bar2.symbol,
                    action=TRADE_ACTION_SELL, price=bar2.close, volume=signal1.volume,
                    reason=signal2.reason))

        fills = strategy.fills
        sells = [f for f in fills if f.action == TRADE_ACTION_SELL]
        logger.info(f"绩效: 交易{sells.__len__()}次")
        dm.store.log('test', f"完成: strategy={cls_name}", status=LOG_STATUS_SUCCESS)
        logger.info("\n" + "=" * 60)
        logger.info("测试模式完成")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        dm.store.log('test', f"失败: {e}", status=LOG_STATUS_ERROR)
        raise
