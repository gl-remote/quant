"""tqsdk 框架网关适配器 - 将纯业务逻辑策略适配为天勤SDK可执行策略

使 MaStrategyCore 可在 tqsdk 环境中运行 (实盘、模拟、天勤回测)。
网关负责:
  - 天勤 API 的连接与认证
  - K线数据的获取与转换
  - 将核心层信号发送至天勤下单接口
  - 图形界面的启动与控制
"""

import logging
import warnings
from datetime import datetime
from typing import Dict, Optional, Any, List

from ..core.ma_strategy import (
    MaStrategyCore, TradingConfig, StrategyState,
    TradeRecord as CoreTradeRecord, PositionStatus,
)

logger = logging.getLogger(__name__)


class TqsdkImports:
    """天勤 SDK 延迟导入管理器

    避免模块级可变全局状态，按需导入 tqsdk 模块。
    """

    def __init__(self):
        self._loaded: bool = False
        self.TqApi: Any = None
        self.TqAuth: Any = None
        self.TargetPosTask: Any = None
        self.SMA: Any = None

    def ensure(self) -> bool:
        if self._loaded:
            return True
        try:
            from tqsdk import TqApi, TqAuth, TargetPosTask
            from tqsdk.ta import SMA
            self.TqApi = TqApi
            self.TqAuth = TqAuth
            self.TargetPosTask = TargetPosTask
            self.SMA = SMA
            self._loaded = True
            return True
        except ImportError:
            return False


_tqsdk = TqsdkImports()


class TqsdkMaStrategy:
    """双均线交叉策略 (天勤网关)

    支持三种运行模式:
      - 实盘/模拟: run() 方法
      - 图形界面: run_with_gui() 方法
      - 纯信号生成: on_bar() 方法 (供外部驱动，如天勤回测)
    """

    def __init__(self, config: Optional[TradingConfig] = None):
        core_config = config or TradingConfig()
        self._core = MaStrategyCore(core_config)
        self.config = core_config

        self.api: Any = None
        self.account: Any = None
        self.signal: Optional[str] = None
        self.signal_reason: str = ""
        self.trade_records: List[CoreTradeRecord] = []
        self.symbol: str = ""

    @property
    def state(self) -> StrategyState:
        return self._core.state

    @state.setter
    def state(self, value: StrategyState):
        self._core.state = value

    def calculate_sma(self, data, period: int) -> float:
        warnings.warn(
            "TqsdkMaStrategy.calculate_sma 已废弃，请直接使用 _core.calculate_sma",
            DeprecationWarning, stacklevel=2,
        )
        if isinstance(data, list):
            return self._core.calculate_sma(data, period)
        try:
            closes = list(data.close)[-period:]
            return sum(closes) / len(closes) if closes else 0.0
        except Exception:
            return 0.0

    def check_crossover(self, short: float, long: float,
                        prev_short: float, prev_long: float) -> str:
        warnings.warn(
            "TqsdkMaStrategy.check_crossover 已废弃，请直接使用 _core.check_crossover",
            DeprecationWarning, stacklevel=2,
        )
        return self._core.check_crossover(short, long, prev_short, prev_long)

    def execute_buy(self, symbol: str, price: float, volume: int, reason: str):
        warnings.warn(
            "TqsdkMaStrategy.execute_buy 已废弃，请使用 _record_trade",
            DeprecationWarning, stacklevel=2,
        )
        self.symbol = symbol
        self._record_trade('buy', price, reason, volume)

    def execute_sell(self, symbol: str, price: float, volume: int, reason: str):
        warnings.warn(
            "TqsdkMaStrategy.execute_sell 已废弃，请使用 _record_trade",
            DeprecationWarning, stacklevel=2,
        )
        self.symbol = symbol
        self._record_trade('sell', price, reason, volume)

    def initialize(self, api: Optional[Any] = None):
        self.api = api
        if api:
            self.account = api.get_account()
        logger.info(
            f"策略初始化: SMA({self.config.sma_short},{self.config.sma_long})"
        )

    def on_bar(self, kline_data):
        self.signal = None
        self.signal_reason = ""

        if kline_data.empty:
            return

        try:
            closes = list(kline_data.close)
            current_price = float(kline_data.close.iloc[-1])
        except Exception as e:
            logger.error(f"获取价格数据失败: {e}", exc_info=True)
            return

        signal, reason = self._core.on_bar_signal(closes, current_price)

        if signal == 'sell':
            self.signal, self.signal_reason = signal, reason
            self._record_trade('sell', current_price, reason)
        elif signal == 'buy':
            self.signal, self.signal_reason = signal, reason

    def _record_trade(self, direction: str, price: float, reason: str,
                      volume: int = 0):
        if direction == 'buy':
            if volume <= 0:
                volume = self._calc_position_size(price)
            self._core.on_enter(price, volume)
            self.trade_records.append(CoreTradeRecord(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                direction="买入", price=price, volume=volume, reason=reason,
            ))
            logger.info(f"买入: {self.symbol} @ {price}, 数量: {volume}, 原因: {reason}")
        elif direction == 'sell':
            profit = self._core.on_exit(price)
            self.trade_records.append(CoreTradeRecord(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                direction="卖出", price=price, volume=volume,
                reason=reason, profit=profit,
            ))
            logger.info(f"卖出: {self.symbol} @ {price}, 原因: {reason}, 盈亏: {profit:.2f}")

    def _calc_position_size(self, price: float) -> int:
        if self.account and hasattr(self.account, 'available'):
            fund = float(self.account.available)
        else:
            fund = 100000.0
        return self._core.calc_position_size(price, fund)

    def get_performance_summary(self) -> Dict[str, Any]:
        return self._core.get_performance(self.trade_records)

    def run(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        if not _tqsdk.ensure():
            logger.error("天勤量化API未安装，请运行: pip install tqsdk")
            return

        self.symbol = symbol or ""
        try:
            api = _tqsdk.TqApi(auth=auth or _tqsdk.TqAuth("guest", ""))
            self.initialize(api)
            klines = api.get_kline_serial(self.symbol, 86400)
            logger.info(f"开始运行策略: {self.symbol}，按Ctrl+C停止")
            while True:
                api.wait_update()
                self.on_bar(klines)
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except Exception as e:
            logger.error(f"策略运行错误: {e}", exc_info=True)
        finally:
            if self.api:
                self.api.close()
            perf = self.get_performance_summary()
            logger.info(
                f"绩效: 交易{perf['total_trades']}次 "
                f"胜率{perf['win_rate']:.0%} 盈亏{perf['total_profit']:.2f}"
            )

    def run_with_gui(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        if not _tqsdk.ensure():
            logger.error("天勤量化API未安装")
            return

        self.symbol = symbol or ""
        try:
            api = _tqsdk.TqApi(auth=auth or _tqsdk.TqAuth("guest", ""), web_gui=True)
            self.initialize(api)
            klines = api.get_kline_serial(self.symbol, 86400)
            logger.info(f"启动图形界面: {self.symbol}，浏览器访问 http://127.0.0.1:9876")
            while True:
                api.wait_update()
                self.on_bar(klines)
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except Exception as e:
            logger.error(f"策略运行错误: {e}", exc_info=True)
        finally:
            if self.api:
                self.api.close()