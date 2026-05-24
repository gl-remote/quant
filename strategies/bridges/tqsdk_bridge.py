"""tqsdk 桥接器 - 将任意 Strategy 接口实现桥接到天勤SDK可执行策略

桥接器职责:
  - 接收 TradingContext，从中提取 Strategy 实例和运行参数
  - 天勤 API 的连接与认证
  - K线数据的获取与转换，传递给核心层 Strategy
  - 将核心层信号发送至天勤下单接口
  - 图形界面的启动与控制
  - 不直接依赖任何具体策略实现类，全部通过 Strategy 接口调用
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List

from ..core.base import Strategy, TradeRecord as CoreTradeRecord
from ..core.context import TradingContext

logger = logging.getLogger(__name__)


class TqsdkImports:
    """天勤 SDK 延迟导入管理器"""

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


class TqsdkStrategyBridge:
    """天勤策略桥接器 - 将 Strategy 接口实现桥接到天勤可执行策略

    策略由调用方通过 TradingContext 注入，桥接器自身不加载任何默认策略。

    运行模式:
      - 实盘/模拟: run() 方法
      - 图形界面: run_with_gui() 方法
      - 纯信号生成: on_bar() 方法 (供外部驱动，如天勤回测)
    """

    def __init__(self, context: TradingContext):
        """初始化天勤策略桥接器

        Args:
            context: 交易上下文 (必需)，提供 Strategy 实例和交易参数，
                     包含 symbol/capital/account 等运行所需信息
        """
        self._context = context
        self._core = context.strategy
        self.symbol: str = context.symbol
        self._capital = context.capital

        self.api: Any = None
        self.account: Any = None
        self.signal: Optional[str] = None
        self.signal_reason: str = ""
        self.trade_records: List[CoreTradeRecord] = []

    @property
    def config(self):
        return self._core.config

    @property
    def state(self):
        return self._core.state

    @state.setter
    def state(self, value):
        self._core.state = value

    def initialize(self, api: Optional[Any] = None):
        self.api = api
        if api:
            self.account = api.get_account()

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
            fund = self._capital
        return self._core.calc_position_size(price, fund)

    def get_performance_summary(self) -> Dict[str, Any]:
        return self._core.get_performance(self.trade_records)

    def run(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        if not _tqsdk.ensure():
            logger.error("天勤量化API未安装，请运行: pip install tqsdk")
            return

        symbol = symbol or self.symbol or ""
        if not auth and self._context and self._context.account:
            auth = _tqsdk.TqAuth(
                self._context.account['api_key'],
                self._context.account['api_secret'],
            )

        self.symbol = symbol
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

        symbol = symbol or self.symbol or ""
        if not auth and self._context and self._context.account:
            auth = _tqsdk.TqAuth(
                self._context.account['api_key'],
                self._context.account['api_secret'],
            )

        self.symbol = symbol
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
