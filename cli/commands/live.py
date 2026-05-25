# -*- coding: utf-8 -*-
"""
实盘交易命令模块

提供基于天勤 SDK 的实盘/模拟交易功能。

功能特点:
    - 支持实盘和模拟交易
    - 支持图形界面监控
    - 完整的交易日志记录
"""

import sys
import logging

from config import ConfigManager
from data import Database, setup_db_logging
from strategies import TqsdkStrategyBridge
from strategies.core import (
    load_strategy,
    apply_strategy_config,
    get_strategy_class_name,
    TradingContext,
)
from common.constants import (
    LOG_STATUS_INFO,
    LOG_STATUS_SUCCESS,
    LOG_STATUS_ERROR,
)

logger = logging.getLogger(__name__)


def cmd_live(args):
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
    db = Database(cm.get_data_config()['db_path'])
    setup_db_logging(db, 'live', args.symbol)

    try:
        cm.validate_config()
        account = cm.get_account_info()
        if not account:
            logger.error("请先在 config/conf.local.yaml 中配置天勤账号信息")
            db.log('live', "配置缺失", symbol=args.symbol, status=LOG_STATUS_ERROR)
            sys.exit(1)

        from tqsdk import TqAuth
        auth = TqAuth(account['api_key'], account['api_secret'])
        strategy = load_strategy(args.strategy)
        apply_strategy_config(strategy, cm)
        strategy_cls = get_strategy_class_name(strategy)

        context = TradingContext.build(strategy, args.symbol, cm)
        bridge = TqsdkStrategyBridge(context=context)

        logger.info(f"实盘交易: {args.symbol} strategy={strategy_cls} GUI={args.gui}")
        db.log('live', f"开始: {args.symbol} strategy={strategy_cls}",
               symbol=args.symbol, status=LOG_STATUS_INFO)

        (bridge.run_with_gui if args.gui else bridge.run)(symbol=args.symbol, auth=auth)

        db.log('live', f"结束: {args.symbol}", symbol=args.symbol, status=LOG_STATUS_SUCCESS)
    except Exception as e:
        logger.error(f"实盘交易失败: {e}", exc_info=True)
        db.log('live', f"失败: {e}", symbol=args.symbol, status=LOG_STATUS_ERROR)
        raise