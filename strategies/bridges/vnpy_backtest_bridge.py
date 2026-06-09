"""vn.py 桥接器模块

将 Strategy 接口桥接到 vnpy CtaTemplate，是整个架构的核心适配层。

重构背景:
- 旧架构：Bridge 只做简单的数据转换，Strategy 自己管理状态
- 新架构：Bridge 集成 runtime 数据管理架构，统一管理 State

核心职责:
  1. 集成 runtime 数据管理架构 (DataFeed setup, 数据加载, BarContext 构造)
  2. vnpy BarData → 标准 Bar 的数据转换
  3. 调用 strategy.on_bar(state, ctx) 获取 Signal
  4. Signal → vnpy self.buy()/self.sell() 的下单翻译
  5. 通过 on_trade 同步成交状态到 State，回调 strategy.on_fill

设计说明:
- strategy 和 state 由 backtest_engine 通过 _InjectedStrategy 在构造后注入
- vn.py 为强制依赖
- 采用注入模式是因为 vn.py 回测引擎要求传入策略类而非实例，引擎内部会自行创建对象实例
"""

import json
import os
from datetime import datetime
from typing import Any, cast

import pandas as pd
from loguru import logger
from vnpy_ctastrategy import CtaTemplate

from common.constants import (
    DIRECTION_MAP,
    OFFSET_MAP,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
    TRADE_OFFSET_OPEN,
)
from common.types import PositionDirection, TradeAction
from data.manager import DataManager
from strategies import Bar, Fill, Signal, State, Strategy, UninitializedStrategy
from strategies.core.types import StrategyPosition
from strategies.runtime import DataFeed, DataRequirements
from strategies.runtime.cache import get_cached_feed, set_cached_feed
from strategies.runtime.period import PeriodDataView
from strategies.runtime.requirements import BarContext


class VnpyBacktestBridge(CtaTemplate):
    """vn.py 策略桥接器 — 集成 runtime 数据管理架构

    【设计理念】
    Bridge 是连接 vnpy 引擎和我们 Strategy 之间的适配层：
    - 向下：适配 vnpy 的 CtaTemplate 接口
    - 向上：适配我们的 Strategy 接口
    - 中间：管理 State 和 DataFeed

    【核心持有】
    - _core: Strategy 实例，纯决策逻辑
    - _state: State 实例，所有运行时数据
    - _data_feed: DataFeed 实例，行情数据管理
    - _requirements: DataRequirements，缓存的数据需求

    【状态同步】
    - vnpy 的 pos: vnpy 引擎的持仓（只读，用于下单检查）
    - _state.position: 我们的持仓（由 Bridge 在 on_trade 中更新）
    - 两者数据同源，但用途不同
    """

    author = "Quant System"
    parameters = ["price_tick"]
    variables = ["pos", "entry_price"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化桥接器 — 构造空的 _core 和 _state

        【注入模式】
        因为 vnpy 回测引擎要求传入策略类而非实例，引擎内部会自行创建对象。
        所以我们在 __init__ 中构造空的占位符，然后由外部（_InjectedStrategy）注入真实的 _core 和 _state。

        【占位符说明】
        - _core: 初始化为 UninitializedStrategy，调用时会报错提示未注入
        - _state: 初始化为空的 State，参数由外部注入
        """
        super().__init__(*args, **kwargs)
        self._core: Strategy[Any] = UninitializedStrategy()
        self._state: State[Any] = State(symbol="", period="", strategy_config=None)
        self._requirements: DataRequirements | None = None
        self._data_feed: Any = None
        self._ctx_cache: dict[pd.Timestamp, BarContext] = {}
        self.entry_price: float = 0.0

    def is_initialized(self) -> bool:
        """检查策略是否已初始化（注入）

        :return: 是否已注入真实的 Strategy
        """
        return self._core.name != "_uninitialized"

    # ── vnpy 生命周期 ──────────────────────────────────────

    def on_init(self) -> None:
        """vnpy 初始化回调 — 预加载数据、预计算指标、预构造上下文

        on_bar 中只做 O(1) 的 dict 查找，零重算、零时间戳搜索。
        """
        if not self.is_initialized():
            logger.error(f"[{self.strategy_name}] strategy 未注入，初始化跳过")
            return

        logger.debug(f"[{self.strategy_name}] 桥接器初始化: {self._core.name}")

        self._requirements = self._core.data_requirements(self._state.strategy_config)
        if self._requirements is None:
            self.write_log(f"策略初始化: {self._core.name}")
            return

        self._data_feed = self._setup_data_feed()
        self._build_ctx_cache()

        self.write_log(f"策略初始化: {self._core.name}")

    def on_start(self) -> None:
        """vnpy 启动回调"""
        self._log_data_feed_summary("策略启动 -- 使用的数据")
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """vnpy 停止回调 — 记录策略停止时的统计信息"""
        fills_count = len(self._state.fills)
        sells = len([f for f in self._state.fills if f.action == TRADE_ACTION_SELL])
        buys = fills_count - sells
        logger.debug(f"[{self.strategy_name}] 策略停止 | fills={fills_count} buys={buys} sells={sells}")
        self.write_log(f"策略停止: fills={fills_count} buys={buys} sells={sells}")

    def _log_data_feed_summary(self, label: str = "") -> None:
        """输出 DataFeed 内容摘要到日志文件（前端运行日志 Tab 可查看）

        列出每个周期的：行数、时间区间、已注册指标、已计算指标列。

        :param label: 日志标签，如 "数据加载完成（计算前）"
        """
        if self._data_feed is None:
            return
        rid = self._state.run_id
        btid = self._state.backtest_id
        for pn in self._data_feed._periods:  # pyright: ignore[reportPrivateUsage]
            pd_obj = self._data_feed.get_period(pn)
            if pd_obj is None:
                continue
            df = pd_obj._df  # pyright: ignore[reportPrivateUsage]
            if len(df) == 0:
                continue
            # 已注册指标配置
            indicators = self._data_feed._registered_indicators.get(pn, [])  # pyright: ignore[reportPrivateUsage]
            ind_names = [f"{n}({','.join(f'{k}={v}' for k, v in p.items())})" for n, p in indicators]
            # 已计算完成的指标列（实际在 _df 中的列名）
            ohlcv = {"open", "high", "low", "close", "volume"}
            calc_cols = [c for c in df.columns if c not in ohlcv]
            logger.debug(
                f"[run={rid} bt={btid}] [{self.strategy_name}] "
                f"{label + ' ' if label else ''}"
                f"period={pn} rows={len(df)} "
                f"range={df.index[0]}~{df.index[-1]} "
                f"registered=[{', '.join(ind_names) if ind_names else '无'}] "
                f"calculated_columns={calc_cols}"
            )

    # ── DataFeed 初始化 ────────────────────────────────────

    def _setup_data_feed(self) -> DataFeed:
        """统一入口：加载 → 校验 → 差量合并 → 增量计算

        只做缺失的工作：
        - 内存缓存命中 → 零 I/O 返回
        - feeds 不存在 → 全量加载 + 全量计算
        - 数据过期 → 重加载数据 + 重算指标
        - 加周期/加指标 → 只加载新周期 + 只算新指标
        - 完全命中磁盘缓存 → 零开销返回
        """
        assert self._requirements is not None  # on_init 已判空

        feeds_dir = f"output/feeds/{self._state.symbol}"
        main_period = self._state.period

        # 0. 查源数据新鲜度，尝试内存缓存（零 I/O 路径）
        dm = DataManager()
        meta = dm.store.get_metadata(self._state.symbol, interval=main_period)
        if meta and meta.get("min_dt") and meta.get("max_dt"):
            cached = get_cached_feed(self._state.symbol, str(meta["min_dt"]), str(meta["max_dt"]))
            if cached is not None:
                logger.debug("[{}] 内存缓存命中，跳过 parquet I/O", self.strategy_name)
                return cached

        # 1. 加载已有 feeds 或创建空 DataFeed，同时检查数据是否过期
        feed, data_stale = self._assess_feed(feeds_dir)

        # 2. 数据过期则全量重加载所有周期数据
        if data_stale:
            self._register_requirements(feed)
            self._load_periods(feed)
            self._log_data_feed_summary("数据加载完成（计算前）")
            feed.calculate_all()
            self._log_data_feed_summary("指标计算完成（计算后）")
            feed.to_feeds(feeds_dir)
            self._cache_feed(feed, meta, feeds_dir)
            return feed

        # 3. 数据不过期 → 增量合并缺失的周期和指标
        changed = self._merge_missing_requirements(feed)

        if changed:
            self._log_data_feed_summary("增量合并完成（计算前）")
            feed.calculate_all()
            self._log_data_feed_summary("指标计算完成（计算后）")
            feed.to_feeds(feeds_dir)
            logger.debug("[{}] feeds 已增量更新", self.strategy_name)
        else:
            self._log_data_feed_summary("feeds 命中，跳过计算")
            logger.debug("[{}] feeds 命中，跳过指标计算", self.strategy_name)

        self._cache_feed(feed, meta, feeds_dir)
        return feed

    def _cache_feed(self, feed: DataFeed, meta: Any, feeds_dir: str) -> None:
        """将 DataFeed 写入内存缓存

        :param feed: DataFeed 实例
        :param meta: ExportMetadata 返回结果（含 min_dt/max_dt），None 时尝试从 parquet 恢复
        """
        if meta and meta.get("min_dt") and meta.get("max_dt"):
            set_cached_feed(feed.symbol, feed, meta["min_dt"], meta["max_dt"])
            return
        # 无 meta 时尝试从 parquet _meta.json 中恢复时间范围
        meta_path = os.path.join(feeds_dir, "_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    pm = json.load(f)
                periods = pm.get("periods", [])
                if periods:
                    first_pd = feed.get_period(periods[0])
                    if first_pd is not None and first_pd.length > 0:
                        idx = first_pd._df.index  # pyright: ignore[reportPrivateUsage]
                        min_dt = str(idx[0].date())
                        max_dt = str(idx[-1].date())
                        set_cached_feed(feed.symbol, feed, min_dt, max_dt)
            except Exception:
                pass

    def _assess_feed(self, feeds_dir: str) -> tuple[DataFeed, bool]:
        """加载 feeds 并判断数据是否过期

        :return: (feed, data_stale) — True 表示数据过期需全量重算
        """
        main_period = self._state.period

        if not os.path.isdir(feeds_dir):
            logger.debug("[{}] feeds 目录不存在，全量加载", self.strategy_name)
            return DataFeed(symbol=self._state.symbol), True

        try:
            feed = DataFeed.from_feeds(feeds_dir)
        except Exception as e:
            logger.warning("[{}] feeds 加载失败: {}，全量重算", self.strategy_name, e)
            return DataFeed(symbol=self._state.symbol), True

        # 检查主周期数据是否存在
        main_pd = feed.get_period(main_period)
        if main_pd is None or len(main_pd._df) == 0:  # pyright: ignore[reportPrivateUsage]
            logger.warning("[{}] feeds 主周期为空，全量重算", self.strategy_name)
            return feed, True

        # 从 ExportMetadata 查源数据起止时间（避免读 CSV）
        dm = DataManager()
        meta = dm.store.get_metadata(self._state.symbol, interval=main_period)
        if meta is None or not meta.get("min_dt") or not meta.get("max_dt"):
            logger.warning("[{}] ExportMetadata 缺失，全量重算", self.strategy_name)
            return feed, True

        cache_start = str(pd.DatetimeIndex(main_pd._df.index)[0].date())  # pyright: ignore[reportAttributeAccessIssue,reportPrivateUsage]
        cache_end = str(pd.DatetimeIndex(main_pd._df.index)[-1].date())  # pyright: ignore[reportAttributeAccessIssue,reportPrivateUsage]
        if meta["min_dt"] != cache_start or meta["max_dt"] != cache_end:
            logger.debug(
                "[{}] feeds 过期 (源:{}/{} 缓存:{}/{})",
                self.strategy_name,
                meta["min_dt"],
                meta["max_dt"],
                cache_start,
                cache_end,
            )
            return feed, True

        return feed, False

    def _merge_missing_requirements(self, feed: DataFeed) -> bool:
        """将 feeds 中缺失的周期和指标增量合并进去

        只加载新周期的数据，只注册新指标（不计算，留给 calculate_all），
        已计算过的指标在 calculate_all 中自动跳过。

        :return: 是否有新增
        """
        assert self._requirements is not None  # _setup_data_feed 调用方已判空
        changed = False
        dm = DataManager()

        # 补充缺失周期 + 加载数据
        for pn in self._requirements.periods:
            if pn not in feed._periods:  # pyright: ignore[reportPrivateUsage]
                feed.register_period(pn)
                results = dm.load_kline([self._state.symbol], interval=pn)
                for _symbol, df, _data_src in results:
                    if len(df) > 0:
                        feed.load_history_df(pn, df.set_index("datetime"))
                        logger.debug(
                            "[{}] 增量加载周期: period={} rows={}",
                            self.strategy_name,
                            pn,
                            len(df),
                        )
                changed = True

        # 补充缺失指标（仅注册，不计算）
        for pn, inds in self._requirements.indicators.items():
            cached = {(n, tuple(sorted(p.items()))) for n, p in feed._registered_indicators.get(pn, [])}  # pyright: ignore[reportPrivateUsage]
            for ind in inds:
                key = (ind.name, tuple(sorted(ind.params.items())))
                if key not in cached:
                    feed.register_indicator(pn, ind.name, **ind.params)
                    logger.debug(
                        "[{}] 增量注册指标: period={} indicator={}({})",
                        self.strategy_name,
                        pn,
                        ind.name,
                        ind.params,
                    )
                    changed = True

        return changed

    def _register_requirements(self, data_feed: DataFeed) -> None:
        """将 DataRequirements 中的全部周期和指标注册到 DataFeed"""
        assert self._requirements is not None
        for pn in self._requirements.periods:
            data_feed.register_period(pn)
        for pn, inds in self._requirements.indicators.items():
            for ind in inds:
                data_feed.register_indicator(pn, ind.name, **ind.params)

    def _load_periods(self, data_feed: Any) -> None:
        """从 DataManager 加载所有周期的历史数据（按主周期结束时间对齐）"""
        assert self._requirements is not None  # _setup_data_feed 调用方已判空
        dm = DataManager()
        main_period = self._state.period

        # 先加载主周期，确定结束日期
        main_results = dm.load_kline([self._state.symbol], interval=main_period)
        if not main_results:
            return
        _, main_df, _ = main_results[0]
        if len(main_df) == 0:
            return
        data_feed.load_history_df(main_period, main_df.set_index("datetime"))
        logger.debug(
            "[{}] 加载主周期: period={} rows={}",
            self.strategy_name,
            main_period,
            len(main_df),
        )
        end_date = str(main_df["datetime"].iloc[-1])[:10]

        # 其他周期以主周期结束日期对齐
        for period in self._requirements.periods:
            if period == main_period:
                continue
            results = dm.load_kline([self._state.symbol], interval=period, end_date=end_date)
            for _symbol, df, _data_src in results:
                if len(df) > 0:
                    data_feed.load_history_df(period, df.set_index("datetime"))
                    logger.debug(
                        "[{}] 加载周期: period={} rows={} (end={})",
                        self.strategy_name,
                        period,
                        len(df),
                        end_date,
                    )
                else:
                    logger.warning("[{}] 加载数据为空: period={}", self.strategy_name, period)

    def _build_ctx_cache(self) -> None:
        """预构造所有 BarContext：按主周期时间戳逐条构造，存到 dict

        on_bar 中直接通过 timestamp 做 O(1) 查找。
        """
        assert self._requirements is not None  # on_init 已判空
        main_pd = self._data_feed.get_period(self._state.period)
        if main_pd is None:
            return

        main_df: pd.DataFrame = main_pd._df  # pyright: ignore[reportPrivateUsage]
        for idx in range(len(main_df)):
            ts: pd.Timestamp = main_df.index[idx]  # type: ignore[assignment]
            row = main_df.iloc[idx]
            bar = Bar(
                symbol=self._state.symbol,
                datetime=ts.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            multi: dict[str, PeriodDataView] = {}
            for period, req in self._requirements.periods.items():
                pd_obj = self._data_feed.get_period(period)
                if pd_obj is None:
                    continue
                pdf: pd.DataFrame = pd_obj._df  # pyright: ignore[reportPrivateUsage]
                end_idx = int(pdf.index.get_indexer(pd.Index([ts]), method="ffill")[0])
                if end_idx < 0:
                    end_idx = 0
                start_idx = max(0, end_idx - req.lookback_bars + 1)
                multi[period] = PeriodDataView(
                    df_ref=pdf,
                    events_ref=None,
                    start_idx=start_idx,
                    end_idx=end_idx,
                    current_time=ts,
                    period=period,
                )
            self._ctx_cache[ts] = BarContext(
                symbol=self._state.symbol,
                bar=bar,
                multi=multi,
                events=[],
            )

        logger.debug(
            "[{}] ctx_cache 构造完成: {} 条, range={}~{}",
            self.strategy_name,
            len(self._ctx_cache),
            main_df.index[0] if len(main_df) > 0 else "N/A",
            main_df.index[-1] if len(main_df) > 0 else "N/A",
        )

    # ── vnpy 行情回调 ──────────────────────────────────────

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

    def _log_bar_diagnostics(self, bar_time: pd.Timestamp, signal: Signal, close_price: float) -> None:
        """统一诊断日志 — 有信号逐条打，无信号百条采样

        :param bar_time: K线时间
        :param signal: 策略信号（含 diagnostics）
        :param close_price: 当前收盘价
        """
        if not hasattr(self, "_bar_log_count"):
            self._bar_log_count = 0
        self._bar_log_count += 1

        if signal.action:
            diag_str = " ".join(f"{k}={v:.4f}" for k, v in signal.diagnostics.items())
            logger.debug(
                "[{}] {} signal={} reason={} vol={} | {}",
                self.strategy_name,
                bar_time,
                signal.action,
                signal.reason,
                signal.volume,
                diag_str,
            )
        elif self._bar_log_count % 100 == 1:
            if signal.diagnostics:
                diag_str = " ".join(f"{k}={v:.4f}" for k, v in signal.diagnostics.items())
            else:
                diag_str = f"close={close_price:.4f}"
            logger.debug("[{}] {} no signal | {}", self.strategy_name, bar_time, diag_str)

    def on_bar(self, bar: Any) -> None:
        """vnpy K线回调 — 从预构造缓存中 O(1) 获取上下文

        所有重活（数据加载、指标计算、上下文构造）已在 on_init 完成，
        此处仅做 dict 查找 + 策略调用 + 下单。
        """
        raw_dt: Any = getattr(bar, "datetime", None)
        if raw_dt is None:
            return
        bar_time = cast(pd.Timestamp, pd.Timestamp(raw_dt))
        close_price = float(getattr(bar, "close_price", 0))

        ctx = self._ctx_cache.get(bar_time)
        if ctx is not None:
            self._update_peak_prices(ctx.bar)
            signal = self._core.on_bar(self._state, ctx)
        else:
            if len(self._ctx_cache) == 0 and not getattr(self, "_warned_empty_cache", False):
                logger.warning("[{}] ctx_cache 为空，所有 bar 将跳过策略调用", self.strategy_name)
                self._warned_empty_cache = True
            signal = Signal()

        self._log_bar_diagnostics(bar_time, signal, close_price)

        if signal.action:
            executed = self._dispatch_signal(signal, close_price, bar_time)
            if not executed:
                logger.debug(
                    "[{}] {} signal={} reason={} vol={} 未执行: pos={} price={}",
                    self.strategy_name,
                    bar_time,
                    signal.action,
                    signal.reason,
                    signal.volume,
                    self.pos,
                    close_price,
                )

    def _dispatch_signal(self, signal: Signal, price: float, bar_time: pd.Timestamp) -> bool:
        """根据 signal.action 和当前持仓判断执行哪种交易。返回是否实际触发下单

        【不允许加仓/反向开仓 — 这是故意的】
        当前已持有多头 (pos>0) 时收到 BUY signal → 忽略（不允许加仓）
        当前已持有空头 (pos<0) 时收到 SELL signal → 忽略（不允许加仓）
        策略核心只在"无持仓"时开仓，持仓后只会触发平仓信号。
        被忽略的信号会打 debug 日志，方便排查策略逻辑问题。
        """
        if signal.action == TRADE_ACTION_BUY:
            if self.pos == 0:
                self._execute_trade(signal, price, bar_time, is_buy=True)
                return True
            if self.pos < 0:
                self._execute_trade(signal, price, bar_time, is_cover=True)
                return True
            logger.debug(
                "[%s] %s BUY signal被忽略: 已持有多头(pos=%s)，不允许加仓",
                self.strategy_name,
                bar_time,
                self.pos,
            )
            return False

        if signal.action == TRADE_ACTION_SELL:
            if self.pos > 0:
                self._execute_trade(signal, price, bar_time, is_sell=True)
                return True
            if self.pos == 0:
                self._execute_trade(signal, price, bar_time, is_short=True)
                return True
            logger.debug(
                "[%s] %s SELL signal被忽略: 已持有空头(pos=%s)，不允许加仓",
                self.strategy_name,
                bar_time,
                self.pos,
            )
            return False

        return False

    def on_tick(self, tick: Any) -> None:
        """vnpy Tick回调 — 本策略不使用 Tick 数据"""
        pass

    def on_order(self, order: Any) -> None:
        """vnpy 订单回调 — 委托变化时调用"""
        super().on_order(order)

    def on_trade(self, trade: Any) -> None:
        """vnpy 成交回调 — 同步成交状态到 State

        【为什么不在 _execute_trade 中更新 State】
        因为下单不等于成交，只有成交后才是真实的持仓变化。
        vnpy 引擎会在成交后调用 on_trade，这是更新 State 的正确时机。

        【State 是唯一真实来源】
        Strategy 应该从 state.position 读取持仓，而不是自己管理。
        """
        super().on_trade(trade)

        direction = getattr(trade, "direction", None)
        trade_price = float(getattr(trade, "price", 0))
        trade_volume = float(getattr(trade, "volume", 0))
        trade_datetime = getattr(trade, "datetime", datetime.now())

        if direction is None:
            return

        is_long = self._resolve_direction(direction)
        is_open = self._resolve_offset(getattr(trade, "offset", None))
        trade_reason = getattr(self, "_last_signal_reason", "")
        trade.reason = trade_reason  # 注入到 vnpy TradeData

        self._apply_trade_to_state(
            is_long=is_long,
            is_open=is_open,
            price=trade_price,
            volume=trade_volume,
            dt=trade_datetime,
            reason=trade_reason,
        )

    def _resolve_direction(self, direction: Any) -> bool:
        """解析 vnpy Direction 枚举或字符串，返回 True=做多"""
        if hasattr(direction, "value"):
            return DIRECTION_MAP.get(direction.value, "") == TRADE_DIRECTION_LONG
        if isinstance(direction, str):
            return str(direction).upper() == TRADE_DIRECTION_LONG
        return False

    def _resolve_offset(self, offset: Any) -> bool:
        """解析 vnpy Offset 枚举或字符串，返回 True=开仓"""
        if offset is None:
            return False
        if hasattr(offset, "value"):
            return OFFSET_MAP.get(offset.value, "") == TRADE_OFFSET_OPEN
        if isinstance(offset, str):
            return offset.upper() == "OPEN"
        return False

    def _apply_trade_to_state(
        self,
        is_long: bool,
        is_open: bool,
        price: float,
        volume: float,
        dt: Any,
        reason: str,
    ) -> None:
        """根据成交方向/开平，更新 state.position 并记录 fill

        三种场景的共同逻辑：构造 Fill → 更新 StrategyPosition → 回调 on_fill。
        """
        if is_open:
            # 开仓（多或空）
            action = cast(TradeAction, TRADE_ACTION_BUY if is_long else TRADE_ACTION_SELL)
            dir_value = cast(
                PositionDirection,
                TRADE_DIRECTION_LONG if is_long else TRADE_DIRECTION_SHORT,
            )
            fill = Fill(
                timestamp=str(dt),
                symbol=self._state.symbol,
                action=action,
                price=price,
                volume=volume,
                reason=reason,
            )
            self._state.position = StrategyPosition(
                direction=dir_value,
                entry_price=price,
                volume=volume,
                highest_price=price,
                lowest_price=price,
            )
        else:
            # 平仓（多平或空平，统一用 SELL 作为 action）
            fill = Fill(
                timestamp=str(dt),
                symbol=self._state.symbol,
                action=cast(TradeAction, TRADE_ACTION_SELL),
                price=price,
                volume=volume,
                reason=reason,
            )
            self._state.position = StrategyPosition()

        self._state.fills.append(fill)
        self._core.on_fill(fill)
        logger.debug(
            "[{}] 成交: {} {} @{:.2f} x{} pos_dir={}",
            self.strategy_name,
            fill.action,
            dt,
            price,
            volume,
            self._state.position.direction,
        )

    # ── 交易执行 ───────────────────────────────────────────

    def _execute_trade(
        self,
        signal: Signal,
        price: float,
        bar_time: pd.Timestamp,
        is_buy: bool = False,
        is_short: bool = False,
        is_cover: bool = False,
        is_sell: bool = False,
    ) -> None:
        """执行交易委托 — 统一入口

        :param signal: 策略信号
        :param price: 当前价格
        :param bar_time: K线时间
        :param is_buy: 做多开仓
        :param is_short: 做空开仓
        :param is_cover: 做空平仓
        :param is_sell: 做多平仓
        """
        self._last_signal_reason = signal.reason  # 暂存给 on_trade 使用

        if is_buy or is_short:
            volume = signal.volume
            if volume <= 0:
                return
            if is_buy:
                self.buy(price, volume)
                action_label = "买入开多"
            else:
                self.short(price, volume)
                action_label = "卖出开空"
            self.entry_price = price
            logger.debug(f"[{self.strategy_name}] {bar_time} {action_label} @{price:.2f} x{volume}")
            return

        # 平仓路径
        pos = abs(self.pos)
        if pos <= 0:
            return
        if is_cover:
            self.cover(price, pos)
            action_label = f"{signal.reason}买入平空"
        else:
            self.sell(price, pos)
            action_label = f"{signal.reason}卖出平多"
        self.entry_price = 0.0
        logger.debug(f"[{self.strategy_name}] {bar_time} {action_label} @{price:.2f}")
