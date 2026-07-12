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

import contextlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from common.constants import (
    DIRECTION_MAP,
    OFFSET_MAP,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
    TRADE_OFFSET_OPEN,
)
from loguru import logger
from vnpy_ctastrategy import CtaTemplate

from strategies import Bar, Fill, Signal, State, Strategy, UninitializedStrategy
from strategies.core.base import DecisionPayloadContract, DecisionPayloadDiagnosticsContract
from strategies.core.types import StrategyPosition
from strategies.runtime import (
    DataFeed,
    DataRequirements,
)


@dataclass(frozen=True)
class SignalDecisionContext:
    reason: str
    decision_payload: dict[str, Any]


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
        self._data_feed: DataFeed | None = None
        self.entry_price: float = 0.0
        self._order_contexts: dict[str, SignalDecisionContext] = {}
        self._active_entry_orders: dict[str, Any] = {}
        self._last_real_bar_time: pd.Timestamp | None = getattr(type(self), "last_real_bar_time", None)
        self._forced_flat_submitted: bool = False

    def is_initialized(self) -> bool:
        """检查策略是否已初始化（注入）

        :return: 是否已注入真实的 Strategy
        """
        return self._core.name != "_uninitialized"

    # ── vnpy 生命周期 ──────────────────────────────────────

    def on_init(self) -> None:
        """vnpy 初始化回调 — 加载数据、计算指标

        BarContext 在 on_bar 动态构造，不需要预缓存。
        """
        if not self.is_initialized():
            logger.error(f"[{self.strategy_name}] strategy 未注入，初始化跳过")
            return

        logger.debug(f"[{self.strategy_name}] 桥接器初始化: {self._core.name}")

        self._requirements = self._core.data_requirements(self._state.strategy_config)
        if self._requirements is None:
            self.write_log(f"策略初始化: {self._core.name}")
            return

        self._data_feed = DataFeed.create(
            symbol=self._state.symbol,
            requirements=self._requirements,
        )
        self._log_data_feed_summary("DataFeed 构造完成")

        logger.debug(
            "[{}] 初始化完成",
            self.strategy_name,
        )

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

        # 回测结束后，如有新计算的指标则更新磁盘缓存
        if self._data_feed is not None:
            self._data_feed.save_cache()

    def _log_data_feed_summary(self, label: str = "") -> None:
        """输出 DataFeed 内容摘要到日志文件（前端运行日志 Tab 可查看）

        列出每个周期的：行数、时间区间、已注册指标、已计算指标列。

        :param label: 日志标签，如 "数据加载完成（计算前）"
        """
        if self._data_feed is None:
            return
        rid = self._state.run_id
        btid = self._state.backtest_id
        for pn in self._data_feed.get_period_names():
            pd_obj = self._data_feed.get_period(pn)
            if pd_obj is None or pd_obj.length == 0:
                continue
            # 已注册指标配置
            indicators = self._data_feed.get_registered_indicators(pn)
            ind_names = [f"{spec.name}({','.join(f'{k}={v}' for k, v in spec.params.items())})" for spec in indicators]
            # 已计算完成的指标列
            calc_cols = self._data_feed.get_indicator_names(pn)
            date_range = self._data_feed.get_date_range(pn)
            range_str = f"{date_range[0]}~{date_range[1]}" if date_range else "N/A"
            logger.debug(
                f"[run={rid} bt={btid}] [{self.strategy_name}] "
                f"{label + ' ' if label else ''}"
                f"period={pn} rows={pd_obj.length} "
                f"range={range_str} "
                f"registered=[{', '.join(ind_names) if ind_names else '无'}] "
                f"calculated_columns={calc_cols}"
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

    @staticmethod
    def _format_diagnostic_value(key: str, value: Any) -> str:
        if isinstance(value, bool):
            return f"{key}={value}"
        if isinstance(value, int | float):
            return f"{key}={value:.4f}"
        return f"{key}={value}"

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
            diag_str = " ".join(self._format_diagnostic_value(key, value) for key, value in signal.diagnostics.items())
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
                diag_str = " ".join(
                    self._format_diagnostic_value(key, value) for key, value in signal.diagnostics.items()
                )
            else:
                diag_str = f"close={close_price:.4f}"
            logger.debug("[{}] {} no signal | {}", self.strategy_name, bar_time, diag_str)

    def on_bar(self, bar: Any) -> None:
        """vnpy K线回调 — 动态构造 BarContext 并驱动策略

        所有数据已在 on_init 加载并计算好指标（含聚合），BarContext 动态构造。
        """
        raw_dt: Any = getattr(bar, "datetime", None)
        if raw_dt is None:
            return
        bar_time = pd.Timestamp(raw_dt)
        close_price = float(getattr(bar, "close_price", 0))
        is_synthetic_liquidation = bool(getattr(bar, "is_synthetic_liquidation", False))

        # 下午收盘撤销当日未成交的开仓挂单（在驱动策略前先清理，避免跨夜/跨日误成交）
        self._maybe_cancel_stale_entry_orders(bar_time)

        if is_synthetic_liquidation:
            return

        assert self._data_feed is not None
        assert self._requirements is not None
        assert self._data_feed.base_period is not None

        # vnpy bar → 标准 Bar，datetime 转成 Python datetime
        bar_obj = Bar(
            symbol=self._state.symbol,
            datetime=bar_time.to_pydatetime(),
            open=float(getattr(bar, "open_price", 0)),
            high=float(getattr(bar, "high_price", 0)),
            low=float(getattr(bar, "low_price", 0)),
            close=close_price,
            volume=float(getattr(bar, "volume", 0)),
        )

        # 动态构造 BarContext
        ctx = self._data_feed.build_context(self._requirements, bar_obj)

        self._update_peak_prices(ctx.bar)
        signal = self._core.on_bar(self._state, ctx)

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

        self._force_flat_at_backtest_end(bar_time, close_price)

    def _force_flat_at_backtest_end(self, bar_time: pd.Timestamp, price: float) -> None:
        if self._forced_flat_submitted or self._last_real_bar_time is None:
            return
        if bar_time < self._last_real_bar_time:
            return
        pos = float(self.pos)
        if pos == 0:
            self._forced_flat_submitted = True
            return

        self._forced_flat_submitted = True
        payload = DecisionPayloadContract(
            source="vnpy_backtest_bridge",
            event_type="system_forced_flat",
            diagnostics=DecisionPayloadDiagnosticsContract(
                execution={
                    "trigger": "backtest_end",
                    "policy": "synthetic_liquidation_bar",
                }
            ),
        )
        payload.validate()
        signal = Signal(
            action=TRADE_ACTION_BUY if pos < 0 else TRADE_ACTION_SELL,
            reason="forced_flat_at_backtest_end",
            volume=abs(pos),
            decision_payload=payload.to_dict(),
        )
        self._dispatch_signal(signal, price, bar_time)
        logger.debug("[{}] {} 回测结束强制平仓 @{:.2f} x{}", self.strategy_name, bar_time, price, abs(pos))

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
                self._execute_trade(signal, price, bar_time)
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
        context = self._get_trade_context(trade)
        trade_reason = context.reason if context else ""
        trade_payload = context.decision_payload if context else {}
        trade_payload_json = json.dumps(trade_payload, ensure_ascii=False) if trade_payload else ""
        trade.reason = trade_reason  # 注入到 vnpy TradeData
        trade.decision_payload_json = trade_payload_json

        self._apply_trade_to_state(
            is_long=is_long,
            is_open=is_open,
            price=trade_price,
            volume=trade_volume,
            dt=trade_datetime,
            reason=trade_reason,
            decision_payload=trade_payload,
        )

        # 成交后从开仓挂单登记表移除（开仓单成交即不再 pending；平仓单本就不登记）
        for oid in self._trade_order_ids(trade):
            self._active_entry_orders.pop(oid, None)

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

    def _trade_order_ids(self, trade: Any) -> list[str]:
        ids: list[str] = []
        for attr in ("vt_orderid", "orderid"):
            value = getattr(trade, attr, None)
            if value:
                ids.append(str(value))
        return ids

    def _get_trade_context(self, trade: Any) -> SignalDecisionContext | None:
        for order_id in self._trade_order_ids(trade):
            context = self._order_contexts.get(order_id)
            if context is not None:
                return context
        return None

    def _register_order_context(self, order_ids: str | list[str], signal: Signal) -> None:
        ids = [order_ids] if isinstance(order_ids, str) else order_ids
        if not ids:
            return
        context = SignalDecisionContext(
            reason=signal.reason,
            decision_payload=signal.decision_payload,
        )
        for order_id in ids:
            if order_id:
                self._order_contexts[str(order_id)] = context

    def _track_entry_order(self, order_ids: str | list[str], bar_time: pd.Timestamp) -> None:
        """登记开仓挂单（仅开仓），记录下单日期，供「当日未成交→下午收盘撤销」。"""
        ids = [order_ids] if isinstance(order_ids, str) else (order_ids or [])
        for oid in ids:
            if oid:
                self._active_entry_orders[str(oid)] = bar_time.date()

    def _maybe_cancel_stale_entry_orders(self, bar_time: pd.Timestamp) -> None:
        """下午收盘撤销当日未成交的开仓挂单。

        规则（兼顾日盘-only 与含夜盘合约）：
          - 挂单下单日若已进入「下午收盘后」（bar 小时 >= cancel_hour，默认 15）→ 撤销；
          - 或挂单跨到了新的日历日（夜盘仍未成交也一并作废）→ 撤销。
        仅撤销「开仓」挂单；平仓（SL/TIME）挂单不在此撤销，须保留至成交。

        注意：本策略只在当日早盘首根 bar 尝试开仓，故 cancel_hour 以日盘下午收盘为界
        即可，不会误伤夜盘开仓（本策略无夜盘开仓）。
        """
        if not self._active_entry_orders:
            return
        cancel_hour = 15
        today = bar_time.date()
        to_cancel: list[str] = []
        for oid, placed_date in self._active_entry_orders.items():
            if placed_date != today or bar_time.hour >= cancel_hour:
                to_cancel.append(oid)
        for oid in to_cancel:
            with contextlib.suppress(Exception):
                self.cancel_order(oid)
            self._active_entry_orders.pop(oid, None)
        if to_cancel:
            logger.debug(
                "[{}] {} 下午收盘撤销未成交开仓挂单 x{}",
                self.strategy_name,
                bar_time,
                len(to_cancel),
            )

    def _apply_trade_to_state(
        self,
        is_long: bool,
        is_open: bool,
        price: float,
        volume: float,
        dt: Any,
        reason: str,
        decision_payload: dict[str, Any],
    ) -> None:
        """根据成交方向/开平，更新 state.position 并记录 fill

        三种场景的共同逻辑：构造 Fill → 更新 StrategyPosition → 回调 on_fill。
        """
        if is_open:
            # 开仓（多或空）
            action = TRADE_ACTION_BUY if is_long else TRADE_ACTION_SELL
            dir_value = TRADE_DIRECTION_LONG if is_long else TRADE_DIRECTION_SHORT
            fill = Fill(
                timestamp=str(dt),
                symbol=self._state.symbol,
                action=action,
                price=price,
                volume=volume,
                reason=reason,
                decision_payload=decision_payload,
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
                action=TRADE_ACTION_SELL,
                price=price,
                volume=volume,
                reason=reason,
                decision_payload=decision_payload,
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
    ) -> None:
        """执行交易委托 — 统一入口

        :param signal: 策略信号
        :param price: 当前价格（LIMIT 默认挂单价 / STOP 兜底价）
        :param bar_time: K线时间
        :param is_buy: 做多开仓
        :param is_short: 做空开仓
        :param is_cover: 做空平仓

        发单类型通道：Signal.order_type 指定 'LIMIT' | 'STOP' | 'MARKET'。
        - LIMIT 且带 limit_price → 用 limit_price；否则用当前 bar 收盘价（旧行为）。
        - STOP 且带 stop_price → 用 stop_price 作为触发价（vnpy stop=True）。
        - 未指定 order_type → 默认 LIMIT@close，完全向后兼容。
        """
        order_type = getattr(signal, "order_type", "LIMIT") or "LIMIT"
        stop = order_type == "STOP"
        limit_price = getattr(signal, "limit_price", None)
        stop_price = getattr(signal, "stop_price", None)
        if order_type == "LIMIT" and limit_price is not None:
            exec_price = float(limit_price)
        elif order_type == "STOP" and stop_price is not None:
            exec_price = float(stop_price)
        else:
            exec_price = price

        if is_buy or is_short:
            volume = signal.volume
            if volume <= 0:
                return
            if is_buy:
                order_ids = self.buy(exec_price, volume, stop=stop)
                action_label = "买入开多"
            else:
                order_ids = self.short(exec_price, volume, stop=stop)
                action_label = "卖出开空"
            self._register_order_context(order_ids, signal)
            # 开仓挂单：登记下单日期，供下午收盘未成交撤销
            self._track_entry_order(order_ids, bar_time)
            self.entry_price = exec_price
            logger.debug(
                f"[{self.strategy_name}] {bar_time} {action_label} @{exec_price:.2f} x{volume} type={order_type}"
            )
            return

        # 平仓路径
        pos = abs(self.pos)
        if pos <= 0:
            return
        if is_cover:
            order_ids = self.cover(exec_price, pos, stop=stop)
            action_label = f"{signal.reason}买入平空"
        else:
            order_ids = self.sell(exec_price, pos, stop=stop)
            action_label = f"{signal.reason}卖出平多"
        self._register_order_context(order_ids, signal)
        self.entry_price = 0.0
        logger.debug(f"[{self.strategy_name}] {bar_time} {action_label} @{exec_price:.2f}")
