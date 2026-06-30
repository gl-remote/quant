"""天勤实时行情工作流（阶段 3.5：从 tqsdk.py 抽取共用逻辑）

`test` 与 `live` 两条命令的共性是「连 TqApi → 桥接策略 → 订阅行情 → 跑事件循环」。
差异仅在于：
  - account_type       test 强制 tqsim；live 读配置
  - require_account    test 允许 guest 匿名行情；live 必须有账号配置
  - trade              test 只回调打印信号；live 走 TargetPosTask 下单

本模块提供 `TqsdkRealtimeWorkflow.run()` 接收纯净请求对象 + 三段差异参数，
commands 层各自传入对应值，workflow 不感知 argparse。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL
from common.tqsdk_imports import tqsdk
from config import ConfigManager
from data import DataManager
from data.connection import database
from data.models import RealtimeSession, RealtimeTrade
from loguru import logger
from strategies import Signal, Strategy
from strategies.bridges.tqsdk_bridge import TqsdkStrategyBridge
from strategies.ma_strategy import MACrossParams
from strategies.utils import apply_strategy_config, get_strategy_class_name, load_strategy

# 合法的账户类型
VALID_ACCOUNT_TYPES = ("tqsim", "tqkq", "tqaccount")


@dataclass(frozen=True)
class TqsdkRealtimeRequest:
    """天勤实时行情的请求对象，不依赖 argparse"""

    strategy: str
    symbol: str
    gui: bool
    config: str | None  # 可选配置文件路径


class TqsdkRealtimeWorkflow:
    """天勤实时行情编排：单次运行的生命周期。

    `run()` 接收请求对象 + 三段差异参数，commands 层各自传入对应值：
      - test: account_type="tqsim", require_account=False, trade=False
      - live: account_type=None, require_account=True, trade=True
    """

    def __init__(self, cm: ConfigManager | None = None, dm: DataManager | None = None) -> None:
        self._cm = cm
        self._dm = dm

    def run(
        self,
        req: TqsdkRealtimeRequest,
        mode: str,
        account_type: str | None = None,
        require_account: bool = False,
        trade: bool = False,
    ) -> None:
        """统一入口：加载策略 → 构造 bridge → 运行。

        Args:
            req: 请求对象（strategy / symbol / gui / config）
            mode: "test" 或 "live"，用做日志前缀与数据库表前缀
            account_type: 不为 None 时强制使用此账户类型（test 强制 tqsim）
            require_account: True 时若未配置账户则退出
            trade: True 走 TargetPosTask 下单；False 只回调打印信号
        """
        cm = self._cm or ConfigManager(config_file=req.config, env=mode)
        dm = self._dm or DataManager(cm)

        account = cm.get_account_info()
        if require_account and account is None:
            logger.error("请先在环境 local 配置中配置天勤账号信息")
            dm.store.log(mode, "配置缺失", symbol=req.symbol, status="ERROR")
            return

        if not tqsdk.ensure():
            logger.error("tqsdk 未安装")
            return

        tq_account, auth = _build_account(account, account_type)

        strategy = load_strategy(req.strategy)
        cls_name = get_strategy_class_name(strategy)
        tc = cm.get_trading_config()
        bc = cm.get_backtest_config()

        strategy_config = MACrossParams()
        apply_strategy_config(strategy_config, cm)

        from strategies.core.state import State

        state = State(
            symbol=req.symbol,
            period=f"{tc.kline_period}m",
            strategy_config=strategy_config,
            capital=bc.initial_capital,
            contract_size=bc.contract_size,
            margin=0.1,
        )

        bridge: TqsdkStrategyBridge[MACrossParams] = TqsdkStrategyBridge(
            strategy=cast(Strategy[MACrossParams], strategy),
            state=state,
        )
        account_name = type(tq_account).__name__

        # ── 数据库持久化：环境隔离由独立 SQLite 文件承担，实时链路使用统一表名 ──
        _ = dm.store
        database.create_tables([RealtimeSession, RealtimeTrade], safe=True)
        session = RealtimeSession.create(
            symbol=req.symbol,
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
            RealtimeTrade.create(
                session=session.id,
                datetime=datetime.now(),
                symbol=req.symbol,
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

        bridge_on_signal = None if trade else on_signal_cb

        logger.info(
            f"[{mode.upper()}] 策略={cls_name} 标的={req.symbol} "
            f"账户={account_name} 下单={'ON' if trade else 'OFF'} "
            f"GUI={'开' if req.gui else '关'}"
        )
        dm.store.log(
            mode,
            f"开始: {req.symbol} strategy={cls_name} account={account_name} trade={trade}",
            symbol=req.symbol,
            status="INFO",
        )

        try:
            bridge.run(
                symbol=req.symbol,
                account=tq_account,
                auth=auth,
                on_signal=bridge_on_signal,
                web_gui=req.gui,
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
            logger.info(
                f"[{mode.upper()}] 完成: 信号={counters['total']} 买入={counters['buy']} 卖出={counters['sell']}"
            )
            dm.store.log(mode, f"完成: signals={counters['total']}", status="INFO")


def _build_account(account_info: Any | None, account_type_override: str | None = None) -> tuple[Any, Any]:
    """根据配置构造 tqsdk 账户对象。

    Args:
        account_info: AccountInfo（含 api_key / api_secret / account_type 等），可为 None
        account_type_override: 不为 None 时强制使用此类型（如 test 强制 tqsim）

    Returns:
        (account_obj, auth_obj)
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
