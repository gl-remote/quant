"""tqsdk 实时行情命令模块。

test 与 live 两条命令共用同一套代码，差异仅在 3 个参数：
  - account_type       test 强制 tqsim（本地模拟，与账号状态无关）
                       live 读配置的 account_type
  - require_account    test 允许 guest 匿名行情；live 必须有账号配置
  - trade              test 只回调打印信号；live 走 TargetPosTask 下单

代码结构：
  build_account()  从配置挑选 TqSim / TqKq / TqAccount 账户对象
  run_bridge()     统一流程：读配置 → 加载策略 → 建 bridge → 运行 → 持久化
  cmd_test()       薄调用：run_bridge(mode="test", account_type="tqsim", trade=False)
  cmd_live()       薄调用：run_bridge(mode="live", account_type=None, trade=True)
"""

import argparse
from datetime import datetime
from typing import Any

from loguru import logger

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL
from common.tqsdk_imports import tqsdk
from config import ConfigManager
from data import DataManager
from data.models import database, get_live_session_model, get_live_trade_model
from strategies import Signal, TqsdkStrategyBridge
from strategies.ma_strategy import MACrossParams
from strategies.utils import apply_strategy_config, get_strategy_class_name, load_strategy

# 合法的账户类型
VALID_ACCOUNT_TYPES = ("tqsim", "tqkq", "tqaccount")


def register_test(subparsers: Any) -> None:
    """注册 test 子命令的 argparse 选项

    `subparsers` 是 `parser.add_subparsers()` 返回的对象（`argparse._SubParsersAction`），
    其类型在 argparse 中是私有的，因此使用 `Any` 表示。
    """
    p = subparsers.add_parser(
        "test",
        help="通过天勤实时数据验证策略信号链路（不下单）",
        description="连接天勤实时行情驱动策略，打印交易信号用于验证链路正确性。\n\n"
        "安全保证：test 命令代码路径中不包含下单逻辑，即使账号已绑定期货公司也不会下单。",
    )
    p.add_argument("--strategy", required=True, help="策略名称 (e.g. ma/ma_strategy/ma_strategy.py)")
    p.add_argument("--symbol", required=True, help="合约代码 (e.g. SHFE.rb2509)")
    p.add_argument("--gui", action="store_true", help="启用浏览器可视化 (默认关闭)")


def register_live(subparsers: Any) -> None:
    """注册 live 子命令的 argparse 选项

    `subparsers` 是 `parser.add_subparsers()` 返回的对象（`argparse._SubParsersAction`），
    其类型在 argparse 中是私有的，因此使用 `Any` 表示。
    """
    p = subparsers.add_parser(
        "live",
        help="天勤模拟/实盘交易（会下单，模拟/实盘取决于账号是否绑定期货公司）",
        description="通过天勤 SDK 连接实时数据运行策略并下单。\n\n"
        "模拟 vs 实盘：取决于天勤账号是否绑定期货公司账户。\n"
        "  未绑定 → 模拟盘（虚拟资金，不影响真实账户）\n"
        "  已绑定 → 实盘（真金白银，慎用！）",
    )
    p.add_argument("--symbol", default="DCE.m2509", help="品种代码")
    p.add_argument("--gui", action="store_true", help="启用图形界面")
    p.add_argument("--config", default=None, help="配置文件路径")
    p.add_argument("--strategy", required=True, help="策略名称 (e.g. ma/ma_strategy/ma_strategy.py)")


def build_account(account_info: Any | None, account_type_override: str | None = None) -> tuple[Any, Any]:
    """根据配置构造 tqsdk 账户对象。

    Args:
        account_info: AccountInfo（含 api_key / api_secret / account_type 等），可为 None
        account_type_override: 不为 None 时强制使用此类型（如 test 强制 tqsim）

    Returns:
        (account_obj, auth_obj)

    账户类型说明：
      tqsim     → TqSim()，本地模拟，默认 1000 万虚拟资金，与账号绑定状态无关
      tqkq      → TqKq()，快期模拟盘
      tqaccount → TqAccount(broker_id, user, pwd)，实盘账户
    """
    account_type = account_type_override or (account_info.account_type if account_info else "tqsim")
    account_type = account_type.lower()

    if account_type not in VALID_ACCOUNT_TYPES:
        raise ValueError(f"未知的 account_type: {account_type} (可选: {', '.join(VALID_ACCOUNT_TYPES)})")

    auth = None
    if account_info and account_info.api_key and account_info.api_secret:
        auth = tqsdk.TqAuth(account_info.api_key, account_info.api_secret)

    if account_type == "tqsim":
        return tqsdk.TqSim(), auth
    if account_type == "tqkq":
        return tqsdk.TqKq(), auth
    # tqaccount
    if not (account_info and account_info.broker_id and account_info.broker_user):
        raise ValueError("account_type = tqaccount 时，必须在配置中填写 broker_id / broker_user / broker_password")
    return (
        tqsdk.TqAccount(
            account_info.broker_id,
            account_info.broker_user,
            account_info.broker_password,
        ),
        auth,
    )


def run_bridge(
    mode: str,
    args: argparse.Namespace,
    account_type: str | None = None,
    require_account: bool = False,
    trade: bool = False,
) -> None:
    """统一入口：加载策略 → 构造 bridge → 运行。

    Args:
        mode: "test" 或 "live"，用做日志前缀与数据库表前缀
        args: argparse.Namespace, 含 strategy / symbol / gui / config(可选)
        account_type: 不为 None 时强制使用此账户类型
        require_account: True 时若未配置账户则退出
        trade: True 走 TargetPosTask 下单；False 只回调打印信号
    """
    cm = ConfigManager(getattr(args, "config", None))
    dm = DataManager(cm)

    account = cm.get_account_info()
    if require_account and account is None:
        logger.error("请先在 config/conf.local.toml 中配置天勤账号信息")
        dm.store.log(mode, "配置缺失", symbol=args.symbol, status="ERROR")
        return

    if not tqsdk.ensure():
        logger.error("tqsdk 未安装")
        return

    tq_account, auth = build_account(account, account_type)

    strategy = load_strategy(args.strategy)
    cls_name = get_strategy_class_name(strategy)
    tc = cm.get_trading_config()
    bc = cm.get_backtest_config()

    strategy_config = MACrossParams()
    apply_strategy_config(strategy_config, cm)

    from strategies.core.state import State

    state = State(
        symbol=args.symbol,
        period=f"{tc.kline_period}m",
        strategy_config=strategy_config,
        capital=bc.initial_capital,
        contract_size=bc.contract_size,
        margin=0.1,
    )

    bridge = TqsdkStrategyBridge(strategy=strategy, state=state)
    gui = getattr(args, "gui", False)
    account_name = type(tq_account).__name__

    # ── 数据库持久化（表前缀 = mode） ──
    _ = dm.store
    session_model = get_live_session_model(f"{mode}_sessions")
    trade_model = get_live_trade_model(f"{mode}_trades")
    database.create_tables([session_model, trade_model], safe=True)  # type: ignore[arg-type]
    session = session_model.create(
        symbol=args.symbol,
        strategy="ma",
        mode=account_name,
        status="running",
        started_at=datetime.now(),
        initial_capital=state.capital,
    )

    counters = {"total": 0, "buy": 0, "sell": 0}

    def on_signal_cb(signal: Signal, price: float) -> None:
        counters["total"] += 1
        diag = " ".join(f"{k}={v:.4f}" for k, v in signal.diagnostics.items())
        direction = "long" if signal.action == TRADE_ACTION_BUY else "short"
        offset = "open" if signal.volume > 0 else "close"
        logger.info(
            f"[{mode.upper()}] #{counters['total']} {signal.action} "
            f"price={price:.2f} vol={signal.volume} "
            f"reason={signal.reason} | {diag}"
        )
        trade_model.create(
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
            counters["buy"] += 1
        elif signal.action == TRADE_ACTION_SELL:
            counters["sell"] += 1

    # bridge.run() 语义：on_signal=None → TargetPosTask 下单；否则回调
    bridge_on_signal = None if trade else on_signal_cb

    logger.info(
        f"[{mode.upper()}] 策略={cls_name} 标的={args.symbol} "
        f"账户={account_name} 下单={'ON' if trade else 'OFF'} "
        f"GUI={'开' if gui else '关'}"
    )
    dm.store.log(
        mode,
        f"开始: {args.symbol} strategy={cls_name} account={account_name} trade={trade}",
        symbol=args.symbol,
        status="INFO",
    )

    try:
        bridge.run(
            symbol=args.symbol,
            account=tq_account,
            auth=auth,
            on_signal=bridge_on_signal,
            web_gui=gui,
        )
    except KeyboardInterrupt:
        pass
    finally:
        session.update(
            status="stopped",
            ended_at=datetime.now(),
            total_signals=counters["total"],
            buy_signals=counters["buy"],
            sell_signals=counters["sell"],
        )
        logger.info(f"[{mode.upper()}] 完成: 信号={counters['total']} 买入={counters['buy']} 卖出={counters['sell']}")
        dm.store.log(mode, f"完成: signals={counters['total']}", status="INFO")


# ── CLI 入口：两个命令只剩参数差异 ──────────────────────────────


def cmd_test(args: argparse.Namespace) -> None:
    """test 命令：本地模拟，只验证信号链路，不下单。"""
    run_bridge(
        mode="test",
        args=args,
        account_type="tqsim",  # 强制本地模拟，与账号绑定状态无关
        require_account=False,  # test 允许 guest 匿名行情
        trade=False,  # 不走 TargetPosTask，只回调打印信号
    )


def cmd_live(args: argparse.Namespace) -> None:
    """live 命令：走 TargetPosTask 下单，账户类型读配置。"""
    run_bridge(
        mode="live",
        args=args,
        account_type=None,  # 读配置的 account_type
        require_account=True,  # live 必须有账号
        trade=True,  # 走 TargetPosTask 下单
    )
