"""vn.py 框架均线交叉策略 - 基于 SMA 金叉/死叉的交易信号，含止损止盈"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    from vnpy_ctastrategy import CtaTemplate
    from vnpy.trader.constant import Direction, Offset, Interval, Status
    from vnpy.trader.object import BarData, TickData, OrderData, TradeData
    HAS_VNPY = True
except ImportError:
    HAS_VNPY = False
    logger.warning("vnpy未安装，策略将运行在兼容模式")
    CtaTemplate = object
    BarData = object
    TickData = object
    OrderData = object
    TradeData = object


class VnpyMaStrategy(CtaTemplate if HAS_VNPY else object):
    """双均线交叉CTA策略 - 金叉买入、死叉卖出，配合止损止盈

    vn.py 标准策略接口:
      - on_init(): 策略初始化
      - on_start(): 策略启动
      - on_stop(): 策略停止
      - on_bar(bar): K线回调 (核心交易逻辑)
      - on_tick(tick): Tick回调 (分钟/日线策略忽略)

    策略参数:
      - sma_short: 短期均线周期 (默认5)
      - sma_long: 长期均线周期 (默认20)
      - stop_loss_ratio: 止损比例 (默认0.03 = 3%)
      - take_profit_ratio: 止盈比例 (默认0.05 = 5%)
      - position_ratio: 仓位比例 (默认0.1 = 10%)
      - price_tick: 最小价格变动单位
    """

    author = "Quant System"

    # vn.py 策略参数 (通过 add_strategy 的 setting 字典传入)
    parameters = [
        "sma_short", "sma_long",
        "stop_loss_ratio", "take_profit_ratio",
        "position_ratio", "price_tick"
    ]
    # vn.py 策略变量 (会被序列化记录)
    variables = [
        "entry_price", "pos", "sma_short_val",
        "sma_long_val", "prev_sma_short", "prev_sma_long"
    ]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict):
        if HAS_VNPY:
            super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        else:
            self.cta_engine = cta_engine
            self.strategy_name = strategy_name
            self.vt_symbol = vt_symbol

        # 策略参数
        self.sma_short: int = setting.get('sma_short', 5)
        self.sma_long: int = setting.get('sma_long', 20)
        self.stop_loss_ratio: float = setting.get('stop_loss_ratio', 0.03)
        self.take_profit_ratio: float = setting.get('take_profit_ratio', 0.05)
        self.position_ratio: float = setting.get('position_ratio', 0.1)
        self.price_tick: float = setting.get('price_tick', 1.0)

        # 内部状态
        self.entry_price: float = 0.0
        self.sma_short_val: float = 0.0
        self.sma_long_val: float = 0.0
        self.prev_sma_short: float = 0.0
        self.prev_sma_long: float = 0.0

        # 历史收盘价缓存 (用于SMA计算)
        self._close_history: list = []

        self.trade_count: int = 0
        self.win_count: int = 0
        self.total_profit: float = 0.0

    def on_init(self):
        """策略初始化回调"""
        logger.info(f"[{self.strategy_name}] 策略初始化: SMA({self.sma_short},{self.sma_long}) "
                     f"止损={self.stop_loss_ratio:.0%} 止盈={self.take_profit_ratio:.0%}")
        if HAS_VNPY:
            self.write_log(f"策略初始化: SMA({self.sma_short},{self.sma_long})")
            self.load_bar(10)

    def on_start(self):
        """策略启动回调"""
        logger.info(f"[{self.strategy_name}] 策略启动")
        if HAS_VNPY:
            self.write_log("策略启动")

    def on_stop(self):
        """策略停止回调"""
        logger.info(f"[{self.strategy_name}] 策略停止 | "
                     f"交易{self.trade_count}次 胜{self.win_count} "
                     f"总盈亏{self.total_profit:.2f}")
        if HAS_VNPY:
            self.write_log(f"策略停止: 交易{self.trade_count}次 总盈亏{self.total_profit:.2f}")

    def on_bar(self, bar):
        """K线行情回调 - 核心交易逻辑

        vn.py 回测引擎每隔一个Bar调用此方法

        Args:
            bar: vnpy BarData 对象或字典 (兼容模式)，包含 OHLCV 数据
        """
        close_price = bar.close_price if hasattr(bar, 'close_price') else bar['close_price']

        # 维护收盘价历史
        self._close_history.append(close_price)

        # 计算双均线
        self.prev_sma_short = self.sma_short_val
        self.prev_sma_long = self.sma_long_val

        if len(self._close_history) >= self.sma_long:
            self.sma_short_val = self._calculate_sma(self.sma_short)
            self.sma_long_val = self._calculate_sma(self.sma_long)
        else:
            return

        # 未持仓：检查金叉买入信号
        if self.pos == 0:
            if self.prev_sma_short <= self.prev_sma_long and \
               self.sma_short_val > self.sma_long_val:
                self._signal_buy(bar)
        else:
            # 已持仓：检查止盈止损和死叉信号
            if self._check_stop_loss(close_price):
                self._signal_sell(bar, "止损")
            elif self._check_take_profit(close_price):
                self._signal_sell(bar, "止盈")
            elif self.prev_sma_short >= self.prev_sma_long and \
                 self.sma_short_val < self.sma_long_val:
                self._signal_sell(bar, "死叉")

    def _calculate_sma(self, period: int) -> float:
        """计算简单移动平均线"""
        if len(self._close_history) < period:
            return 0.0
        return sum(self._close_history[-period:]) / period

    def _signal_buy(self, bar: BarData):
        """发出买入信号"""
        volume = self._calc_volume(bar.close_price)
        if volume <= 0:
            return
        if HAS_VNPY:
            self.buy(bar.close_price, volume)
        self.entry_price = bar.close_price
        self.trade_count += 1
        logger.info(
            f"[{self.strategy_name}] {bar.datetime} 金叉买入 "
            f"@{bar.close_price:.2f} x{volume}"
        )

    def _signal_sell(self, bar: BarData, reason: str):
        """发出卖出信号"""
        if HAS_VNPY:
            self.sell(bar.close_price, abs(self.pos))
        profit = (bar.close_price - self.entry_price) * abs(self.pos)
        self.total_profit += profit
        self.entry_price = 0.0
        if profit > 0:
            self.win_count += 1
        logger.info(
            f"[{self.strategy_name}] {bar.datetime} {reason}卖出 "
            f"@{bar.close_price:.2f} 盈亏{profit:.2f}"
        )

    def _calc_volume(self, price: float) -> int:
        """计算开仓手数"""
        capital = self.cta_engine.capital if hasattr(self.cta_engine, 'capital') else 100000
        contract_size = getattr(self, 'contract_size', 10)
        vol = capital * self.position_ratio / (price * contract_size)
        return max(1, int(vol))

    def _check_stop_loss(self, price: float) -> bool:
        """检查止损条件"""
        if self.entry_price <= 0:
            return False
        return (self.entry_price - price) / self.entry_price >= self.stop_loss_ratio

    def _check_take_profit(self, price: float) -> bool:
        """检查止盈条件"""
        if self.entry_price <= 0:
            return False
        return (price - self.entry_price) / self.entry_price >= self.take_profit_ratio

    def on_tick(self, tick: TickData):
        """Tick行情回调 (本策略不使用)"""
        pass

    def on_order(self, order: OrderData):
        """委托回报回调"""
        if HAS_VNPY:
            super().on_order(order)

    def on_trade(self, trade: TradeData):
        """成交回报回调"""
        if HAS_VNPY:
            super().on_trade(trade)

    def get_performance(self) -> Dict:
        """获取策略绩效摘要"""
        return {
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'lose_count': self.trade_count - self.win_count,
            'win_rate': self.win_count / max(self.trade_count, 1),
            'total_profit': self.total_profit,
        }