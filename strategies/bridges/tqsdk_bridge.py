"""tqsdk 桥接器 — 将 Strategy 接口桥接到天勤SDK

桥接器负责:
  1. 天勤 kline_serial DataFrame → 标准 Bar 的数据转换
  2. 调用 strategy.on_bar(state, ctx) 获取 Signal → 返回给调用方
  3. 天勤 API 连接/认证/图形界面

所有交易状态由 State 管理，Bridge 通过 notify_fill 同步。
"""

from loguru import logger
from datetime import datetime
from typing import Any, cast, TypeVar, Generic

from strategies import Strategy, Bar, Signal, Fill, State

T = TypeVar('T')
from strategies.runtime import BarContext
from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT
from common.types import PositionDirection
from common.schemas import KlineDataFrame
from common.typing import check_types
from common.tqsdk_imports import tqsdk

def _to_datetime(raw_dt: int) -> datetime:
    """将 tqsdk kline_serial 的 datetime 转为 Python datetime

    tqsdk 文档:
      datetime 列为自 unix epoch 以来的**纳秒**数 (int64)，例如 1501080715000000000。
    参见: TqApi.get_kline_serial 的 Returns 部分。

    注意: 此格式不同于常见的毫秒/秒时间戳，转换时必须除以 1e9。
    """
    return datetime.fromtimestamp(raw_dt / 1_000_000_000)


class TqsdkStrategyBridge(Generic[T]):
    """天勤策略桥接器 — 纯协议转换层

    调用流程:
      signal = bridge.on_bar(kline_data)  # DataFrame → Bar → Strategy → Signal
      caller 根据 signal 执行下单 → bridge.notify_fill(fill)

    类型参数 T: 策略配置的具体类型，与 Strategy[T] 和 State[T] 保持一致
    """

    def __init__(self, strategy: Strategy[T], state: State[T]):
        self._strategy: Strategy[T] = strategy
        self._state: State[T] = state
        self.symbol: str = state.symbol

        self.api: Any = None
        self.account: Any = None

    @property
    def strategy(self) -> Strategy[T]:
        return self._strategy

    @property
    def fills(self) -> list[Fill]:
        return list(self._state.fills)

    def initialize(self, api: Any | None = None) -> None:
        self.api = api
        if api:
            self.account = api.get_account()

    def _update_peak_prices(self, bar: Bar) -> None:
        """更新持仓期间的 peak 价格，在调用 strategy.on_bar 前执行"""
        pos = self._state.position
        if not pos.direction:
            return
        if pos.direction == TRADE_DIRECTION_LONG:
            if bar.high > pos.highest_price:
                pos.highest_price = bar.high
            if pos.lowest_price == 0.0 or bar.low < pos.lowest_price:
                pos.lowest_price = bar.low
        elif pos.direction == TRADE_DIRECTION_SHORT:
            if pos.highest_price == 0.0 or bar.high > pos.highest_price:
                pos.highest_price = bar.high
            if bar.low < pos.lowest_price:
                pos.lowest_price = bar.low

    @check_types
    def on_bar(self, kline_data: KlineDataFrame, idx: int = -1) -> Signal:
        """处理天勤K线数据指定索引行，返回标准化 Signal

        无状态 — 每次调用独立转换并返回结果。
        idx 默认为 -1 (最新一根K线)，传具体索引可处理历史行。
        """

        if kline_data.empty:
            return Signal()

        try:
            last_close = float(kline_data.close.iloc[idx])
        except Exception as e:
            logger.exception(f"获取价格数据失败: {e}")
            return Signal()

        bar = Bar(
            symbol=self.symbol,
            datetime=_to_datetime(kline_data.datetime.iloc[idx]),
            open=float(kline_data.open.iloc[idx]),
            high=float(kline_data.high.iloc[idx]),
            low=float(kline_data.low.iloc[idx]),
            close=last_close,
            volume=float(kline_data.volume.iloc[idx]),
        )

        ctx = BarContext(symbol=self.symbol, bar=bar, multi={}, events=[])
        # 调用 strategy 前更新 peak 价格
        self._update_peak_prices(bar)

        return self._strategy.on_bar(self._state, ctx)

    def notify_fill(self, signal: Signal, fill_price: float) -> None:
        """通知 Strategy 订单成交，同步更新 State"""
        from strategies.core.types import StrategyPosition

        fill = Fill(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbol=self.symbol,
            action=signal.action,
            price=fill_price,
            volume=signal.volume,
            reason=signal.reason,
        )
        self._state.fills.append(fill)

        if signal.action == TRADE_ACTION_BUY:
            self._state.position = StrategyPosition(
                direction=cast(PositionDirection, TRADE_DIRECTION_LONG),
                entry_price=fill_price,
                volume=signal.volume,
                highest_price=fill_price,
                lowest_price=fill_price,
            )
        elif signal.action == TRADE_ACTION_SELL:
            self._state.position = StrategyPosition()

        self._strategy.on_fill(fill)

    # ---- 实盘/模拟运行 ----

    def _ensure_auth(self, auth: Any | None, symbol: str) -> Any:
        """统一认证和符号设置"""
        self.symbol = symbol or self.symbol or ""
        if not auth and self.account is None:
            auth = tqsdk.TqAuth("guest", "")
        return auth or tqsdk.TqAuth("guest", "")

    def _watch_klines(self, api: Any, klines: KlineDataFrame, symbol: str) -> None:
        """监控 K 线序列变化并驱动策略 — 回测/实盘共用核心循环

        跟踪 kline_serial 长度变化，每次 wait_update 处理所有新增 K 线，
        避免仅取 iloc[-1] 时跳过中间数据。

        此方法被 _run_loop (实盘/模拟) 和 CLI _run_tq_backtest (回测) 共用，
        消除了两处 ~50 行重复的行情处理循环。

        Args:
            api: TqApi 实例 (可能含 TqBacktest 包装)
            klines: get_kline_serial 返回的 DataFrame
            symbol: 品种代码

        Raises:
            BacktestFinished: 回测模式下由 TqApi.wait_update() 自然抛出
        """
        target_pos = tqsdk.TargetPosTask(api, symbol)
        prev_kline_len = len(klines)
        bar_log_count = 0
        while True:
            api.wait_update()
            if api.is_changing(klines):
                current_len = len(klines)
                for i in range(prev_kline_len, current_len):
                    signal = self.on_bar(klines, idx=i)
                    bar_log_count += 1
                    if signal.action:
                        diag_str = " ".join(f"{k}={v:.4f}" for k, v in signal.diagnostics.items())
                        logger.debug("[{}] signal={} reason={} vol={} | {}",
                                    self.symbol, signal.action, signal.reason, signal.volume, diag_str)
                    elif bar_log_count % 100 == 1:
                        if signal.diagnostics:
                            diag_str = " ".join(f"{k}={v:.4f}" for k, v in signal.diagnostics.items())
                        else:
                            diag_str = f"close={float(klines.close.iloc[i]):.4f}"
                        logger.debug("[{}] no signal | {}", self.symbol, diag_str)
                    if signal.action == TRADE_ACTION_BUY:
                        target_pos.set_target_volume(signal.volume)
                        self.notify_fill(signal, float(klines.close.iloc[i]))
                    elif signal.action == TRADE_ACTION_SELL:
                        target_pos.set_target_volume(0)
                        self.notify_fill(signal, float(klines.close.iloc[i]))
                prev_kline_len = current_len

    def _run_loop(self, symbol: str, auth: Any, web_gui: bool = False) -> None:
        """实盘/模拟主循环 — 初始化 API 后委托 _watch_klines 驱动策略"""
        if not tqsdk.ensure():
            logger.error("天勤量化API未安装，请运行: pip install tqsdk")
            return

        try:
            api = tqsdk.TqApi(auth=auth, web_gui=web_gui)
            self.initialize(api)
            klines = api.get_kline_serial(symbol, 86400)
            log_msg = f"开始运行策略: {symbol}，按Ctrl+C停止"
            if web_gui:
                log_msg += "，浏览器访问 http://127.0.0.1:9876"
            logger.debug(log_msg)
            self._watch_klines(api, klines, symbol)
        except KeyboardInterrupt:
            logger.debug("策略已停止")
        except Exception as e:
            logger.exception(f"策略运行错误: {e}")
        finally:
            if self.api:
                self.api.close()
            fills_count = len(self._state.fills)
            sells = len([f for f in self._state.fills if f.action == TRADE_ACTION_SELL])
            logger.debug(
                f"策略停止: fills={fills_count} sells={sells}"
            )

    def run(self, symbol: str | None = None, auth: Any | None = None) -> None:
        auth = self._ensure_auth(auth, symbol or "")
        self._run_loop(symbol or self.symbol, auth, web_gui=False)

    def run_with_gui(self, symbol: str | None = None, auth: Any | None = None) -> None:
        auth = self._ensure_auth(auth, symbol or "")
        self._run_loop(symbol or self.symbol, auth, web_gui=True)
