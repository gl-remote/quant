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
from typing import Any, Generic, TypeVar, cast

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
from common.types import PositionDirection  # noqa: E402
from common.typing import check_types  # noqa: E402
from strategies.runtime import BarContext, DataFeed  # noqa: E402
from strategies.runtime.period import PeriodDataView  # noqa: E402

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
                - TqSim()     → 本地模拟，默认 1000 万虚拟资金
                - TqKq()      → 快期模拟盘
                - TqAccount(...) → 实盘账户
                None 则不传（等于 TqSim 默认行为，但建议显式传入）
            auth: 天勤认证 TqAuth(key, secret)。None 则用 guest
            on_signal: 信号回调。
                - None     → bridge 内部创建 TargetPosTask 自动下单（live 模式）
                - callable → 由调用方处理（test 模式只打印不下单）
            web_gui: 是否启用浏览器可视化
        """
        if not tqsdk.ensure():
            logger.error("天勤量化API未安装")
            return

        # ── API 管理：优先用外部注入的，否则自己创建 ──
        close_on_exit = False
        if self.api is None:
            self.api = tqsdk.TqApi(account=account, auth=auth, web_gui=web_gui)
            close_on_exit = True

        try:
            self.symbol = symbol

            # === 多周期订阅 ===
            logger.info("[init] 订阅多周期 K线 (1m/5m/15m)...")
            self._subscribe_klines(symbol)
            logger.info("[init] 订阅完成，周期列表={}".format(", ".join(self._klines.keys())))

            # === 等待初始历史数据（tqsdk kline_serial 是异步填充）
            # 用带超时的 wait_update，避免非交易时段永久阻塞
            t0 = time.time()
            init_ok = self._wait_update_with_timeout(timeout=10.0)
            elapsed = time.time() - t0
            if init_ok:
                logger.info(f"[init] wait_update 完成，耗时 {elapsed:.2f}s")
            else:
                # 超时但仍可能有历史数据（get_kline_serial 已同步填充了历史），检查一下
                total_rows = sum(len(kl) for kl in self._klines.values())
                logger.warning(
                    f"[init] wait_update 超时 {elapsed:.1f}s（非交易时段无行情推送），"
                    f"已获取 {total_rows} 根历史K线，继续初始化..."
                )

            # 检查各周期数据是否都有内容
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

            # === 批量加载历史数据 + 预计算指标 ===
            self._init_period_data()

            # === 下单任务（仅 live 模式创建）
            target_pos = None
            if on_signal is None:
                target_pos = tqsdk.TargetPosTask(self.api, symbol)

            # prev_lens 基于加载后的真实长度 — 主循环只处理 INIT 之后的 NEW bars
            prev_lens = {name: len(kl) for name, kl in self._klines.items()}
            log_msg = f"开始运行策略: {symbol}，按Ctrl+C停止"
            if web_gui:
                log_msg += "（浏览器可视化已开启）"
            logger.info(log_msg)

            # === 主循环 ===
            no_data_count = 0
            while True:
                if not self._wait_update_with_timeout(timeout=3.0):
                    # 非交易时段无新数据：缓一缓再检查
                    no_data_count += 1
                    if no_data_count % 20 == 0:
                        logger.info(f"[run] 等待行情中... 已等待 {no_data_count * 3:.0f}s 无新数据（非交易时段）")
                    time.sleep(1.0)
                    continue
                no_data_count = 0
                for period_name, klines in self._klines.items():
                    if self.api.is_changing(klines):
                        current_len = len(klines)
                        # 首次收到实时数据时打印截面日志
                        if not self._caught_up and current_len > prev_lens.get(period_name, 0):
                            self._caught_up = True
                            self._log_indicator_snapshot("追上实时数据")
                        for i in range(prev_lens[period_name], current_len):
                            signal = self._on_bar_multi(
                                klines=klines,
                                idx=i,
                                main_period=period_name,
                            )
                            if signal.action:
                                close_price = float(klines.close.iloc[i])
                                # 分叉点：test 回调 vs live 下单
                                if on_signal:
                                    on_signal(signal, close_price)
                                elif target_pos:
                                    self._execute_order(target_pos, signal, close_price)
                        prev_lens[period_name] = current_len

        except KeyboardInterrupt:
            logger.info("策略已停止")
        except tqsdk.BacktestFinished:
            # 回测模式下 wait_update() 自然抛出，向上传播给调用方处理
            raise
        except Exception as e:
            logger.exception(f"策略运行错误: {e}")
        finally:
            if close_on_exit and self.api:
                self.api.close()
            fills_count = len(self._state.fills)
            sells = len([f for f in self._state.fills if f.action == TRADE_ACTION_SELL])
            logger.debug(f"策略停止: fills={fills_count} sells={sells}")

    # ------------------------------------------------------------------ #
    #  内部方法：数据初始化
    # ------------------------------------------------------------------ #

    def _subscribe_klines(self, symbol: str) -> None:
        """根据策略 data_requirements 订阅多周期 kline_serial

        设计决策（参见 cli/tqsdk-test-plan.md §8 决策项1）:
          使用 PeriodData 结构 + 复用回测指标计算逻辑，
          不需要自定义适配器类（TqSdkPeriodView 方案已废弃）。
        """
        reqs = self._strategy.data_requirements(self._state.strategy_config)
        if reqs:
            for period_name in reqs.periods:
                duration = _PERIOD_MAP.get(period_name, 60)
                self._klines[period_name] = self.api.get_kline_serial(symbol, duration)
        else:
            # 策略未声明需求时默认订阅 1 分钟线
            self._klines["1m"] = self.api.get_kline_serial(symbol, 60)

    def _init_period_data(self) -> None:
        """用 tqsdk kline_serial DataFrame 初始化 DataFeed + PeriodData

        复用 strategies.runtime.DataFeed 和已有的指标注册/计算函数，
        与回测路径完全相同的数据结构和计算逻辑。

        前置条件: run() 已调用 _subscribe_klines 且 api.wait_update() 已执行，
                 确保各周期的 kline_serial DataFrame 已填充满历史数据。
        """
        reqs = self._strategy.data_requirements(self._state.strategy_config)

        # 创建 DataFeed 作为指标管理容器（不涉及文件 I/O）
        self._data_feed = DataFeed(symbol=self.symbol)

        if reqs:
            # 1. 注册策略声明的所有周期和指标
            period_count = 0
            ind_count = 0
            for pn in reqs.periods:
                self._data_feed.register_period(pn)
                period_count += 1
            if reqs.indicators:
                for pn, ind_list in reqs.indicators.items():
                    for ind_req in ind_list:
                        self._data_feed.register_indicator(pn, ind_req.name, **ind_req.params)
                        ind_count += 1
            logger.info(f"[init] DataFeed: 注册 {period_count} 个周期, {ind_count} 个指标")

            # 2. 将每个周期的 kline_serial DataFrame 批量加载到 PeriodData
            total_loaded = 0
            for period_name, klines in self._klines.items():
                pd_obj = self._data_feed.get_period(period_name)
                if pd_obj is None:
                    logger.warning(f"[init]   {period_name}: PeriodData 未注册，跳过")
                    continue
                if len(klines) == 0:
                    logger.warning(f"[init]   {period_name}: kline 为空（tqsdk 未返回数据），跳过")
                    continue
                # 转换 datetime: tqsdk 是 int64 纳秒 → Python datetime
                df = klines.copy()
                df["datetime"] = df["datetime"].apply(_to_datetime)
                df.set_index("datetime", inplace=True)
                pd_obj.load_df(df)
                logger.info(
                    f"[init]   {period_name}: 加载 {len(df)} 根K线，最新={df.index[-1].strftime('%Y-%m-%d %H:%M')}"
                )
                total_loaded += len(df)
            logger.info(f"[init]   共加载 {total_loaded} 根K线到 PeriodData")

            # 3. 一次性预计算所有周期所有指标（与回测路径一致）
            t0 = time.time()
            self._data_feed.calculate_all()
            logger.info(f"[init]   指标计算完成，耗时 {time.time() - t0:.3f}s")

            # 4. 打印指标截面（便于核对数据完整性）
            self._log_indicator_snapshot("初始历史数据")
        else:
            # 策略未声明 data_requirements 时退化为单周期最简模式
            if "1m" in self._klines and len(self._klines["1m"]) > 0:
                self._data_feed.register_period("1m")
                pd_obj = self._data_feed.get_period("1m")
                if pd_obj is None:
                    logger.warning("[init] 1m PeriodData 注册后获取失败")
                    return
                df = self._klines["1m"].copy()
                df["datetime"] = df["datetime"].apply(_to_datetime)
                df.set_index("datetime", inplace=True)
                pd_obj.load_df(df)
                logger.info(f"[init] 已加载 1m 周期 {len(self._klines['1m'])} 根K线（无指标声明）")

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
        # 从 DataFeed 注册的周期中取数据（而非 _klines），确保只迭代有数据的周期
        periods_to_log = []
        if hasattr(self._data_feed, "_periods"):
            periods_to_log = sorted(self._data_feed._periods.keys())  # pyright: ignore[reportPrivateUsage]
        else:
            periods_to_log = sorted(self._klines.keys())
        for period_name in periods_to_log:
            pd_obj = self._data_feed.get_period(period_name)
            if pd_obj is None or pd_obj.length == 0:
                continue
            latest_time = pd_obj.latest_time
            latest_time_str = latest_time.strftime("%Y-%m-%d %H:%M") if latest_time else "N/A"
            # 收集指标列的最新值（排除 OHLCV 和 tqsdk 元数据列）
            skip_cols = frozenset(
                {"open", "high", "low", "close", "volume", "id", "symbol", "duration", "open_oi", "close_oi"}
            )
            ind_cols = [c for c in pd_obj._df.columns if c not in skip_cols]  # pyright: ignore[reportPrivateUsage]
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

    @check_types
    def _on_bar_multi(self, klines: KlineDataFrame, idx: int, main_period: str) -> Signal:
        """从多周期 kline_serial 构造完整 BarContext 并驱动策略

        与回测路径 VnpyBacktestBridge._build_ctx() 对称：
          回测: DataFeed.get_data() → PeriodDataView → BarContext
          实时: PeriodData.append_bar() + 重算最新行 → view → BarContext
        """
        bar = Bar(
            symbol=self.symbol,
            datetime=_to_datetime(klines.datetime.iloc[idx]),
            open=float(klines.open.iloc[idx]),
            high=float(klines.high.iloc[idx]),
            low=float(klines.low.iloc[idx]),
            close=float(klines.close.iloc[idx]),
            volume=float(klines.volume.iloc[idx]),
        )

        # 更新主周期的 PeriodData 并重算指标
        # append_bar 会清除指标缓存，calculate_all 全量重算（实时数据量小，性能可接受）
        if self._data_feed is not None:
            main_pd = self._data_feed.get_period(main_period)
            if main_pd is not None:
                main_pd.append_bar(bar)
                self._data_feed.calculate_period(main_period)

        # 构造 multi 字典：PeriodDataView（策略熟悉的接口）
        multi: dict[str, Any] = {}
        if self._data_feed is not None:
            for period_name in self._klines:
                pd_obj = self._data_feed.get_period(period_name)
                if pd_obj is not None and pd_obj.length > 0:
                    # 与 VnpyBacktestBridge._build_ctx() 对称：构造 PeriodDataView
                    pdf = pd_obj._df  # pyright: ignore[reportPrivateUsage]
                    end_idx = len(pdf) - 1
                    multi[period_name] = PeriodDataView(
                        df_ref=pdf,
                        events_ref=None,
                        start_idx=0,
                        end_idx=end_idx,
                        current_time=pdf.index[-1],
                        period=period_name,
                    )

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
        """处理天勤K线数据指定索引行，返回标准化 Signal（无状态版本）

        无多周期数据、无指标计算，仅做基础 DataFrame → Bar → Signal 转换。
        主要用于简单测试场景，生产环境请使用 run() 方法。
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
                direction=cast(PositionDirection, TRADE_DIRECTION_LONG),
                entry_price=fill_price,
                volume=signal.volume,
                highest_price=fill_price,
                lowest_price=fill_price,
            )
        elif signal.action == TRADE_ACTION_SELL:
            self._state.position = StrategyPosition()

        self._strategy.on_fill(fill)
