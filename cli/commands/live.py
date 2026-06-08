"""
实盘交易命令模块

职责（参见 cli/tqsdk-test-plan.md §7）:
  加载策略 → 创建 State/Bridge → 调用 bridge.run()（自动触发 TargetPosTask 下单）

安全说明:
  live 命令会通过 TargetPosTask 下单。模拟还是实盘取决于天勤账号是否绑定期货公司。
  未绑定 = 模拟盘（虚拟资金），已绑定 = 实盘（真金白银，慎用！）。

使用方式:
  python main.py live --strategy ma --symbol SHFE.rb2509
  python main.py live --strategy ma --symbol SHFE.rb2509 --gui
"""

import argparse
import sys
from datetime import datetime

from loguru import logger

from common.constants import (
    LOG_STATUS_ERROR,
    LOG_STATUS_INFO,
    LOG_STATUS_SUCCESS,
)
from common.tqsdk_imports import tqsdk
from config import ConfigManager
from data import DataManager
from data.models import get_live_session_model, get_live_trade_model
from strategies import TqsdkStrategyBridge
from strategies.ma_strategy import MACrossParams
from strategies.utils import (
    apply_strategy_config,
    get_strategy_class_name,
    load_strategy,
)


def cmd_live(args: argparse.Namespace):
    """执行实盘/模拟交易命令

    使用天勤 SDK 连接实时数据运行策略并通过 TargetPosTask 下单。

    已修复: 旧版缺少 state 参数导致 Bridge 无法正确初始化。
            现在与 test.py 保持一致的 State 创建逻辑。

    Args:
        args: argparse.Namespace 对象，包含:
            symbol: 合约代码
            gui: 是否启用图形界面
            config: 配置文件路径（可选）
            strategy: 策略名称（必填）
    """
    cm = ConfigManager(args.config)
    dm = DataManager(cm)

    try:
        cm.validate_config()
        account = cm.get_account_info()
        if account is None:
            logger.error("请先在 config/conf.local.toml 中配置天勤账号信息")
            dm.store.log("live", "配置缺失", symbol=args.symbol, status=LOG_STATUS_ERROR)
            sys.exit(1)

        if not tqsdk.ensure():
            logger.error("tqsdk 未安装，无法启动实盘模式")
            sys.exit(1)

        auth = tqsdk.TqAuth(account.api_key, account.api_secret)
        cm.get_trading_config(args.strategy)
        cm.get_backtest_config()
        strategy = load_strategy(args.strategy)
        strategy_cls = get_strategy_class_name(strategy)
        tc = cm.get_trading_config()
        bc = cm.get_backtest_config()

        # 创建策略配置 dataclass 并应用 TOML 参数
        strategy_config = MACrossParams()
        apply_strategy_config(strategy_config, cm)

        # 创建 State（修复旧 bug：原来缺 state 参数）
        from strategies.core.state import State

        state = State(
            symbol=args.symbol,
            period=f"{tc.kline_period}m",
            strategy_config=strategy_config,
            capital=bc.initial_capital,
            contract_size=bc.contract_size,
            margin=0.1,  # 保证金比例（BacktestConfig 无此字段，取默认值）
        )

        # 修复: 旧代码 TqsdkStrategyBridge(strategy=strategy, symbol=args.symbol) 缺 state
        bridge = TqsdkStrategyBridge(strategy=strategy, state=state)
        logger.info(f"实盘交易: {args.symbol} strategy={strategy_cls} GUI={args.gui}")
        dm.store.log("live", f"开始: {args.symbol} strategy={strategy_cls}", symbol=args.symbol, status=LOG_STATUS_INFO)

        # 数据库持久化（live 表前缀）
        live_session_model = get_live_session_model("live_sessions")
        live_trade_model = get_live_trade_model("live_trades")  # noqa: F841 — 未来 fill 回调时使用
        session = live_session_model.create(
            symbol=args.symbol,
            strategy="ma",
            mode="sim",  # 由账号绑定状态决定实际是 sim 还是 live
            status="running",
            started_at=datetime.now(),
            initial_capital=state.capital,
        )

        try:
            # on_signal=None → live 模式，bridge.run() 内部自动创建 TargetPosTask 下单
            bridge.run(symbol=args.symbol, auth=auth, web_gui=getattr(args, "gui", False))
        finally:
            session.update(status="stopped", ended_at=datetime.now())

        dm.store.log("live", f"结束: {args.symbol}", symbol=args.symbol, status=LOG_STATUS_SUCCESS)
    except Exception as e:
        logger.exception(f"实盘交易失败: {e}")
        dm.store.log("live", f"失败: {e}", symbol=args.symbol, status=LOG_STATUS_ERROR)
        raise
