# -*- coding: utf-8 -*-
"""
实盘交易命令模块

提供基于天勤 SDK 的实盘/模拟交易功能。

功能特点:
    - 支持实盘和模拟交易
    - 支持图形界面监控
    - 完整的交易日志记录
"""

import argparse
import sys
import logging

from config import ConfigManager
from data import DataManager
from strategies import TqsdkStrategyBridge
from strategies.utils import (
    load_strategy,
    get_strategy_class_name,
)
from common.constants import (
    LOG_STATUS_INFO,
    LOG_STATUS_SUCCESS,
    LOG_STATUS_ERROR,
)

logger = logging.getLogger(__name__)


def cmd_live(args: argparse.Namespace):
    """执行实盘/模拟交易命令

    使用天勤 SDK 连接实盘或模拟账户进行交易。

    Args:
        args: argparse.Namespace 对象，包含:
            symbol: 品种代码
            gui: 是否启用图形界面
            config: 配置文件路径（可选）
            strategy: 策略名称（可选）
    """
    cm = ConfigManager(args.config)
    dm = DataManager(cm)

    try:
        cm.validate_config()
        account = cm.get_account_info()
        if account is None:
            logger.error("请先在 config/conf.local.toml 中配置天勤账号信息")
            dm.store.log('live', "配置缺失", symbol=args.symbol, status=LOG_STATUS_ERROR)
            sys.exit(1)

        from tqsdk import TqAuth
        auth = TqAuth(account.api_key, account.api_secret)
        sc = cm.get_trading_config(args.strategy)
        strategy_params = sc.model_dump(exclude={"name", "enabled"})
        bc = cm.get_backtest_config()
        strategy = load_strategy(
            args.strategy,
            strategy_params=strategy_params,
            capital=bc.initial_capital,
            contract_size=bc.contract_size,
        )
        strategy_cls = get_strategy_class_name(strategy)

        bridge = TqsdkStrategyBridge(strategy=strategy, symbol=args.symbol)\

        logger.info(f"实盘交易: {args.symbol} strategy={strategy_cls} GUI={args.gui}")
        dm.store.log('live', f"开始: {args.symbol} strategy={strategy_cls}",
                     symbol=args.symbol, status=LOG_STATUS_INFO)

        (bridge.run_with_gui if args.gui else bridge.run)(symbol=args.symbol, auth=auth)

        dm.store.log('live', f"结束: {args.symbol}", symbol=args.symbol, status=LOG_STATUS_SUCCESS)
    except Exception as e:
        logger.error(f"实盘交易失败: {e}", exc_info=True)
        dm.store.log('live', f"失败: {e}", symbol=args.symbol, status=LOG_STATUS_ERROR)
        raise
