"""tqsdk 桥接器 — 将 Strategy 接口桥接到天勤SDK

桥接器仅负责:
  1. 天勤 kline_serial DataFrame → 标准 Bar 的数据转换
  2. 调用 strategy.on_bar(bar) 获取 Signal → 返回给调用方
  3. 天勤 API 连接/认证/图形界面

所有交易状态由 Strategy 管理。on_bar() 是无状态方法，直接返回 Signal。

调用方通过 strategy.performance / strategy.position 获取状态。
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List

from ..core.base import Strategy
from ..core.context import TradingContext
from ..core.types import Bar, Signal, Fill

logger = logging.getLogger(__name__)


class TqsdkImports:
    """天勤 SDK 延迟导入管理器"""

    def __init__(self):
        self._loaded: bool = False
        self.TqApi: Any = None
        self.TqAuth: Any = None
        self.TargetPosTask: Any = None

    def ensure(self) -> bool:
        if self._loaded:
            return True
        try:
            from tqsdk import TqApi, TqAuth, TargetPosTask
            self.TqApi = TqApi
            self.TqAuth = TqAuth
            self.TargetPosTask = TargetPosTask
            self._loaded = True
            return True
        except ImportError:
            return False


_tqsdk = TqsdkImports()


class TqsdkStrategyBridge:
    """天勤策略桥接器 — 纯协议转换层

    调用流程:
      signal = bridge.on_bar(kline_data)  # DataFrame → Bar → Strategy → Signal
      caller 根据 signal 执行下单 → strategy.on_fill(fill)
    """

    def __init__(self, context: TradingContext):
        self._strategy: Strategy = context.strategy
        self.symbol: str = context.symbol

        self.api: Any = None
        self.account: Any = None

    @property
    def strategy(self) -> Strategy:
        return self._strategy

    def initialize(self, api: Optional[Any] = None):
        self.api = api
        if api:
            self.account = api.get_account()

    def on_bar(self, kline_data) -> Signal:
        """处理天勤K线数据，返回标准化 Signal

        无状态 — 每次调用独立转换并返回结果。
        """

        if kline_data.empty:
            return Signal()

        try:
            last_close = float(kline_data.close.iloc[-1])
        except Exception as e:
            logger.error(f"获取价格数据失败: {e}", exc_info=True)
            return Signal()

        bar = Bar(
            symbol=self.symbol,
            datetime=str(datetime.now()),
            open=float(kline_data.open.iloc[-1]),
            high=float(kline_data.high.iloc[-1]),
            low=float(kline_data.low.iloc[-1]),
            close=last_close,
            volume=float(kline_data.volume.iloc[-1]),
        )

        return self._strategy.on_bar(bar)

    def notify_fill(self, signal: Signal, fill_price: float) -> None:
        """通知 Strategy 订单成交"""
        self._strategy.on_fill(Fill(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol=self.symbol,
            action=signal.action,
            price=fill_price,
            volume=signal.volume,
            reason=signal.reason,
        ))

    # ---- 实盘/模拟运行 ----

    def run(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        if not _tqsdk.ensure():
            logger.error("天勤量化API未安装，请运行: pip install tqsdk")
            return

        symbol = symbol or self.symbol or ""
        if not auth and self.account is None:
            auth = _tqsdk.TqAuth("guest", "")

        self.symbol = symbol
        try:
            api = _tqsdk.TqApi(auth=auth or _tqsdk.TqAuth("guest", ""))
            self.initialize(api)
            target_pos = _tqsdk.TargetPosTask(api, symbol)
            klines = api.get_kline_serial(symbol, 86400)
            logger.info(f"开始运行策略: {symbol}，按Ctrl+C停止")
            while True:
                api.wait_update()
                if api.is_changing(klines):
                    signal = self.on_bar(klines)
                    if signal.action == 'buy':
                        target_pos.set_target_volume(signal.volume)
                        self.notify_fill(
                            signal,
                            float(klines.close.iloc[-1]),
                        )
                    elif signal.action == 'sell':
                        target_pos.set_target_volume(0)
                        self.notify_fill(
                            signal,
                            float(klines.close.iloc[-1]),
                        )
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except Exception as e:
            logger.error(f"策略运行错误: {e}", exc_info=True)
        finally:
            if self.api:
                self.api.close()
            p = self._strategy.performance
            logger.info(
                f"绩效: 交易{p.total_trades}次 "
                f"胜率{p.win_rate:.0%} 盈亏{p.total_profit:.2f}"
            )

    def run_with_gui(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        if not _tqsdk.ensure():
            logger.error("天勤量化API未安装")
            return

        symbol = symbol or self.symbol or ""
        if not auth:
            auth = _tqsdk.TqAuth("guest", "")

        self.symbol = symbol
        try:
            api = _tqsdk.TqApi(auth=auth, web_gui=True)
            self.initialize(api)
            target_pos = _tqsdk.TargetPosTask(api, symbol)
            klines = api.get_kline_serial(symbol, 86400)
            logger.info(
                f"启动图形界面: {symbol}，浏览器访问 http://127.0.0.1:9876"
            )
            while True:
                api.wait_update()
                if api.is_changing(klines):
                    signal = self.on_bar(klines)
                    if signal.action == 'buy':
                        target_pos.set_target_volume(signal.volume)
                        self.notify_fill(
                            signal,
                            float(klines.close.iloc[-1]),
                        )
                    elif signal.action == 'sell':
                        target_pos.set_target_volume(0)
                        self.notify_fill(
                            signal,
                            float(klines.close.iloc[-1]),
                        )
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except Exception as e:
            logger.error(f"策略运行错误: {e}", exc_info=True)
        finally:
            if self.api:
                self.api.close()
