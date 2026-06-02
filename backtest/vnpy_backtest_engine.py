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
from typing import TYPE_CHECKING, Any

import pandas as pd

from strategies.utils import serialize_strategy_params
from config.app_config import BacktestConfig
from data.manager import DataManager

from .data_utils import df_to_vnpy_datalines, resolve_interval
from .results import aggregate_walk_forward
from .strategy_factory import create_strategy_class

from common.symbol_utils import parse_contract
from common.types import BacktestResult

if TYPE_CHECKING:
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Exchange, Interval

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
        logger.info(f"资金={self.initial_capital:,.0f} "
                    f"费率={self.commission_rate:.4%} 滑点={self.slippage}")
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

            data_start = str(df['datetime'].iloc[0])[:10]
            data_end = str(df['datetime'].iloc[-1])[:10]
            logger.debug(f"数据: {len(df)} 条, {data_start} ~ {data_end}")

            batch_results = self._run_backtest(df, symbol, strategy_names, strategy_params_list)
            for i, r in enumerate(batch_results):
                stats = r.get('statistics', {})
                daily = r.get('daily_results', [])
                error = r.get('error')
                sym = symbols[i] if i < len(symbols) else symbol
                strategy_config = r.get('strategy_config')
                results.append(BacktestResult(
                    symbol=sym,
                    strategy=strategy_names[i] if i < len(strategy_names) else "unknown",
                    strategy_version=r.get('strategy_version'),
                    strategy_params=serialize_strategy_params(strategy_config) if strategy_config else {},
                    success=error is None,
                    error_message=error,
                    start_date=data_start,
                    end_date=data_end,
                    total_trades=stats.get('total_trades', 0) or 0,
                    total_return=stats.get('total_return', 0.0) or 0.0,
                    end_balance=stats.get('end_balance', self.initial_capital) or self.initial_capital,
                    annual_return=stats.get('annual_return'),
                    win_trades=stats.get('profit_days', stats.get('win_trades', 0)) or 0,
                    loss_trades=stats.get('loss_days', stats.get('loss_trades', 0)) or 0,
                    win_rate=stats.get('win_rate'),
                    max_consecutive_win=stats.get('max_consecutive_win'),
                    max_consecutive_loss=stats.get('max_consecutive_loss'),
                    avg_win=stats.get('average_win'),
                    avg_loss=stats.get('average_loss'),
                    win_loss_ratio=stats.get('win_loss_ratio'),
                    sharpe_ratio=stats.get('sharpe_ratio'),
                    max_drawdown=stats.get('max_drawdown'),
                    max_drawdown_duration=stats.get('max_drawdown_duration', stats.get('max_ddpercent_duration', 0)),
                    daily_std=stats.get('return_std', stats.get('daily_std')),
                    return_drawdown_ratio=stats.get('return_drawdown_ratio'),
                    initial_capital=self.initial_capital,
                    commission_rate=self.commission_rate,
                    slippage=self.slippage,
                    price_tick=self.price_tick,
                    contract_size=self.contract_size,
                    kline_interval=self.interval,
                    daily_results=daily if daily else [],
                ))

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
            return {'success': False, 'error': '数据为空', 'windows': 0}

        if train_size is not None and val_size is not None and test_size is not None:
            step_val = step or max(1, test_size // 2)
            windows = walk_forward_split(data, train_size, val_size, test_size, step_val)
        else:
            windows = walk_forward_split_by_ratio(data)

        if not windows:
            return {'success': False, 'error': '无法生成窗口', 'windows': 0}

        logger.info(f"Walk-Forward: {len(windows)} 个窗口, {symbol}")

        window_results = []
        for wi, (train_df, val_df, test_df) in enumerate(windows):
            logger.debug(f"\n>>> Walk-Forward 窗口 {wi + 1}/{len(windows)}")
            train_results = self._run_backtest(
                train_df, symbol, [strategy_name], [strategy_params],
            )
            test_results = self._run_backtest(
                test_df, symbol, [strategy_name], [strategy_params],
            )

            train_result = train_results[0] if train_results else {}
            test_result = test_results[0] if test_results else {}

            if 'error' in train_result or 'error' in test_result:
                logger.warning(
                    f"窗口 {wi + 1} 回测异常，跳过: "
                    f"train_error={train_result.get('error')}, "
                    f"test_error={test_result.get('error')}"
                )
                continue

            window_results.append({
                'window': wi,
                'train_rows': len(train_df),
                'val_rows': len(val_df),
                'test_rows': len(test_df),
                'train_start': str(train_df['datetime'].iloc[0])[:10],
                'train_end': str(train_df['datetime'].iloc[-1])[:10],
                'test_start': str(test_df['datetime'].iloc[0])[:10],
                'test_end': str(test_df['datetime'].iloc[-1])[:10],
                'statistics': test_result.get('statistics', {}),
                'statistics_is': train_result.get('statistics', {}),
            })

        aggregate = aggregate_walk_forward(window_results)

        logger.info(
            f"Walk-Forward 汇总 ({len(windows)} 窗口): "
            f"OOS均收益={aggregate.return_mean:.2%}, "
            f"夏普={aggregate.sharpe_mean:.2f}, "
            f"IS-OOS差距={aggregate.is_oos_return_gap:.2%}, "
            f"盈利窗口比={aggregate.positive_window_ratio:.0%}"
        )

        return {
            'success': True,
            'symbol': symbol,
            'windows': len(windows),
            'window_results': window_results,
            'aggregate': aggregate.to_dict(),
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

        results: list[dict[str, Any]] = []
        for strategy_name, strategy_params in zip(strategy_names, strategy_params_list):
            strategy_cls = create_strategy_class(
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                symbol=symbol,
                period=self.interval,
                capital=self.initial_capital,
                contract_size=self.contract_size,
            )

            engine = BacktestingEngine()
            engine.output = lambda msg: logger.debug(f"[vnpy] {msg}")  # 重定向 print 到 loguru
            engine.set_parameters(
                vt_symbol=vt_symbol,
                interval=interval,
                start=df['datetime'].iloc[0].to_pydatetime(),
                end=df['datetime'].iloc[-1].to_pydatetime(),
                rate=self.commission_rate,
                slippage=self.slippage,
                size=self.contract_size,
                pricetick=self.price_tick,
                capital=int(self.initial_capital),
            )
            engine.add_strategy(strategy_cls, {'price_tick': self.price_tick})
            engine.history_data = bars

            try:
                engine.run_backtesting()
                daily_results = engine.calculate_result()
                statistics = engine.calculate_statistics()
            except Exception as e:
                logger.exception(
                    f"回测执行异常 [{symbol}][{strategy_name}]: {e}",
                )
                results.append({
                    'statistics': {},
                    'daily_results': [],
                    'error': str(e),
                    'strategy_config': None,
                    'strategy_version': '',
                })
                continue

            results.append({
                'statistics': statistics,
                'daily_results': (
                    daily_results.reset_index().to_dict('records')
                    if daily_results is not None
                    else []
                ),
                'strategy_config': None,
                'strategy_version': '',
            })

        return results