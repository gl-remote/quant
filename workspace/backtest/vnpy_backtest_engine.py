"""vn.py 回测引擎（纯执行器）

基于 vnpy_ctastrategy.backtesting.BacktestingEngine，接收 DataFrame + 策略参数，
返回结构化回测结果。不负责数据加载和策略创建。

职责明确：
  - data_utils 负责数据转换
  - strategy_factory 负责策略创建
  - results 负责结果聚合
  - optimizer 负责参数搜索
  - backtest 层仅调用 vnpy 执行回测

重构说明（2026-06-06）：
  - 原 `_run_backtest` 约 160 行，混合引擎初始化、执行、交易解析、统计计算
  - 拆分为 `_prepare_vnpy_engine`、`_parse_trades`、`_calculate_trade_stats` 等子方法
  - `run_walk_forward` 拆分为窗口执行 + 聚合两步
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
from common.constants import DIRECTION_MAP, OFFSET_MAP
from common.contract_specs import CONTRACT_SPECS
from common.symbol_utils import parse_contract
from common.types import BacktestResult
from config.app_config import BacktestConfig
from loguru import logger
from strategies.utils import serialize_strategy_params

from .data_utils import append_synthetic_liquidation_bar, calculate_date_range, df_to_vnpy_datalines, resolve_interval
from .results import WalkForwardResult, WalkForwardWindowResult, aggregate_walk_forward
from .strategy_factory import create_strategy_class


class VnpyBacktestEngine:
    """vn.py 回测引擎（纯执行器）

    接收 DataFrame + 策略名称参数，调用 vnpy BacktestingEngine 执行回测，
    返回结构化结果字典。

    使用方式:
        engine = VnpyBacktestEngine(backtest_config, data_manager)
        results = engine.run(pairs)             # 多策略 × 多品种
        wf_result = engine.run_walk_forward(    # 单策略 Walk-Forward
            data, symbol, strategy_name, strategy_params, ...
        )
    """

    def __init__(self, backtest_config: BacktestConfig) -> None:
        """
        Args:
            backtest_config: 回测配置（含 capital/commission/slippage 等交易环境参数）
        """
        self._run_id: int | None = None
        self._git_hash: str | None = None
        self.initial_capital: float = float(backtest_config.initial_capital)
        self.commission_rate: float = float(backtest_config.commission_rate)
        self.slippage: float = float(backtest_config.slippage)
        self.price_tick: float = float(backtest_config.price_tick)
        self.contract_size: int = int(backtest_config.contract_size)
        self.interval: str = backtest_config.interval

        if self.initial_capital <= 0:
            raise ValueError(f"initial_capital 必须大于 0，当前: {self.initial_capital}")
        if not (0 <= self.commission_rate < 1):
            raise ValueError(f"commission_rate 必须在 [0, 1) 范围内，当前: {self.commission_rate}")
        if self.slippage < 0:
            raise ValueError(f"slippage 不能为负数，当前: {self.slippage}")
        if self.price_tick <= 0:
            raise ValueError(f"price_tick 必须大于 0，当前: {self.price_tick}")
        if self.contract_size <= 0:
            raise ValueError(f"contract_size 必须大于 0，当前: {self.contract_size}")

    def set_git_hash(self, git_hash: str | None) -> None:
        """设置 Git 提交哈希"""
        self._git_hash = git_hash

    def set_run_id(self, run_id: int | None) -> None:
        """设置当前运行记录 ID"""
        self._run_id = run_id

    # ── 结果构建辅助方法 ──────────────────────────────────

    def _create_backtest_result(
        self,
        symbol: str,
        backtest_id: int | None,
        strategy_name: str,
        strategy_version: str | None,
        strategy_params: dict[str, Any] | None,
        error: str | None,
        data_start: str,
        data_end: str,
        total_days: int,
        stats: dict[str, Any],
        daily_results: list[dict[str, Any]],
        trades: list[dict[str, Any]] | None = None,
    ) -> BacktestResult:
        """创建 BacktestResult 对象

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
            # ── 核心绩效指标（优先 vnpy，缺失时从成交自行计算）──
            total_trades=(
                stats.get("total_trade_count")
                or stats.get("total_trades")
                or (stats.get("win_trades", 0) + stats.get("loss_trades", 0))
            )
            or 0,
            total_return=stats.get("total_return", 0.0) or 0.0,
            end_balance=stats.get("end_balance", self.initial_capital) or self.initial_capital,
            annual_return=stats.get("annual_return"),
            sharpe_ratio=stats.get("sharpe_ratio"),
            max_drawdown=stats.get("max_drawdown"),
            max_ddpercent=stats.get("max_ddpercent"),
            max_drawdown_duration=stats.get("max_drawdown_duration", stats.get("max_ddpercent_duration", 0)),
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

    # ── 公开接口 ──────────────────────────────────────────

    def run(
        self,
        pairs: list[tuple[str, pd.DataFrame, str, dict[str, Any]]],
        batch_mode: bool = False,
    ) -> list[BacktestResult]:
        """执行多策略 × 多品种回测

        每个品种创建一个 vnpy engine，注册该品种的所有策略，一次回放拿到多组结果。

        Args:
            pairs: [(symbol, DataFrame, strategy_name, strategy_params), ...]
            batch_mode: True 时跳过 _create_placeholder_record（不写 DB），
                        由主进程统一入库。用于并行回测子进程。

        Returns:
            list[BacktestResult]
        """
        logger.info(f"{'=' * 60}")
        logger.info(f"启动 vn.py 回测: {len(pairs)} 个配对")
        logger.info(f"资金={self.initial_capital:,.0f} 费率={self.commission_rate:.4%} 滑点={self.slippage}")
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
            logger.debug(f"数据: {len(df)} 条, {data_start} ~ {data_end}, 共 {total_days} 天")

            batch_results = self._run_backtest(df, symbol, strategy_names, strategy_params_list, batch_mode=batch_mode)
            for i, r in enumerate(batch_results):
                stats = r.get("statistics", {})
                daily = r.get("daily_results", [])
                error = r.get("error")
                sym = symbols[i] if i < len(symbols) else symbol
                strategy_config = r.get("strategy_config")
                results.append(
                    self._create_backtest_result(
                        symbol=sym,
                        backtest_id=r.get("bt_id") if r.get("bt_id") != -1 else None,
                        strategy_name=strategy_names[i] if i < len(strategy_names) else "unknown",
                        strategy_version=r.get("strategy_version"),
                        strategy_params=serialize_strategy_params(strategy_config) if strategy_config else {},
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

    # ── Walk-Forward 支持 ────────────────────────────────

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
    ) -> WalkForwardResult:
        """执行 Walk-Forward 时间序列验证回测

        Args:
            data: K 线数据（已由调用方加载和日期过滤）
            symbol: 合约代码
            strategy_name: 策略名称
            strategy_params: 策略参数字典
            train_size/val_size/test_size/step: 窗口参数

        Returns:
            WalkForwardResult 强类型结果对象
        """
        from .walk_forward import walk_forward_split, walk_forward_split_by_ratio

        if data is None or data.empty:
            return WalkForwardResult(success=False, windows=0, error="数据为空")

        if train_size is not None and val_size is not None and test_size is not None:
            step_val = step or max(1, test_size // 2)
            windows = walk_forward_split(data, train_size, val_size, test_size, step_val)
        else:
            windows = walk_forward_split_by_ratio(data)

        if not windows:
            return WalkForwardResult(success=False, windows=0, error="无法生成窗口")

        logger.info(f"Walk-Forward: {len(windows)} 个窗口, {symbol}")

        window_results = self._execute_walk_forward_windows(windows, symbol, strategy_name, strategy_params)

        if not window_results:
            return WalkForwardResult(success=False, windows=len(windows), error="所有窗口回测失败")

        aggregate = aggregate_walk_forward(window_results)

        logger.info(
            f"Walk-Forward 汇总 ({len(windows)} 窗口): "
            f"OOS均收益={aggregate.return_mean:.2%}, "
            f"夏普={aggregate.sharpe_mean:.2f}, "
            f"IS-OOS差距={aggregate.is_oos_return_gap:.2%}, "
            f"盈利窗口比={aggregate.positive_window_ratio:.0%}"
        )

        return WalkForwardResult(
            success=True,
            symbol=symbol,
            windows=len(windows),
            window_results=window_results,
            aggregate=aggregate,
        )

    def _execute_walk_forward_windows(
        self,
        windows: list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]],
        symbol: str,
        strategy_name: str,
        strategy_params: dict[str, Any],
    ) -> list[WalkForwardWindowResult]:
        """执行 Walk-Forward 的所有窗口回测

        Args:
            windows: [(train_df, val_df, test_df), ...]
            symbol: 合约代码
            strategy_name: 策略名称
            strategy_params: 策略参数字典

        Returns:
            每个窗口的 WalkForwardWindowResult 列表
        """
        window_results: list[WalkForwardWindowResult] = []
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
                WalkForwardWindowResult(
                    window=wi,
                    train_rows=len(train_df),
                    val_rows=len(val_df),
                    test_rows=len(test_df),
                    train_start=str(train_df["datetime"].iloc[0])[:10],
                    train_end=str(train_df["datetime"].iloc[-1])[:10],
                    test_start=str(test_df["datetime"].iloc[0])[:10],
                    test_end=str(test_df["datetime"].iloc[-1])[:10],
                    statistics=test_result.get("statistics", {}),
                    statistics_is=train_result.get("statistics", {}),
                    daily_results=test_result.get("daily_results", []),
                    trades=test_result.get("trades", []),
                )
            )
        return window_results

    # ── 核心：单数据集回测 ────────────────────────────────

    def _run_backtest(
        self,
        df: pd.DataFrame,
        symbol: str,
        strategy_names: list[str],
        strategy_params_list: list[dict[str, Any]],
        batch_mode: bool = False,
    ) -> list[dict[str, Any]]:
        """在单个数据集上执行 vnpy 回测（主流程编排）

        拆分为: 合约解析 → 引擎准备 → 逐策略执行 → 结果收集

        Args:
            df: K 线数据
            symbol: 品种代码
            strategy_names: 策略名称列表
            strategy_params_list: 策略参数列表
            batch_mode: True 时跳过 _create_placeholder_record，bt_id 用 -1 占位，
                        用于并行回测子进程，结果回主进程统一入库。

        Returns:
            list[dict]，每个 dict 包含 statistics, daily_results, strategy_config, strategy_version 等
        """
        # ── 步骤 1: 合约解析 ─────────────────────────────
        c = parse_contract(symbol)
        if c is None:
            raise ValueError(f"无法解析合约代码: {symbol!r}")
        pure_symbol = c.contract_code
        exchange_code = c.exchange
        vt_symbol = c.vnpy_symbol

        # ── 步骤 2: 计算品种级参数（费率/滑点/合约乘数）───
        cs, pt, sl, mg, cr = self._resolve_contract_params(symbol, df)

        # ── 步骤 3: 数据准备 ───────────────────────────
        interval = resolve_interval(self.interval)
        real_bars = df_to_vnpy_datalines(df, pure_symbol, exchange_code, interval)
        bars = append_synthetic_liquidation_bar(real_bars)
        last_real_bar_time = pd.Timestamp(real_bars[-1].datetime) if real_bars else None
        data_start, data_end, total_days = calculate_date_range(df)

        # ── 步骤 4: 逐策略执行 ─────────────────────────
        results: list[dict[str, Any]] = []
        for strategy_name, strategy_params in zip(strategy_names, strategy_params_list, strict=False):
            strategy_version = self._get_strategy_version(strategy_name)

            if batch_mode:
                bt_id = -1
            else:
                bt_placeholder = self._create_placeholder_record(
                    symbol=symbol,
                    strategy_name=strategy_name,
                    strategy_version=strategy_version,
                    data_start=data_start,
                    data_end=data_end,
                    total_days=total_days,
                )
                bt_id = bt_placeholder.id

            # 创建 vnpy 引擎并执行回测
            # fail-fast（阶段 9）：单个回测的任何异常直接上抛，不再软着陆。
            # 回测失败说明存在严重问题，整个 run 应立即终止，由顶层
            # _handle_vnpy_failure 标记 run=failed + 落日志后非零退出。
            engine = self._prepare_vnpy_engine(
                vt_symbol=vt_symbol,
                full_symbol=symbol,
                interval=interval,
                start_dt=df["datetime"].iloc[0].to_pydatetime(),
                end_dt=df["datetime"].iloc[-1].to_pydatetime(),
                rate=0.0,
                slippage_val=sl,
                size=cs,
                pricetick=pt,
                capital=int(self.initial_capital),
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                bt_id=bt_id,
                margin=mg,
                last_real_bar_time=last_real_bar_time,
            )
            engine.history_data = bars

            with logger.contextualize(bt_id=f"|bt{bt_id}"):
                engine.run_backtesting()

            # ── 步骤 5: 解析 vnpy 输出 ─────────
            daily_results = engine.calculate_result()
            statistics = engine.calculate_statistics()

            # ── 步骤 6: 解析与格式化原始成交记录 ────
            formatted_trades = self._parse_trades(engine, symbol)

            # ── 步骤 7: 交易级清算统计由 clearing 域回填 ──

            # ── 步骤 8: 爆仓状态检测 ──
            # vnpy calculate_statistics() 在爆仓(balance≤0)时所有指标返回 0，
            # 此时从 daily_results 自行计算补上核心统计。
            if (
                statistics
                and not statistics.get("sharpe_ratio")
                and not statistics.get("max_drawdown")
                and not daily_results.empty
            ):
                logger.warning(f"[{symbol}] 检测到爆仓，从 daily_results 重新计算统计指标")
                _override_blown_up_stats(statistics, daily_results, self.initial_capital)

            logger.info(f"[{symbol}][{strategy_name}] 提取到 {len(formatted_trades)} 条交易记录")

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

    # ── 拆分出的子方法：合约参数解析 ──────────────────────

    def _resolve_contract_params(
        self,
        symbol: str,
        df: pd.DataFrame,
    ) -> tuple[float, float, float, float, float]:
        """解析品种参数（合约乘数/最小变动价位/滑点/保证金/费率）

        根据 CONTRACT_SPECS 表动态计算；缺失时回退到全局默认值。

        Returns:
            (contract_size, price_tick, slippage, margin, commission_rate)
        """
        spec = CONTRACT_SPECS.get_symbol(symbol)
        if spec is not None:
            cs = spec.size
            pt = spec.tick
            sl = spec.tick * spec.slip_tick
            mg = spec.margin
            # vnpy 只支持费率模式；真实手续费由 clearing 域统一计算。
            cr = 0.0
        else:
            cs = self.contract_size
            pt = self.price_tick
            sl = self.slippage
            mg = 0.1
            cr = 0.0
        return cs, pt, sl, mg, cr

    # ── 拆分出的子方法：获取策略版本 ─────────────────────

    @staticmethod
    def _get_strategy_version(strategy_name: str) -> str | None:
        """从策略类中获取版本号"""
        from strategies import load_strategy

        core = load_strategy(strategy_name)
        return getattr(type(core), "VERSION", None)

    # ── 拆分出的子方法：vnpy 引擎初始化 ─────────────────

    def _prepare_vnpy_engine(
        self,
        vt_symbol: str,
        full_symbol: str,
        interval: Any,
        start_dt: Any,
        end_dt: Any,
        rate: float,
        slippage_val: float,
        size: float,
        pricetick: float,
        capital: int,
        strategy_name: str,
        strategy_params: dict[str, Any],
        bt_id: int,
        margin: float,
        last_real_bar_time: pd.Timestamp | None,
    ) -> Any:
        """准备并返回 vnpy BacktestingEngine 实例

        负责: 创建 engine → 设置参数 → 注册策略 → 设置回调输出
        """
        from vnpy_ctastrategy.backtesting import BacktestingEngine

        engine = BacktestingEngine()

        # vnpy print → loguru，加上下文，丢进度条
        ctx = f"bt{bt_id}/{full_symbol}/{strategy_name}"
        params_summary = ", ".join(f"{k}={v}" for k, v in strategy_params.items())

        def _vnpy_output(msg: str, _ctx: str = ctx) -> None:
            if "回放进度" in msg:
                return
            logger.debug(f"[vnpy|{_ctx}] {msg}")

        engine.output = _vnpy_output
        logger.debug(f"[vnpy|{ctx}] 参数: {params_summary}")

        engine.set_parameters(
            vt_symbol=vt_symbol,
            interval=interval,
            start=start_dt,
            end=end_dt,
            rate=rate,
            slippage=slippage_val,
            size=size,
            pricetick=pricetick,
            capital=capital,
        )

        strategy_cls = create_strategy_class(
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            symbol=full_symbol,
            period=self.interval,
            capital=capital,
            contract_size=int(size),
            margin=margin,
            run_id=self._run_id or 0,
            backtest_id=bt_id,
            last_real_bar_time=last_real_bar_time,
        )
        engine.add_strategy(strategy_cls, {"price_tick": pricetick})

        return engine

    # ── 拆分出的子方法：交易记录解析与格式化 ─────────────

    def _parse_trades(
        self,
        engine: Any,
        symbol: str,
    ) -> list[dict[str, Any]]:
        """从 vnpy engine 中提取 raw fill 记录。"""
        trades_list: list[Any] = []
        if hasattr(engine, "trades"):
            trades_list = list(engine.trades.values())
        trades_list.sort(key=lambda t: t.datetime.timestamp() if t.datetime else 0)

        formatted_trades: list[dict[str, Any]] = []
        for trade in trades_list:
            dt = getattr(trade, "datetime", None)
            direction_val = getattr(trade, "direction", None)
            offset_val = getattr(trade, "offset", None)
            price_val = getattr(trade, "price", 0.0)
            quantity_val = getattr(trade, "volume", 0.0)
            raw_direction = (
                direction_val.value
                if direction_val is not None and hasattr(direction_val, "value")
                else str(direction_val)
            )
            raw_offset = (
                offset_val.value if offset_val is not None and hasattr(offset_val, "value") else str(offset_val)
            )
            direction = DIRECTION_MAP.get(raw_direction, raw_direction)
            offset = OFFSET_MAP.get(raw_offset, raw_offset)

            trade_dict = {
                "datetime": dt,
                "symbol": symbol,
                "direction": direction,
                "offset": offset,
                "price": price_val,
                "open_price": price_val,
                "close_price": price_val,
                "quantity": quantity_val,
                "pnl": 0.0,
                "commission": 0.0,
                "reason": getattr(trade, "reason", ""),
                "decision_payload_json": getattr(trade, "decision_payload_json", ""),
                "engine_trade_id": getattr(trade, "vt_tradeid", None) or getattr(trade, "tradeid", None),
                "engine_order_id": getattr(trade, "vt_orderid", None) or getattr(trade, "orderid", None),
                "raw_direction": raw_direction,
                "raw_offset": raw_offset,
            }
            formatted_trades.append(trade_dict)

        return formatted_trades

    # ── 拆分出的子方法：交易统计计算 ─────────────────────

    @staticmethod
    def _calculate_trade_stats(
        statistics: dict[str, Any],
        formatted_trades: list[dict[str, Any]],
    ) -> None:
        """从格式化后的交易记录计算胜率/平均盈亏/最大连盈连亏等指标

        修改输入的 statistics 字典，就地追加:
        - win_trades, loss_trades: 盈利/亏损的平仓交易数
        - average_win, average_loss: 平均盈利/亏损金额
        - win_rate: 胜率（盈利平仓数 / 总平仓数）
        - win_loss_ratio: 盈亏比（avg_win / abs(avg_loss)）
        - max_consecutive_win, max_consecutive_loss: 最大连续盈利/亏损次数

        Args:
            statistics: vnpy calculate_statistics 返回的字典
            formatted_trades: 已格式化的交易记录列表
        """
        if not formatted_trades:
            return

        # 统计盈亏数量时只纳入非零盈亏；连赢连亏序列遍历平仓交易，pnl=0 切断序列但不计入输赢。
        close_trades = [t for t in formatted_trades if t.get("offset") != "open"]
        non_zero_trades = [t for t in close_trades if cast(float, t["pnl"]) != 0]
        win_list = [t for t in non_zero_trades if cast(float, t["pnl"]) > 0]
        loss_list = [t for t in non_zero_trades if cast(float, t["pnl"]) < 0]
        win_cnt = len(win_list)
        loss_cnt = len(loss_list)
        total_trade_cnt = win_cnt + loss_cnt

        avg_win_val = sum(cast(float, t["pnl"]) for t in win_list) / win_cnt if win_cnt else 0
        avg_loss_val = abs(sum(cast(float, t["pnl"]) for t in loss_list) / loss_cnt) if loss_cnt else 0

        # 最大连续盈利/亏损（基于交易时间顺序）
        max_consecutive_win = 0
        max_consecutive_loss = 0
        cur_win = 0
        cur_loss = 0
        for t in close_trades:
            if cast(float, t["pnl"]) > 0:
                cur_win += 1
                cur_loss = 0
                if cur_win > max_consecutive_win:
                    max_consecutive_win = cur_win
            elif cast(float, t["pnl"]) < 0:
                cur_loss += 1
                cur_win = 0
                if cur_loss > max_consecutive_loss:
                    max_consecutive_loss = cur_loss
            else:
                cur_win = 0
                cur_loss = 0

        statistics["win_trades"] = win_cnt
        statistics["loss_trades"] = loss_cnt
        statistics["average_win"] = avg_win_val
        statistics["average_loss"] = avg_loss_val
        statistics["win_rate"] = win_cnt / total_trade_cnt if total_trade_cnt else 0
        statistics["win_loss_ratio"] = avg_win_val / avg_loss_val if avg_loss_val > 0 else 0
        statistics["max_consecutive_win"] = max_consecutive_win
        statistics["max_consecutive_loss"] = max_consecutive_loss


def _override_blown_up_stats(
    statistics: dict[str, Any],
    daily_df: pd.DataFrame,
    capital: float,
) -> None:
    """vnpy 爆仓时所有统计指标为 0，从 daily_results 自行计算补上

    不修改传入 statistics 中已有的 win/loss/win_rate 等自行计算字段，
    仅覆盖 vnpy 因爆仓跳过而未正确计算的核心统计字段。

    Args:
        statistics: vnpy calculate_statistics() 返回的字典，被就地修改
        daily_df: calculate_result() 返回的 DataFrame（列: net_pnl, commission, slippage, turnover, trade_count）
        capital: 初始资金
    """
    if daily_df is None or daily_df.empty:
        return

    df = daily_df.copy()
    required_cols = {"net_pnl", "commission", "slippage", "turnover", "trade_count"}
    if not required_cols.issubset(df.columns):
        return

    # ── 计算衍生列 ──
    df["balance"] = df["net_pnl"].cumsum() + capital
    # 爆仓场景下 balance 会穿越 0 变为负值，几何收益 log(balance_t / balance_{t-1})
    # 在「负÷负=正」时会算出错误的正收益，导致巨亏账户得到正 Sharpe。
    # 改用以初始资金为不变基数的算术日收益，符号始终正确。
    df["return"] = df["net_pnl"] / capital
    df["highlevel"] = df["balance"].cummax()
    df["drawdown"] = df["balance"] - df["highlevel"]
    df["ddpercent"] = np.where(df["highlevel"] > 0, df["drawdown"] / df["highlevel"] * 100, 0.0)

    total_days = len(df)
    end_balance = float(df["balance"].iloc[-1])
    total_return = (end_balance / capital - 1) * 100
    annual_days = 252.0
    annual_return = total_return / total_days * annual_days if total_days else 0.0
    daily_return_mean = float(df["return"].mean() * 100)
    return_std = float(df["return"].std() * 100)

    # ── 覆盖 vnpy 返回的 0 值 ──
    statistics["end_balance"] = end_balance
    statistics["total_return"] = total_return
    statistics["annual_return"] = annual_return
    statistics["total_net_pnl"] = float(df["net_pnl"].sum())
    statistics["daily_net_pnl"] = float(df["net_pnl"].sum() / total_days) if total_days else 0.0
    statistics["total_commission"] = float(df["commission"].sum())
    statistics["daily_commission"] = float(df["commission"].sum() / total_days) if total_days else 0.0
    statistics["total_slippage"] = float(df["slippage"].sum())
    statistics["daily_slippage"] = float(df["slippage"].sum() / total_days) if total_days else 0.0
    statistics["total_turnover"] = float(df["turnover"].sum())
    statistics["daily_turnover"] = float(df["turnover"].sum() / total_days) if total_days else 0.0
    statistics["profit_days"] = int((df["net_pnl"] > 0).sum())
    statistics["loss_days"] = int((df["net_pnl"] < 0).sum())
    statistics["total_trade_count"] = int(df["trade_count"].sum())
    statistics["daily_trade_count"] = float(df["trade_count"].sum() / total_days) if total_days else 0.0
    statistics["max_drawdown"] = float(df["drawdown"].min())
    statistics["max_ddpercent"] = float(df["ddpercent"].min())
    statistics["daily_return"] = daily_return_mean
    statistics["return_std"] = return_std
    statistics["sharpe_ratio"] = daily_return_mean / return_std * (annual_days**0.5) if return_std > 0 else 0.0
    max_ddpercent = statistics.get("max_ddpercent", 0) or 0
    statistics["return_drawdown_ratio"] = -total_return / max_ddpercent if max_ddpercent else 0.0
