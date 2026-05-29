"""tqsdk 桥接器 — 将 Strategy 接口桥接到天勤SDK

桥接器仅负责:
  1. 天勤 kline_serial DataFrame → 标准 Bar 的数据转换
  2. 调用 strategy.on_bar(bar) 获取 Signal → 返回给调用方
  3. 天勤 API 连接/认证/图形界面

所有交易状态由 Strategy 管理。on_bar() 是无状态方法，直接返回 Signal。

调用方通过 strategy.position 获取状态。
"""

import logging
from datetime import datetime
from typing import Any

from strategies import Strategy, Bar, Signal, Fill
from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL
from common.schemas import KlineDataFrame
from common.typing import check_types
from common.tqsdk_imports import tqsdk

logger = logging.getLogger(__name__)


class TqsdkStrategyBridge:
    """天勤策略桥接器 — 纯协议转换层

    调用流程:
      signal = bridge.on_bar(kline_data)  # DataFrame → Bar → Strategy → Signal
      caller 根据 signal 执行下单 → strategy.on_fill(fill)
    """

    def __init__(self, strategy: Strategy[Any], symbol: str):
        self._strategy: Strategy[Any] = strategy
        self.symbol: str = symbol

        self.api: Any = None
        self.account: Any = None

    @property
    def strategy(self) -> Strategy[Any]:
        return self._strategy

    def initialize(self, api: Any | None = None):
        self.api = api
        if api:
            self.account = api.get_account()

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
            logger.error(f"获取价格数据失败: {e}", exc_info=True)
            return Signal()

        bar = Bar(
            symbol=self.symbol,
            datetime=datetime.now(),
            open=float(kline_data.open.iloc[idx]),
            high=float(kline_data.high.iloc[idx]),
            low=float(kline_data.low.iloc[idx]),
            close=last_close,
            volume=float(kline_data.volume.iloc[idx]),
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

    def _ensure_auth(self, auth: Any | None, symbol: str) -> Any:
        """统一认证和符号设置"""
        self.symbol = symbol or self.symbol or ""
        if not auth and self.account is None:
            auth = tqsdk.TqAuth("guest", "")
        return auth or tqsdk.TqAuth("guest", "")

    def _watch_klines(self, api, klines, symbol: str):
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
        while True:
            api.wait_update()
            if api.is_changing(klines):
                current_len = len(klines)
                for i in range(prev_kline_len, current_len):
                    signal = self.on_bar(klines, idx=i)
                    if signal.action == TRADE_ACTION_BUY:
                        target_pos.set_target_volume(signal.volume)
                        self.notify_fill(signal, float(klines.close.iloc[i]))
                    elif signal.action == TRADE_ACTION_SELL:
                        target_pos.set_target_volume(0)
                        self.notify_fill(signal, float(klines.close.iloc[i]))
                prev_kline_len = current_len

    def _run_loop(self, symbol: str, auth: Any, web_gui: bool = False):
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
            logger.info(log_msg)
            self._watch_klines(api, klines, symbol)
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except Exception as e:
            logger.error(f"策略运行错误: {e}", exc_info=True)
        finally:
            if self.api:
                self.api.close()
            p = self._strategy
            fills_count = len(p.fills)
            sells = len([f for f in p.fills if f.action == TRADE_ACTION_SELL])
            logger.info(
                f"策略停止: fills={fills_count} sells={sells}"
            )

    def run(self, symbol: str | None = None, auth: Any | None = None):
        auth = self._ensure_auth(auth, symbol or "")
        self._run_loop(symbol or self.symbol, auth, web_gui=False)

    def run_with_gui(self, symbol: str | None = None, auth: Any | None = None):
        auth = self._ensure_auth(auth, symbol or "")
        self._run_loop(symbol or self.symbol, auth, web_gui=True)
