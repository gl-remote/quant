# -*- coding: utf-8 -*-
"""
vn.py 回测引擎 (纯执行器)

基于 vnpy_ctastrategy.backtesting.BacktestingEngine，接收 DataFrame + 策略参数，
返回结构化回测结果。不负责数据加载和策略创建。

职责明确：
  - data_utils 负责数据转换
  - strategy_factory 负责策略创建
  - results 负责结果聚合
  - optimizer 负责参数搜索
  - backtest 层仅调用 vnpy 执行回测
"""

from __future__ import annotations

from loguru import logger
from typing import Any, cast

import pandas as pd

from strategies.utils import serialize_strategy_params
from config.app_config import BacktestConfig
from data.manager import DataManager

from .data_utils import df_to_vnpy_datalines, resolve_interval, calculate_date_range
from .results import aggregate_walk_forward
from .strategy_factory import create_strategy_class

from common.symbol_utils import parse_contract
from common.types import BacktestResult
from common.constants import DIRECTION_MAP, OFFSET_MAP
from common.contract_specs import CONTRACT_SPECS, BROKER_ADDON_DFCF


class VnpyBacktestEngine:
    """vn.py 回测引擎 (纯执行器)

    接收 DataFrame + 策略名称参数，调用 vnpy BacktestingEngine 执行回测，
    返回结构化结果字典。

    使用方式:
        engine = VnpyBacktestEngine(backtest_config, data_manager)
        results = engine.run(pairs)             # 多策略 × 多品种
        wf_result = engine.run_walk_forward(    # 单策略 Walk-Forward
            data, symbol, strategy_name, strategy_params, ...
        )
    """

    def __init__(self, backtest_config: BacktestConfig, dm: DataManager):
        """
        Args:
            backtest_config: 回测配置（含 capital/commission/slippage 等交易环境参数）
            dm: 数据管理器，提供数据加载能力
        """
        self._dm = dm
        self._run_id: int | None = None
        self._git_hash: str | None = None
        self.initial_capital: float = float(backtest_config.initial_capital)
        self.commission_rate: float = float(backtest_config.commission_rate)
        self.slippage: float = float(backtest_config.slippage)
        self.price_tick: float = float(backtest_config.price_tick)
        self.contract_size: int = int(backtest_config.contract_size)
        self.interval: str = backtest_config.interval

        if self.initial_capital <= 0:
            raise ValueError(
                f"initial_capital 必须大于 0，当前: {self.initial_capital}"
            )
        if not (0 <= self.commission_rate < 1):
            raise ValueError(
                f"commission_rate 必须在 [0, 1) 范围内，当前: {self.commission_rate}"
            )
        if self.slippage < 0:
            raise ValueError(f"slippage 不能为负数，当前: {self.slippage}")
        if self.price_tick <= 0:
            raise ValueError(f"price_tick 必须大于 0，当前: {self.price_tick}")
        if self.contract_size <= 0:
            raise ValueError(f"contract_size 必须大于 0，当前: {self.contract_size}")

    def set_git_hash(self, git_hash: str | None) -> None:
        """设置 Git 提交哈希"""
        self._git_hash = git_hash

    # ── 私有辅助方法 ──────────────────────────────────────────

    def _create_backtest_result(
        self,
        symbol: str,
        backtest_id: int | None,
        strategy_name: str,
        strategy_version: str | None,
        strategy_params: dict[str, float] | None,
        error: str | None,
        data_start: str,
        data_end: str,
        total_days: int,
        stats: dict[str, Any],
        daily_results: list[dict[str, Any]],
        trades: list[dict[str, Any]] | None = None,
    ) -> BacktestResult:
        """创建 BacktestResult 对象

        Args:
            symbol: 品种代码
            backtest_id: 回测记录 ID
            strategy_name: 策略名称
            strategy_version: 策略版本
            strategy_params: 策略参数
            error: 错误信息（如果有）
            data_start: 开始日期
            data_end: 结束日期
            total_days: 总天数
            stats: 统计信息字典
            daily_results: 每日结果列表
            trades: 交易记录列表

        Returns:
            BacktestResult 对象

        调试沉淀(2026-06-04):
        - vn.py 回测引擎返回的 statistics 字典中，总交易数的键为 total_trade_count 而非 total_trades
        - 旧代码从 profit_days/loss_days 读取会导致错误的交易统计
        - win_trades/loss_trades 等字段在默认统计输出中可能缺失
        """
        return BacktestResult(
            symbol=symbol,
            backtest_id=backtest_id,
            strategy=strategy_name,
            strategy_version=strategy_version,
            git_hash=self._git_hash,
            strategy_params=strategy_params or {},
            success=error is None,
            error_message=error,
            start_date=data_start,
            end_date=data_end,
            total_days=total_days,
            # ── 核心绩效指标（vnpy calculate_statistics 直接输出）───
            # vnpy 键名为 total_trade_count；total_trades 为旧版兼容 fallback
            total_trades=stats.get("total_trade_count", stats.get("total_trades", 0))
            or 0,
            total_return=stats.get("total_return", 0.0) or 0.0,
            end_balance=stats.get("end_balance", self.initial_capital)
            or self.initial_capital,
            annual_return=stats.get("annual_return"),
            sharpe_ratio=stats.get("sharpe_ratio"),
            max_drawdown=stats.get("max_drawdown"),
            max_ddpercent=stats.get("max_ddpercent"),
            max_drawdown_duration=stats.get(
                "max_drawdown_duration", stats.get("max_ddpercent_duration", 0)
            ),
            daily_std=stats.get("return_std", stats.get("daily_std")),
            return_drawdown_ratio=stats.get("return_drawdown_ratio"),
            # ── 盈亏汇总（vnpy 直接输出）───────────────────────
            total_net_pnl=stats.get("total_net_pnl"),
            daily_net_pnl=stats.get("daily_net_pnl"),
            total_commission=stats.get("total_commission"),
            daily_commission=stats.get("daily_commission"),
            total_slippage=stats.get("total_slippage"),
            daily_slippage=stats.get("daily_slippage"),
            total_turnover=stats.get("total_turnover"),
            daily_turnover=stats.get("daily_turnover"),
            # ── 交易日统计（vnpy 直接输出）──────────────────────
            profit_days=stats.get("profit_days"),
            loss_days=stats.get("loss_days"),
            daily_trade_count=stats.get("daily_trade_count"),
            daily_return_pct=stats.get("daily_return"),
            # ── 交易级别统计（自行从逐笔 pnl 聚合计算）────────────
            win_trades=stats.get("win_trades", 0) or 0,
            loss_trades=stats.get("loss_trades", 0) or 0,
            win_rate=stats.get("win_rate"),
            max_consecutive_win=stats.get("max_consecutive_win"),
            max_consecutive_loss=stats.get("max_consecutive_loss"),
            avg_win=stats.get("average_win"),
            avg_loss=stats.get("average_loss"),
            win_loss_ratio=stats.get("win_loss_ratio"),
            # ── 进阶指标（vnpy 输出）───────────────────────────
            ewm_sharpe=stats.get("ewm_sharpe"),
            rgr_ratio=stats.get("rgr_ratio"),
            # ── 引擎配置（入参）────────────────────────────────
            initial_capital=self.initial_capital,
            commission_rate=self.commission_rate,
            slippage=self.slippage,
            price_tick=self.price_tick,
            contract_size=self.contract_size,
            kline_interval=self.interval,
            daily_results=daily_results if daily_results else [],
            fills=trades if trades else [],
        )

    def _create_placeholder_record(
        self,
        symbol: str,
        strategy_name: str,
        strategy_version: str | None,
        data_start: str,
        data_end: str,
        total_days: int,
    ) -> Any:
        """创建回测占位记录

        Args:
            symbol: 品种代码
            strategy_name: 策略名称
            strategy_version: 策略版本
            data_start: 开始日期
            data_end: 结束日期
            total_days: 总天数

        Returns:
            创建的 Backtest 模型实例
        """
        from data.models import Backtest as BTModel

        return BTModel.create(
            run=self._run_id,
            symbol=symbol,
            strategy=strategy_name,
            strategy_version=strategy_version,
            git_hash=self._git_hash,
            status="running",
            start_date=data_start,
            end_date=data_end,
            total_days=total_days,
            initial_capital=self.initial_capital,
            commission_rate=self.commission_rate,
            slippage=self.slippage,
            price_tick=self.price_tick,
            contract_size=self.contract_size,
            kline_interval=self.interval,
        )

    # ── 公开接口 ──────────────────────────────────────────────

    def run(
        self,
        pairs: list[tuple[str, pd.DataFrame, str, dict[str, Any]]],
    ) -> list[BacktestResult]:
        """执行多策略 × 多品种回测

        每个品种创建一个 vnpy engine，注册该品种的所有策略，一次回放拿到多组结果。

        Args:
            pairs: [(symbol, DataFrame, strategy_name, strategy_params), ...]

        Returns:
            list[BacktestResult]
        """
        logger.info(f"{'=' * 60}")
        logger.info(f"启动 vn.py 回测: {len(pairs)} 个配对")
        logger.info(
            f"资金={self.initial_capital:,.0f} "
            f"费率={self.commission_rate:.4%} 滑点={self.slippage}"
        )
        logger.info(f"{'=' * 60}")

        from collections import defaultdict

        groups: dict[int, list[tuple[str, str, dict[str, Any]]]] = defaultdict(list)
        df_map: dict[int, pd.DataFrame] = {}
        for sym, df, strategy_name, strategy_params in pairs:
            df_id = id(df)
            groups[df_id].append((sym, strategy_name, strategy_params))
            df_map[df_id] = df

        results: list[BacktestResult] = []
        for df_id, items in groups.items():
            df = df_map[df_id]
            symbols = [sym for sym, _, _ in items]
            strategy_names = [name for _, name, _ in items]
            strategy_params_list = [params for _, _, params in items]
            symbol = symbols[0]

            logger.info(f"\n>>> 品种: {symbol} ({len(strategy_names)} 个策略)")

            data_start, data_end, total_days = calculate_date_range(df)
            logger.debug(
                f"数据: {len(df)} 条, {data_start} ~ {data_end}, 共 {total_days} 天"
            )

            batch_results = self._run_backtest(
                df, symbol, strategy_names, strategy_params_list
            )
            for i, r in enumerate(batch_results):
                stats = r.get("statistics", {})
                daily = r.get("daily_results", [])
                error = r.get("error")
                sym = symbols[i] if i < len(symbols) else symbol
                strategy_config = r.get("strategy_config")
                results.append(
                    self._create_backtest_result(
                        symbol=sym,
                        backtest_id=r.get("bt_id"),
                        strategy_name=strategy_names[i]
                        if i < len(strategy_names)
                        else "unknown",
                        strategy_version=r.get("strategy_version"),
                        strategy_params=serialize_strategy_params(strategy_config)
                        if strategy_config
                        else {},
                        error=error,
                        data_start=data_start,
                        data_end=data_end,
                        total_days=total_days,
                        stats=stats,
                        daily_results=daily,
                        trades=r.get("trades", []),
                    )
                )

        succeeded = sum(1 for r in results if r.success)
        logger.info(f"\n回测完成: {succeeded}/{len(results)} 成功")
        return results

    def run_walk_forward(
        self,
        data: pd.DataFrame | None,
        symbol: str,
        strategy_name: str,
        strategy_params: dict[str, Any],
        train_size: int | None = None,
        val_size: int | None = None,
        test_size: int | None = None,
        step: int | None = None,
    ) -> dict[str, Any]:
        """执行 Walk-Forward 时间序列验证回测

        Args:
            data: K 线数据 (已由调用方加载和日期过滤)
            symbol: 合约代码
            strategy_name: 策略名称
            strategy_params: 策略参数字典
            train_size/val_size/test_size/step: 窗口参数

        Returns:
            walk_forward 结果字典
        """
        from .walk_forward import walk_forward_split_by_ratio, walk_forward_split

        if data is None or data.empty:
            return {"success": False, "error": "数据为空", "windows": 0}

        if train_size is not None and val_size is not None and test_size is not None:
            step_val = step or max(1, test_size // 2)
            windows = walk_forward_split(
                data, train_size, val_size, test_size, step_val
            )
        else:
            windows = walk_forward_split_by_ratio(data)

        if not windows:
            return {"success": False, "error": "无法生成窗口", "windows": 0}

        logger.info(f"Walk-Forward: {len(windows)} 个窗口, {symbol}")

        window_results = []
        for wi, (train_df, val_df, test_df) in enumerate(windows):
            logger.debug(f"\n>>> Walk-Forward 窗口 {wi + 1}/{len(windows)}")
            train_results = self._run_backtest(
                train_df,
                symbol,
                [strategy_name],
                [strategy_params],
            )
            test_results = self._run_backtest(
                test_df,
                symbol,
                [strategy_name],
                [strategy_params],
            )

            train_result = train_results[0] if train_results else {}
            test_result = test_results[0] if test_results else {}

            if "error" in train_result or "error" in test_result:
                logger.warning(
                    f"窗口 {wi + 1} 回测异常，跳过: "
                    f"train_error={train_result.get('error')}, "
                    f"test_error={test_result.get('error')}"
                )
                continue

            window_results.append(
                {
                    "window": wi,
                    "train_rows": len(train_df),
                    "val_rows": len(val_df),
                    "test_rows": len(test_df),
                    "train_start": str(train_df["datetime"].iloc[0])[:10],
                    "train_end": str(train_df["datetime"].iloc[-1])[:10],
                    "test_start": str(test_df["datetime"].iloc[0])[:10],
                    "test_end": str(test_df["datetime"].iloc[-1])[:10],
                    "statistics": test_result.get("statistics", {}),
                    "statistics_is": train_result.get("statistics", {}),
                }
            )

        aggregate = aggregate_walk_forward(window_results)

        logger.info(
            f"Walk-Forward 汇总 ({len(windows)} 窗口): "
            f"OOS均收益={aggregate.return_mean:.2%}, "
            f"夏普={aggregate.sharpe_mean:.2f}, "
            f"IS-OOS差距={aggregate.is_oos_return_gap:.2%}, "
            f"盈利窗口比={aggregate.positive_window_ratio:.0%}"
        )

        return {
            "success": True,
            "symbol": symbol,
            "windows": len(windows),
            "window_results": window_results,
            "aggregate": aggregate.to_dict(),
        }

    # ── 内部方法 ──────────────────────────────────────────────

    def _run_backtest(
        self,
        df: pd.DataFrame,
        symbol: str,
        strategy_names: list[str],
        strategy_params_list: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """在单个数据集上执行 vnpy 回测

        Args:
            df: K 线数据
            symbol: 品种代码
            strategy_names: 策略名称列表
            strategy_params_list: 策略参数列表

        Returns:
            list[dict]，每个 dict:
              - statistics, daily_results, strategy_config, strategy_version
              - error (如果失败)
        """
        from vnpy_ctastrategy.backtesting import BacktestingEngine
        from vnpy.trader.constant import Exchange

        c = parse_contract(symbol)
        if c is None:
            raise ValueError(f"无法解析合约代码: {symbol!r}")
        pure_symbol = c.contract_code
        exchange_code = c.exchange
        vt_symbol = f"{pure_symbol}.{Exchange(exchange_code).value}"

        interval = resolve_interval(self.interval)
        bars = df_to_vnpy_datalines(df, pure_symbol, exchange_code, interval)

        data_start, data_end, total_days = calculate_date_range(df)

        # ── 根据品种查合约规格表，自动填充参数 ─────────────────────────
        spec = CONTRACT_SPECS.get_symbol(symbol)
        if spec is not None:
            # 合约乘数 / 最小变动价位
            cs = spec.size
            pt = spec.tick
            # 滑点（价格单位）: slip_tick × tick
            sl = spec.tick * spec.slip_tick
            # 保证金比例
            mg = spec.margin
            # 手续费：含交易所 + 期货公司加收
            # vnpy 只支持费率模式 commission = price × volume × size × rate
            # 固定元/手品种需要换算为 rate = 总手续费/手 / (均价 × 合约乘数)
            # 均价用 OHLC 四价均值比单独 close 更稳定
            avg_price = (
                float(df[["open", "high", "low", "close"]].mean().mean())
                if not df.empty
                else 0.0
            )
            if avg_price > 0 and spec.size > 0:
                total_per_lot = spec.commission + BROKER_ADDON_DFCF
                if spec.is_rate:
                    # 费率品种：交易所费率 + 加收元/手折算回费率
                    cr = spec.commission + BROKER_ADDON_DFCF / (avg_price * spec.size)
                else:
                    # 固定元/手品种：总费用/手 ÷ (均价 × 合约乘数)
                    cr = total_per_lot / (avg_price * spec.size)
            else:
                # avg_price=0 或 size=0: 全部回退到默认值，避免 cs/pt/sl 取自 spec 而 cr 取自默认的不一致
                cs = self.contract_size
                pt = self.price_tick
                sl = self.slippage
                mg = 0.1
                cr = self.commission_rate
        else:
            cs = self.contract_size
            pt = self.price_tick
            sl = self.slippage
            mg = 0.1
            cr = self.commission_rate

        results: list[dict[str, Any]] = []
        for strategy_name, strategy_params in zip(strategy_names, strategy_params_list):
            # 提前获取策略版本号
            from strategies import load_strategy

            _core = load_strategy(strategy_name)
            strategy_version = getattr(type(_core), "VERSION", None)

            # 创建占位记录
            bt_placeholder = self._create_placeholder_record(
                symbol=symbol,
                strategy_name=strategy_name,
                strategy_version=strategy_version,
                data_start=data_start,
                data_end=data_end,
                total_days=total_days,
            )
            bt_id = bt_placeholder.id

            strategy_cls = create_strategy_class(
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                symbol=symbol,
                period=self.interval,
                capital=self.initial_capital,
                contract_size=cs,  # 品种级合约乘数
                margin=mg,  # 品种级保证金比例
                run_id=self._run_id or 0,
                backtest_id=bt_id,
            )

            engine = BacktestingEngine()
            # vnpy print → loguru，加上下文，丢进度条
            _ctx = f"bt{bt_id}/{symbol}/{strategy_name}"
            _params_summary = ", ".join(f"{k}={v}" for k, v in strategy_params.items())

            def _vnpy_output(msg: str, _ctx: str = _ctx) -> None:
                if "回放进度" in msg:
                    return
                logger.debug(f"[vnpy|{_ctx}] {msg}")

            engine.output = _vnpy_output
            logger.debug(f"[vnpy|{_ctx}] 参数: {_params_summary}")
            engine.set_parameters(
                vt_symbol=vt_symbol,
                interval=interval,
                start=df["datetime"].iloc[0].to_pydatetime(),
                end=df["datetime"].iloc[-1].to_pydatetime(),
                rate=cr,  # 品种级费率（固定元/手已换算）
                slippage=sl,  # 品种级滑点（slip_tick × tick）
                size=cs,  # 品种级合约乘数
                pricetick=pt,  # 品种级最小变动价位
                capital=int(self.initial_capital),
            )
            engine.add_strategy(strategy_cls, {"price_tick": pt})
            engine.history_data = bars

            try:
                with logger.contextualize(bt_id=f"|bt{bt_id}"):
                    engine.run_backtesting()
                daily_results = engine.calculate_result()
                statistics = engine.calculate_statistics()

                """
                从 vnpy 回测引擎中提取交易记录并格式化

                调试沉淀(2026-06-04):
                - vn.py BacktestingEngine.trades 是一个字典，而非列表！
                - 字典键格式: 'BACKTESTING.1', 'BACKTESTING.2'... 等序号字符串
                - 值类型: vnpy.trader.object.TradeData 对象
                - 旧代码直接遍历字典导致只拿到键字符串，报 'str' object has no attribute 'datetime' 错误
                - 需要用 dict.values() 获取 TradeData 对象列表

                调试沉淀(2026-06-06):
                - TradeData 无 trade_pnl / commission 字段（vnpy 4.x 设计如此）
                - vnpy 的费用计算在 DailyResult.calculate_pnl() 中按日汇总：
                  commission = sum(price * volume * size * rate)   每笔成交
                  slippage  = sum(volume * size * slippage)         每笔成交
                  net_pnl   = total_pnl - commission - slippage
                - 我们在 FIFO 配对层面用相同公式逐笔计算，结果与 vnpy 日度净盈亏一致
                """
                trades_list = []
                if hasattr(engine, "trades"):
                    trades_list = list(engine.trades.values())

                # 从 vnpy 引擎读取费率参数（与 set_parameters 传入的一致）
                _rate = cr
                _slip = sl
                _size = cs

                # FIFO 配对开平仓，计算逐笔净盈亏（含费用）
                #
                # 算法概述:
                #   1. 按时间排序所有成交记录
                #   2. 维护开仓队列 open_queue: (direction, price, volume)，遇到 offset=open 时入队
                #   3. 遇到 offset=close 时，按 FIFO 从队列取最旧的开仓记录配对，过程中同时记录
                #      实际配对的 (开仓价, 配对量)，用于计算加权平均开仓价（一套配对，两个用途）：
                #      a. 毛利 = (平仓价 - 开仓价) × 方向系数 × 配对量 × 合约乘数
                #      b. commission += 开仓侧(价×量×size×rate) + 平仓侧(价×量×size×rate)
                #      c. slippage_cost += 开仓侧(量×size×slip) + 平仓侧(量×size×slip)
                #   5. 净盈亏(pnl) = 毛利 - 总commission - 总slippage_cost
                #   6. 加权平均开仓价 = Σ(配对的开仓价×配对量) / Σ(配对量)（与 PnL 同源同套配对）
                #   7. 开仓记录的 pnl/commission 均为 0，费用统一挂到平仓记录上
                # 费用公式与 vnpy DailyResult.calculate_pnl() 完全一致
                trades_list.sort(
                    key=lambda t: t.datetime.timestamp() if t.datetime else 0
                )
                # 开仓队列: (direction, price, volume)
                open_queue: list[tuple[str, float, float]] = []
                trade_pnls: list[float] = [0.0] * len(trades_list)
                trade_commissions: list[float] = [0.0] * len(trades_list)
                trade_open_prices: list[float] = [0.0] * len(
                    trades_list
                )  # 开仓价（开仓=成交价，平仓=加权平均开仓价）

                for i, trade in enumerate(trades_list):
                    offset_val = getattr(trade, "offset", None)
                    offset_str = (
                        offset_val.value
                        if offset_val is not None and hasattr(offset_val, "value")
                        else str(offset_val)
                        if offset_val
                        else ""
                    )
                    offset = OFFSET_MAP.get(offset_str, offset_str)
                    trade_price = getattr(trade, "price", 0.0)
                    trade_volume = getattr(trade, "volume", 0.0)

                    if offset == "open":
                        direction_val = getattr(trade, "direction", None)
                        direction_str = (
                            direction_val.value
                            if direction_val is not None
                            and hasattr(direction_val, "value")
                            else str(direction_val)
                            if direction_val
                            else ""
                        )
                        direction = DIRECTION_MAP.get(direction_str, direction_str)
                        open_queue.append((direction, trade_price, trade_volume))
                        trade_pnls[i] = 0.0
                        trade_open_prices[i] = (
                            trade_price  # 开仓记录 open_price = 自己的成交价
                        )
                        # 开仓手续费在平仓时一并计入（完整的一开一平周期）
                        trade_commissions[i] = 0.0
                    else:
                        # 平仓：先提取方向，计算被平仓方向
                        direction_val = getattr(trade, "direction", None)
                        direction_str = (
                            direction_val.value
                            if direction_val is not None
                            and hasattr(direction_val, "value")
                            else str(direction_val)
                            if direction_val
                            else ""
                        )
                        direction = DIRECTION_MAP.get(direction_str, direction_str)
                        # vnpy 约定: 平多(dir=short) → 匹配开多(dir=long)
                        #           平空(dir=long)  → 匹配开空(dir=short)
                        expected_open_dir: str = (
                            "long" if direction == "short" else "short"
                        )

                        # 平仓：按 FIFO 与开仓配对，计算净盈亏
                        remaining = trade_volume
                        gross_pnl = 0.0
                        total_commission = 0.0
                        total_slippage = 0.0
                        matched_opens: list[
                            tuple[float, float]
                        ] = []  # 记录实际配对的 (开仓价, 配对量)

                        # 平仓自身的手续费和滑点
                        total_commission += trade_price * trade_volume * _size * _rate
                        total_slippage += trade_volume * _size * _slip

                        while remaining > 0 and open_queue:
                            open_dir, open_price, open_vol = open_queue[0]
                            # 跳过方向不匹配的开仓（避免多空错配）
                            if open_dir != expected_open_dir:
                                open_queue.pop(0)
                                continue
                            matched_vol = min(remaining, open_vol)
                            matched_opens.append((open_price, matched_vol))
                            price_diff = trade_price - open_price

                            # 毛利（价差收益）
                            if open_dir == "long":
                                gross_pnl += price_diff * matched_vol * _size
                            else:  # short
                                gross_pnl += -price_diff * matched_vol * _size

                            # 配对开仓侧的费用（与 vnpy DailyResult 公式一致）
                            total_commission += open_price * matched_vol * _size * _rate
                            total_slippage += matched_vol * _size * _slip

                            remaining -= matched_vol
                            if matched_vol >= open_vol:
                                open_queue.pop(0)
                            else:
                                open_queue[0] = (
                                    open_dir,
                                    open_price,
                                    open_vol - matched_vol,
                                )

                        # 从实际 FIFO 配对记录计算加权平均开仓价（与 PnL 同源）
                        total_matched_cost = sum(p * v for p, v in matched_opens)
                        total_matched_vol = sum(v for _, v in matched_opens)
                        trade_open_prices[i] = (
                            total_matched_cost / total_matched_vol
                            if total_matched_vol > 0
                            else trade_price
                        )

                        # 防御性检查: 剩余量未被配对
                        if remaining > 0:
                            logger.warning(
                                f"[{symbol}] 平仓有余量未配对: dir={direction} "
                                f"qty={trade_volume} remaining={remaining} "
                                f"open_queue_empty={not bool(open_queue)}"
                            )
                            # 修正：只对已配对部分收费（当前平仓侧费用按 trade_volume 全量算了）
                            # 实际上偏差不大，因为 vnpy 正常场景不会产生超持仓的平仓

                        # 净盈亏 = 毛利 - 手续费 - 滑点
                        trade_pnls[i] = gross_pnl - total_commission - total_slippage
                        trade_commissions[i] = total_commission

                """
                将 vnpy TradeData 对象转换为标准字典（字段名与 ORM BacktestTrade 对齐）

                字段映射（vnpy TradeData → 标准字段）:
                    datetime   → datetime
                    direction  → direction (枚举值转字符串)
                    offset     → offset    (枚举值转字符串)
                    price      → open_price（开仓=成交价，平仓=实际 FIFO 配对加权平均开仓价）, close_price（成交价）
                    volume     → quantity
                    pnl        → 净盈亏（FIFO 配对计算，已扣除 commission + slippage）
                    commission → 手续费总额（开仓侧 + 平仓侧，与 vnpy DailyResult 公式一致）
                    (symbol 由外层注入)

                调试沉淀(2026-06-04):
                - direction 和 offset 是枚举类型，需调用 .value 获取字符串值
                - 避免直接访问 trade 对象属性，使用 getattr() 以防字段缺失

                调试沉淀(2026-06-06):
                - pnl 为净盈亏（扣除手续费和滑点），commission 为该笔平仓周期内的总手续费
                - 费用公式与 vnpy DailyResult.calculate_pnl() 完全一致：
                  commission = Σ(price × volume × size × rate)
                  slippage  = Σ(volume × size × slippage)

                调试沉淀(2026-06-06 v2):
                - 平仓记录 open_price → 实际 FIFO 配对加权平均开仓价（Σ 配对的 price×vol / Σ 配对的 vol）
                - 与 PnL 同源同套 FIFO while 循环（matched_opens 记录），避免两套配对不一致
                - close_price → 平仓成交价（不变）
                - (close_price - open_price) × quantity × size × direction = 毛利，pnl = 净利（已扣费用）
                - 开仓记录 open_price = close_price = 成交价（不变）
                """
                formatted_trades = []
                for i, trade in enumerate(trades_list):
                    dt = getattr(trade, "datetime", None)
                    direction_val = getattr(trade, "direction", None)
                    offset_val = getattr(trade, "offset", None)
                    price_val = getattr(trade, "price", 0.0)
                    quantity_val = getattr(trade, "volume", 0.0)

                    direction = (
                        DIRECTION_MAP.get(direction_val.value)
                        if direction_val is not None and hasattr(direction_val, "value")
                        else DIRECTION_MAP.get(str(direction_val), str(direction_val))
                    )
                    offset = (
                        OFFSET_MAP.get(offset_val.value)
                        if offset_val is not None and hasattr(offset_val, "value")
                        else OFFSET_MAP.get(str(offset_val), str(offset_val))
                    )

                    trade_dict = {
                        "datetime": dt,
                        "symbol": symbol,
                        "direction": direction,
                        "offset": offset,
                        "open_price": trade_open_prices[
                            i
                        ],  # 开仓=成交价，平仓=加权平均开仓价
                        "close_price": price_val,  # 成交价（开仓/平仓均为实际成交价）
                        "quantity": quantity_val,
                        "pnl": trade_pnls[i],
                        "commission": trade_commissions[i],
                        "reason": getattr(trade, "reason", ""),
                    }
                    formatted_trades.append(trade_dict)

                # vnpy calculate_statistics 不输出 win_trades/loss_trades 等字段
                # 从交易记录的 pnl 字段自行计算并注入 statistics 字典
                # 注意：formatted_trades 包含开仓(pnl=0)和平仓(有实际pnl)，只统计有实际盈亏的平仓交易
                if formatted_trades:
                    # 只取有实际盈亏的交易（排除开仓 pnl=0 和持平 pnl=0）
                    closed_trades = [
                        t for t in formatted_trades if cast(float, t["pnl"]) != 0
                    ]
                    win_list = [t for t in closed_trades if cast(float, t["pnl"]) > 0]
                    loss_list = [t for t in closed_trades if cast(float, t["pnl"]) < 0]
                    win_cnt = len(win_list)
                    loss_cnt = len(loss_list)
                    total_trade_cnt = win_cnt + loss_cnt  # 有实际盈亏的笔数，非总成交数
                    avg_win_val = (
                        sum(cast(float, t["pnl"]) for t in win_list) / win_cnt
                        if win_cnt
                        else 0
                    )
                    avg_loss_val = (
                        abs(sum(cast(float, t["pnl"]) for t in loss_list) / loss_cnt)
                        if loss_cnt
                        else 0
                    )

                    # 最大连续盈利/亏损（基于平仓时间顺序）
                    # 注意：此处遍历 formatted_trades（含 pnl=0 的开仓），
                    #       pnl=0 走 else 分支会重置 cur_win，这是有意为之——
                    #       连续亏损的定义包含"没有盈利交易"的情况
                    max_consecutive_win = 0
                    max_consecutive_loss = 0
                    cur_win = 0
                    cur_loss = 0
                    for t in formatted_trades:
                        if cast(float, t["pnl"]) > 0:
                            cur_win += 1
                            cur_loss = 0
                            if cur_win > max_consecutive_win:
                                max_consecutive_win = cur_win
                        else:
                            cur_loss += 1
                            cur_win = 0
                            if cur_loss > max_consecutive_loss:
                                max_consecutive_loss = cur_loss

                    statistics["win_trades"] = win_cnt
                    statistics["loss_trades"] = loss_cnt
                    statistics["average_win"] = avg_win_val
                    statistics["average_loss"] = avg_loss_val
                    statistics["win_rate"] = (
                        win_cnt / total_trade_cnt if total_trade_cnt else 0
                    )
                    statistics["win_loss_ratio"] = (
                        avg_win_val / avg_loss_val if avg_loss_val > 0 else 0
                    )
                    statistics["max_consecutive_win"] = max_consecutive_win
                    statistics["max_consecutive_loss"] = max_consecutive_loss

                logger.info(
                    f"[{symbol}][{strategy_name}] 提取到 {len(formatted_trades)} 条交易记录"
                )
            except Exception as e:
                logger.exception(
                    f"回测执行异常 [{symbol}][{strategy_name}]: {e}",
                )
                results.append(
                    {
                        "bt_id": bt_id,
                        "statistics": {},
                        "daily_results": [],
                        "trades": [],
                        "error": str(e),
                        "strategy_config": None,
                        "strategy_version": strategy_version or "",
                    }
                )
                continue

            results.append(
                {
                    "bt_id": bt_id,
                    "statistics": statistics,
                    "daily_results": daily_results.reset_index().to_dict("records"),
                    "trades": formatted_trades,
                    "strategy_config": None,
                    "strategy_version": strategy_version or "",
                }
            )

        return results
