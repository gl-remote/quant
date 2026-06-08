"""
策略测试命令模块（tqsdk 实时数据信号验证）

职责（参见 cli/tqsdk-test-plan.md §7）:
  连接天勤实时行情 → 驱动 MA 策略 → 打印信号 → 验证信号链路正确性

安全设计（参见 cli/tqsdk-test-plan.md §8 决策项2）:
  命令即安全边界 — 本模块代码路径中不包含 TargetPosTask，
  即使天勤账号已绑定期货公司，运行 test 也永远不会下单。

使用方式:
  python main.py test --strategy ma --symbol SHFE.rb2509
  python main.py test --strategy ma --symbol SHFE.rb2509 --gui
"""

import argparse
from datetime import datetime

from loguru import logger

from common.constants import (
    LOG_STATUS_INFO,
    LOG_STATUS_SUCCESS,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
)
from common.tqsdk_imports import tqsdk
from config import ConfigManager
from data import DataManager
from data.models import get_live_session_model, get_live_trade_model
from strategies import Signal, TqsdkStrategyBridge
from strategies.utils import apply_strategy_config, get_strategy_class_name, load_strategy


def _get_tq_auth(cm: ConfigManager):
    """从配置读取天勤认证信息，无配置则返回 None（使用 guest 模式）"""
    account = cm.get_account_info()
    if account and account.api_key and account.api_secret:
        return tqsdk.TqAuth(account.api_key, account.api_secret)
    return None


def cmd_test(args: argparse.Namespace):
    """连接天勤实时数据运行策略，打印信号（不下单）

    Args:
        args: argparse.Namespace，包含:
            strategy: 策略名称（必填）
            symbol: 合约代码（必填）
            gui: 是否启用浏览器可视化（可选）
    """
    cm = ConfigManager()
    dm = DataManager(cm)

    strategy = load_strategy(args.strategy)
    apply_strategy_config(strategy, cm)
    cls_name = get_strategy_class_name(strategy)
    tc = cm.get_trading_config()

    # 创建 State（与回测路径一致的参数来源）
    from strategies.core.state import State

    state = State(
        symbol=args.symbol,
        period=f"{tc.get('kline_period', 1)}m",
        strategy_config=strategy.config,
        capital=float(tc.get("initial_capital", 100000)),
        contract_size=int(tc.get("contract_size", 10)),
        margin=float(tc.get("margin_ratio", 0.1)),
    )

    bridge = TqsdkStrategyBridge(strategy=strategy, state=state)
    auth = _get_tq_auth(cm)

    # 数据库持久化（test 表前缀）
    test_session_model = get_live_session_model("test_sessions")
    test_trade_model = get_live_trade_model("test_trades")
    session = test_session_model.create(
        symbol=args.symbol,
        strategy="ma",
        mode="test",
        status="running",
        started_at=datetime.now(),
    )

    signal_count = 0
    buy_count = 0
    sell_count = 0

    def on_signal(signal: Signal, price: float) -> None:
        """信号回调 — 打印并持久化，不下单"""
        nonlocal signal_count, buy_count, sell_count
        signal_count += 1
        diag = " ".join(f"{k}={v:.4f}" for k, v in signal.diagnostics.items())
        direction = "long" if signal.action == TRADE_ACTION_BUY else "short"
        offset = "open" if signal.volume > 0 else "close"
        logger.info(
            f"[TEST] #{signal_count} {signal.action} "
            f"price={price:.2f} vol={signal.volume} "
            f"reason={signal.reason} | {diag}"
        )

        # 写入数据库
        test_trade_model.create(
            session=session.id,
            datetime=datetime.now(),
            symbol=args.symbol,
            direction=direction,
            offset=offset,
            price=price,
            quantity=signal.volume,
            reason=signal.reason,
        )
        if signal.action == TRADE_ACTION_BUY:
            buy_count += 1
        elif signal.action == TRADE_ACTION_SELL:
            sell_count += 1

    gui = getattr(args, "gui", False)
    logger.info(f"[TEST] 策略={cls_name} 标的={args.symbol} GUI={'开' if gui else '关'}")
    dm.store.log("test", f"开始: {args.symbol} strategy={cls_name}", symbol=args.symbol, status=LOG_STATUS_INFO)

    try:
        bridge.run(symbol=args.symbol, auth=auth, on_signal=on_signal, web_gui=gui)
    except KeyboardInterrupt:
        pass
    finally:
        session.update(
            status="stopped",
            ended_at=datetime.now(),
            total_signals=signal_count,
            buy_signals=buy_count,
            sell_signals=sell_count,
        )
        logger.info(f"[TEST] 完成: 信号={signal_count} 买入={buy_count} 卖出={sell_count}")
        dm.store.log("test", f"完成: signals={signal_count}", status=LOG_STATUS_SUCCESS)
