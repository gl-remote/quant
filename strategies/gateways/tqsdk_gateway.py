"""tqsdk 框架网关适配器 - 将纯业务逻辑策略适配为天勤SDK可执行策略

使 MaStrategyCore 可在 tqsdk 环境中运行 (实盘、模拟、天勤回测)。
网关负责:
  - 天勤 API 的连接与认证
  - K线数据的获取与转换
  - 将核心层信号发送至天勤下单接口
  - 图形界面的启动与控制
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Any, List

from ..core.ma_strategy import (
    MaStrategyCore, TradingConfig, StrategyState,
    TradeRecord as CoreTradeRecord, PositionStatus,
)

logger = logging.getLogger(__name__)

_tq_imports = {}

def _import_tqsdk():
    if _tq_imports:
        return True
    try:
        from tqsdk import TqApi, TqAuth, TargetPosTask
        from tqsdk.ta import SMA
        _tq_imports.update(TqApi=TqApi, TqAuth=TqAuth,
                           TargetPosTask=TargetPosTask, SMA=SMA)
        return True
    except ImportError:
        return False


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
        self.config = core_config  # 兼容旧接口

        self.api = None
        self.account = None
        self.signal: Optional[str] = None  # 'buy' / 'sell' / None
        self.signal_reason: str = ""
        self.trade_records: List[CoreTradeRecord] = []
        self.symbol: str = ""

    @property
    def state(self) -> StrategyState:
        """向后兼容: 暴露核心策略状态"""
        return self._core.state

    @state.setter
    def state(self, value):
        self._core.state = value

    def calculate_sma(self, data, period: int) -> float:
        """计算SMA - 向后兼容旧接口

        支持 list 和 tqsdk kline_serial 对象
        """
        if _import_tqsdk():
            SMA = _tq_imports['SMA']
            try:
                result = SMA(data, period)
                return float(result.iloc[-1]) if len(result) > 0 else 0.0
            except Exception:
                pass
        if isinstance(data, list):
            return self._core.calculate_sma(data, period)
        try:
            closes = list(data.close)[-period:]
            return sum(closes) / len(closes) if closes else 0.0
        except Exception:
            return 0.0

    def check_crossover(self, short: float, long: float,
                        prev_short: float, prev_long: float) -> str:
        """检测交叉信号 - 向后兼容旧接口"""
        return self._core.check_crossover(short, long, prev_short, prev_long)

    def execute_buy(self, symbol: str, price: float, volume: int, reason: str):
        """执行买入 - 向后兼容旧接口"""
        self.symbol = symbol
        self._record_trade('buy', price, reason, volume)

    def execute_sell(self, symbol: str, price: float, volume: int, reason: str):
        """执行卖出 - 向后兼容旧接口"""
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
        """处理一根K线 - 返回信号供外部使用

        Args:
            kline_data: tqsdk kline_serial 对象 (须有 .close 属性)
        """
        self.signal = None
        self.signal_reason = ""

        if kline_data.empty:
            return

        try:
            closes = list(kline_data.close)
            current_price = float(kline_data.close.iloc[-1])
        except Exception as e:
            logger.error(f"获取价格数据失败: {e}")
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
            if volume <= 0:
                volume = 0
            self.trade_records.append(CoreTradeRecord(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                direction="卖出", price=price,
                volume=volume,
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
        if not _import_tqsdk():
            logger.error("天勤量化API未安装，请运行: pip install tqsdk")
            return

        TqApi = _tq_imports['TqApi']
        TqAuth = _tq_imports['TqAuth']

        self.symbol = symbol or ""
        try:
            api = TqApi(auth=auth or TqAuth("guest", ""))
            self.initialize(api)
            klines = api.get_kline_serial(self.symbol, 86400)
            logger.info(f"开始运行策略: {self.symbol}，按Ctrl+C停止")
            while True:
                api.wait_update()
                self.on_bar(klines)
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except Exception as e:
            logger.error(f"策略运行错误: {e}")
        finally:
            if self.api:
                self.api.close()
            perf = self.get_performance_summary()
            logger.info(
                f"绩效: 交易{perf['total_trades']}次 "
                f"胜率{perf['win_rate']:.0%} 盈亏{perf['total_profit']:.2f}"
            )

    def run_with_gui(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        if not _import_tqsdk():
            logger.error("天勤量化API未安装")
            return

        TqApi = _tq_imports['TqApi']
        TqAuth = _tq_imports['TqAuth']

        self.symbol = symbol or ""
        try:
            api = TqApi(auth=auth or TqAuth("guest", ""), web_gui=True)
            self.initialize(api)
            klines = api.get_kline_serial(self.symbol, 86400)
            logger.info(f"启动图形界面: {self.symbol}，浏览器访问 http://127.0.0.1:9876")
            while True:
                api.wait_update()
                self.on_bar(klines)
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except Exception as e:
            logger.error(f"策略运行错误: {e}")
        finally:
            if self.api:
                self.api.close()