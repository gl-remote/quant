"""tqsdk 桥接器 — 将 Strategy 接口桥接到天勤SDK

桥接器职责（参见 cli/tqsdk-test-plan.md §7）:
  1. 天勤 API 连接管理（支持外部注入，多合约共享）
  2. 多周期 kline_serial 订阅
  3. kline_serial DataFrame → PeriodData → 指标计算（复用回测路径同一套逻辑）
  4. 构造完整 BarContext（含多周期指标视图）
  5. 驱动 strategy.on_bar(state, ctx) 获取 Signal
  6. 信号分发：test 回调打印 / live TargetPosTask 下单

安全设计（参见 cli/tqsdk-test-plan.md §8 决策项2）:
  命令即安全边界 — test 代码路径中不包含 TargetPosTask，
  即使天勤账号已绑定期货公司，运行 test 也永远不会下单。

多合约支持（参见 cli/tqsdk-test-plan.md §8 决策项5 / §3.2）:
  CLI 创建 1 个 TqApi 实例，通过构造函数 api 参数注入给 N 个 Bridge 共享。
  每个 Bridge 有独立的 State / PeriodData / BarContext。
"""

import queue
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, Generic, TypeVar

from loguru import logger

from strategies import Bar, Fill, Signal, State, Strategy

T = TypeVar("T")
from common.constants import (  # noqa: E402
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)
from common.schemas import KlineDataFrame  # noqa: E402
from common.tqsdk_imports import tqsdk  # noqa: E402
from common.typing import check_types  # noqa: E402
from strategies.runtime import SOURCE_PERIOD, BarContext, DataFeed  # noqa: E402

# 周期名称 → tqsdk duration 秒数映射
_PERIOD_MAP: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "d": 86400,
}


def _to_datetime(raw_dt: int) -> datetime:
    """将 tqsdk kline_serial 的 datetime 转为 Python datetime

    tqsdk 文档:
      datetime 列为自 unix epoch 以来的**纳秒**数 (int64)，例如 1501080715000000000。
    参见: TqApi.get_kline_serial 的 Returns 部分。

    注意: 此格式不同于常见的毫秒/秒时间戳，转换时必须除以 1e9。
    """
    return datetime.fromtimestamp(raw_dt / 1_000_000_000)


class TqsdkStrategyBridge(Generic[T]):  # noqa: UP046
    """天勤策略桥接器 — 纯协议转换层

    【调用流程】
      单合约:  bridge = TqsdkStrategyBridge(strategy, state)
                 bridge.run(symbol, auth=..., on_signal=...)

      多合约:  api = tqsdk.TqApi(auth=auth)       # CLI 层创建 1 个连接
                 b1 = TqsdkStrategyBridge(s1, st1, api=api)
                 b2 = TqsdkStrategyBridge(s2, st2, api=api)
                 b1.run(symbol1, ...)               # 共享同 1 个 wait_update 循环
                 b2.run(symbol2, ...)

    【run() 行为矩阵】(参见 cli/tqsdk-test-plan.md §4.1.2)
      on_signal=None,  web_gui=False  → 终端 live 模式（TargetPosTask 下单）
      on_signal=None,  web_gui=True   → 浏览器 live 模式
      on_signal=fn,   web_gui=False   → 终端 test 模式（回调打印，不下单）
      on_signal=fn,   web_gui=True    → 浏览器 test 模式

    类型参数 T: 策略配置的具体类型，与 Strategy[T] 和 State[T] 保持一致
    """

    def __init__(self, strategy: Strategy[T], state: State[T], api: Any | None = None):
        """初始化桥接器

        Args:
            strategy: 策略实例
            state: 运行时状态容器
            api: 外部注入的 TqApi 实例（多合约场景）。None 则 run() 内部自行创建
        """
        self._strategy: Strategy[T] = strategy
        self._state: State[T] = state
        self.symbol: str = state.symbol

        self.api: Any = api  # 外部注入或 run() 内创建

        # 多周期数据（run() 中初始化）
        self._klines: dict[str, KlineDataFrame] = {}
        self._data_feed: DataFeed | None = None  # 用于指标注册/计算
        self._caught_up: bool = False  # 是否已追上实时数据
        self._api_owned: bool = False  # 是否由本 bridge 创建并负责关闭 API

    @property
    def strategy(self) -> Strategy[T]:
        return self._strategy

    @property
    def fills(self) -> list[Fill]:
        return list(self._state.fills)

    # ------------------------------------------------------------------ #
    #  公开 API
    # ------------------------------------------------------------------ #

    def _wait_update_with_timeout(self, timeout: float = 5.0) -> bool:
        """带超时的 wait_update()，避免非交易时段永久阻塞。

        tqsdk 的 api.wait_update() 会阻塞到天勤推送新数据为止。
        非交易时段（日盘收盘、夜盘未开）不会有任何新数据，会导致永久阻塞。

        实现方式: 在独立线程中调用 wait_update()，主线程用 queue.get() 等待。

        Args:
            timeout: 超时秒数（默认 5 秒）

        Returns:
            True: wait_update 正常返回（有新数据）
            False: 超时无新数据（非交易时段）
        """
        result_queue: queue.Queue[bool] = queue.Queue(maxsize=1)

        def _worker() -> None:
            try:
                self.api.wait_update()
                result_queue.put(True)
            except Exception:
                result_queue.put(False)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        try:
            return result_queue.get(timeout=timeout)
        except queue.Empty:
            return False

    # ──────────────────────────────────────────────────
    #  阶段 1: API 管理
    # ──────────────────────────────────────────────────

    def _ensure_api_ready(
        self,
        account: Any | None,
        auth: Any | None,
        web_gui: bool,
    ) -> bool:
        """确保 tqsdk API 可用 — 外部已注入则直接返回 True，否则自行创建

        Returns:
            True: API 可用，可以继续后续流程
            False: tqsdk 模块未安装，流程终止
        """
        if not tqsdk.ensure():
            logger.error("天勤量化API未安装")
            return False
        if self.api is None:
            self.api = tqsdk.TqApi(account=account, auth=auth, web_gui=web_gui)
            self._api_owned = True
        return True

    # ──────────────────────────────────────────────────
    #  阶段 2: 初始化（订阅 → 等待历史 → 加载 → 预计算）
    # ──────────────────────────────────────────────────

    def _initialize_feed(self, symbol: str) -> None:
        """订阅多周期行情 → 等待历史数据 → 加载到 PeriodData → 预计算指标"""
        logger.info("[init] 订阅多周期 K线...")
        self._subscribe_klines(symbol)
        logger.info("[init] 订阅完成，周期列表={}".format(", ".join(self._klines.keys())))

        self._wait_for_initial_data()
        self._log_initial_klines()
        self._init_period_data()

    def _wait_for_initial_data(self) -> None:
        """等待 tqsdk 推送第一波历史数据（异步填充 kline_serial）"""
        t0 = time.time()
        init_ok = self._wait_update_with_timeout(timeout=10.0)
        elapsed = time.time() - t0
        if init_ok:
            logger.info(f"[init] wait_update 完成，耗时 {elapsed:.2f}s")
            return
        total_rows = sum(len(kl) for kl in self._klines.values())
        logger.warning(
            f"[init] wait_update 超时 {elapsed:.1f}s（非交易时段无行情推送），"
            f"已获取 {total_rows} 根历史K线，继续初始化..."
        )

    def _log_initial_klines(self) -> None:
        """打印各周期的 K 线数量和时间范围（调试信息）"""
        for pn, klines in self._klines.items():
            rows = len(klines)
            logger.info(f"[init]   {pn}: {rows} 根K线")
            if rows > 0:
                first_ts = int(klines.iloc[0]["datetime"])
                last_ts = int(klines.iloc[-1]["datetime"])
                logger.info(
                    "[init]     时间范围: {} ~ {}".format(
                        datetime.fromtimestamp(first_ts / 1_000_000_000).strftime("%Y-%m-%d %H:%M"),
                        datetime.fromtimestamp(last_ts / 1_000_000_000).strftime("%Y-%m-%d %H:%M"),
                    )
                )

    # ──────────────────────────────────────────────────
    #  阶段 3: 主循环
    # ──────────────────────────────────────────────────

    def _run_event_loop(
        self,
        symbol: str,
        on_signal: Callable[[Signal, float], None] | None,
        web_gui: bool = False,
    ) -> None:
        """主事件循环 — 驱动多周期 K 线 → 策略 → 信号分发

        Args:
            symbol: 合约代码
            on_signal: 信号处理函数。None → 创建 TargetPosTask 自动下单（live）
            web_gui: 是否启用浏览器可视化（仅用于日志提示）
        """
        # 仅 live 模式创建下单任务（命令即安全边界）
        target_pos = None
        if on_signal is None:
            target_pos = tqsdk.TargetPosTask(self.api, symbol)

        # 主循环只处理 INIT 之后新增的 bars
        prev_lens = {name: len(kl) for name, kl in self._klines.items()}
        suffix = "（浏览器可视化已开启）" if web_gui else ""
        logger.info(f"开始运行策略: {symbol}，按Ctrl+C停止{suffix}")

        no_data_count = 0
        while True:
            if not self._wait_update_with_timeout(timeout=3.0):
                no_data_count += 1
                if no_data_count % 20 == 0:
                    logger.info(f"[run] 等待行情中... 已等待 {no_data_count * 3:.0f}s 无新数据（非交易时段）")
                time.sleep(1.0)
                continue
            no_data_count = 0
            self._dispatch_new_bars(prev_lens, on_signal, target_pos)

    def _dispatch_new_bars(
        self,
        prev_lens: dict[str, int],
        on_signal: Callable[[Signal, float], None] | None,
        target_pos: Any,
    ) -> None:
        """只处理源周期的新增 K 线，驱动策略 + 分发信号

        聚合模式下只有源周期数据，高周期由 DataFeed 自动聚合。
        """
        source_period = SOURCE_PERIOD
        klines = self._klines.get(source_period)
        if klines is None:
            return
        if not self.api.is_changing(klines):
            return
        current_len = len(klines)
        if not self._caught_up and current_len > prev_lens.get(source_period, 0):
            self._caught_up = True
            self._log_indicator_snapshot("追上实时数据")
        for i in range(prev_lens.get(source_period, 0), current_len):
            signal = self._on_bar_1m(klines=klines, idx=i)
            if signal.action:
                close_price = float(klines.close.iloc[i])
                if on_signal:
                    on_signal(signal, close_price)
                elif target_pos:
                    self._execute_order(target_pos, signal, close_price)
        prev_lens[source_period] = current_len

    # ──────────────────────────────────────────────────
    #  公开入口：组合以上三个阶段
    # ──────────────────────────────────────────────────

    def run(
        self,
        symbol: str,
        account: Any | None = None,
        auth: Any | None = None,
        on_signal: Callable[[Signal, float], None] | None = None,
        web_gui: bool = False,
    ) -> None:
        """唯一入口 — 订阅行情 → 驱动策略 → 信号回调或 TargetPosTask 下单

        Args:
            symbol: 合约代码 (e.g. SHFE.rb2509)
            account: tqsdk 账户对象。由 CLI 层根据配置构造:
                - TqSim()     → 本地模拟
                - TqKq()      → 快期模拟盘
                - TqAccount(...) → 实盘账户
            auth: 天勤认证 TqAuth(key, secret)。None 则用 guest
            on_signal: 信号回调。None → bridge 内部 TargetPosTask 自动下单（live）
            web_gui: 是否启用浏览器可视化

        行为矩阵（参见 cli/tqsdk-test-plan.md §4.1.2）:
          on_signal=None, web_gui=False → 终端 live 模式
          on_signal=fn,   web_gui=False → 终端 test 模式（回调打印，不下单）
        """
        self._api_owned = False
        self.symbol = symbol

        if not self._ensure_api_ready(account, auth, web_gui):
            return

        try:
            self._initialize_feed(symbol)
            self._run_event_loop(symbol, on_signal, web_gui)
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except tqsdk.BacktestFinished:
            # 回测模式下 wait_update() 自然抛出，向上传播给调用方处理
            raise
        except Exception as e:
            logger.exception(f"策略运行错误: {e}")
        finally:
            if self._api_owned and self.api:
                self.api.close()
            fills_count = len(self._state.fills)
            sells = len([f for f in self._state.fills if f.action == TRADE_ACTION_SELL])
            logger.debug(f"策略停止: fills={fills_count} sells={sells}")

    # ------------------------------------------------------------------ #
    #  内部方法：数据初始化
    # ------------------------------------------------------------------ #

    def _subscribe_klines(self, symbol: str) -> None:
        """根据策略 data_requirements 只订阅源周期 kline_serial

        高周期由 DataFeed 内部聚合生成，无需从网络订阅。
        """
        # 只订阅源周期（1m）数据
        self._klines[SOURCE_PERIOD] = self.api.get_kline_serial(self.symbol, 60)

    def _klines_to_dataframe(self, klines: KlineDataFrame) -> Any:
        """将 tqsdk kline_serial DataFrame 转换为 PeriodData 可加载的格式

        - datetime: int64 纳秒 → Python datetime
        - 设置 datetime 为索引
        """
        df = klines.copy()
        df["datetime"] = df["datetime"].apply(_to_datetime)
        df.set_index("datetime", inplace=True)
        return df

    def _init_period_data(self) -> None:
        """用 tqsdk 源周期 kline_serial 初始化 DataFeed + 周期 + 预计算指标

        高周期由 DataFeed 内部聚合生成，不需要从网络订阅，也不需要外部手动配置聚合。
        策略声明了 data_requirements → DataFeed.apply_requirements 一步搞定。
        无声明 → 退化为单源周期无指标。

        前置条件: _subscribe_klines() + _wait_for_initial_data() 已执行
        """
        reqs = self._strategy.data_requirements(self._state.strategy_config)
        has_indicators = bool(reqs and reqs.indicators)

        # 1. 创建 DataFeed 并应用需求（注册周期、配置聚合、注册指标 一步到位）
        self._data_feed = DataFeed(symbol=self.symbol)
        if reqs:
            self._data_feed.apply_requirements(reqs)
        else:
            self._data_feed.register_period(SOURCE_PERIOD)

        logger.info("[init] DataFeed: 已配置需求，高周期将由内部聚合生成")

        # 2. 加载源周期数据（kline_serial → PeriodData）
        total_loaded = 0
        source_period = SOURCE_PERIOD
        if source_period in self._klines:
            klines = self._klines[source_period]
            if len(klines) > 0:
                pd_obj = self._data_feed.get_period(source_period)
                if pd_obj is not None:
                    df = self._klines_to_dataframe(klines)
                    pd_obj.load_df(df)
                    total_loaded += len(df)
                    logger.info(
                        f"[init]   {source_period}: 加载 {len(df)} 根K线，最新={df.index[-1].strftime('%Y-%m-%d %H:%M')}"
                    )
        logger.info(f"[init]   共加载 {total_loaded} 根K线到 PeriodData")

        # 3. 预计算指标（与回测路径一致，全量计算一次）
        if has_indicators:
            t0 = time.time()
            self._data_feed.calculate_all()
            logger.info(f"[init]   指标计算完成，耗时 {time.time() - t0:.3f}s")
            self._log_indicator_snapshot("初始历史数据")

    def _log_indicator_snapshot(self, label: str) -> None:
        """打印当前所有周期的指标截面信息（最新一行各指标值）

        日志格式示例:
          2026-06-08 20:07:13 | 指标截面 [初始历史数据] | symbol=SHFE.rb2509
            period=1m rows=845 latest=2026-06-08 14:59 | sma_10=3688.50 macd_12_26_9=12.34 kdj_3_3_9=45.67
            period=5m rows=845 latest=2026-06-08 14:55 | sma_10=3689.00 macd_12_26_9=11.22 kdj_3_3_9=44.56
            period=15m rows=840 latest=2026-06-08 14:45 | sma_40=3690.12 atr_14=8.50

        :param label: 截面标记，如 "初始历史数据" 或 "追上实时数据"
        """
        if self._data_feed is None:
            return
        for period_name in self._data_feed.get_period_names():
            pd_obj = self._data_feed.get_period(period_name)
            if pd_obj is None or pd_obj.length == 0:
                continue
            latest_time = pd_obj.latest_time
            latest_time_str = latest_time.strftime("%Y-%m-%d %H:%M") if latest_time else "N/A"
            ind_cols = self._data_feed.get_indicator_names(period_name)
            ind_parts = []
            for c in sorted(ind_cols):
                val = pd_obj.get_indicator(c, -1)
                if val is not None:
                    ind_parts.append(f"{c}={val:.4f}")
            ind_str = " ".join(ind_parts) if ind_parts else "(无指标)"
            logger.info(
                "指标截面 [{}] | symbol={} period={} rows={} latest={} | {}",
                label,
                self.symbol,
                period_name,
                pd_obj.length,
                latest_time_str,
                ind_str,
            )

    # ------------------------------------------------------------------ #
    #  内部方法：K线处理 & 策略驱动
    # ------------------------------------------------------------------ #

    # ──────────────────────────────────────────────────
    #  K 线 & 指标处理工具
    # ──────────────────────────────────────────────────

    def _kline_to_bar(self, klines: KlineDataFrame, idx: int) -> Bar:
        """从 tqsdk kline_serial 指定行构造标准 Bar 对象

        与回测路径的 Bar 构造保持一致。
        """
        return Bar(
            symbol=self.symbol,
            datetime=_to_datetime(klines.datetime.iloc[idx]),
            open=float(klines.open.iloc[idx]),
            high=float(klines.high.iloc[idx]),
            low=float(klines.low.iloc[idx]),
            close=float(klines.close.iloc[idx]),
            volume=float(klines.volume.iloc[idx]),
        )

    def _build_multi_context(self, current_bar: Bar) -> dict[str, Any]:
        """构造多周期 PeriodDataView 字典（供 strategy.on_bar 使用）

        通过 DataFeed.get_data() 公共 API 获取各周期视图，天然防偷看。
        """
        if self._data_feed is None:
            return {}
        reqs = self._strategy.data_requirements(self._state.strategy_config)
        multi: dict[str, Any] = {}
        for period_name in self._klines:
            pd_obj = self._data_feed.get_period(period_name)
            if pd_obj is None or pd_obj.length == 0:
                continue
            lookback = (
                reqs.periods[period_name].lookback_bars if reqs and period_name in reqs.periods else pd_obj.length
            )
            view = self._data_feed.get_data(period_name, current_bar.datetime, lookback)
            if view is not None:
                multi[period_name] = view
        return multi

    def _update_period_and_recalc(self, bar: Bar) -> None:
        """喂入一根源周期 K 线到 DataFeed，高周期自动聚合更新

        聚合由 DataFeed 内部完成，调用方不用关心哪些周期需要聚合。
        """
        if self._data_feed is None:
            return
        self._data_feed.feed_bar(bar)

    # ------------------------------------------------------------------ #
    #  内部方法：K线处理 & 策略驱动
    # ------------------------------------------------------------------ #

    @check_types
    def _on_bar_1m(self, klines: KlineDataFrame, idx: int) -> Signal:
        """从源周期 kline_serial 构造完整 BarContext 并驱动策略

        流程: 源周期 kline → Bar → 喂入 DataFeed → 自动聚合高周期 → 构造 context → on_bar
        """
        bar = self._kline_to_bar(klines, idx)
        self._update_period_and_recalc(bar)
        multi = self._build_multi_context(bar)

        ctx = BarContext(symbol=self.symbol, bar=bar, multi=multi, events=[])
        self._update_peak_prices(bar)
        return self._strategy.on_bar(self._state, ctx)

    def _execute_order(self, target_pos: Any, signal: Signal, price: float) -> None:
        """通过 TargetPosTask 执行下单（仅 live 模式调用）

        安全边界: 此方法仅在 on_signal=None 时被调用，
        即只有 live 命令的代码路径会到达这里。
        """
        if signal.action == TRADE_ACTION_BUY:
            target_pos.set_target_volume(signal.volume)
            self.notify_fill(signal, price)
        elif signal.action == TRADE_ACTION_SELL:
            target_pos.set_target_volume(0)
            self.notify_fill(signal, price)

    # ------------------------------------------------------------------ #
    #  保留的旧方法（无状态 on_bar / notify_fill / peak 价格更新）
    # ------------------------------------------------------------------ #

    @check_types
    def on_bar(self, kline_data: KlineDataFrame, idx: int = -1) -> Signal:
        """处理单根 K 线（无多周期、无指标计算的简化版）

        主要用于简单测试场景。生产环境请使用 run()。
        """
        if kline_data.empty:
            return Signal()
        bar = self._kline_to_bar(kline_data, idx)
        ctx = BarContext(symbol=self.symbol, bar=bar, multi={}, events=[])
        self._update_peak_prices(bar)
        return self._strategy.on_bar(self._state, ctx)

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
                direction=TRADE_DIRECTION_LONG,
                entry_price=fill_price,
                volume=signal.volume,
                highest_price=fill_price,
                lowest_price=fill_price,
            )
        elif signal.action == TRADE_ACTION_SELL:
            self._state.position = StrategyPosition()

        self._strategy.on_fill(fill)
