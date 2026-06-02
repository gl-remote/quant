# -*- coding: utf-8 -*-
"""
vn.py 回测引擎 (纯执行器)

基于 vnpy_ctastrategy.backtesting.BacktestingEngine，接收 DataFrame + 策略参数，
返回结构化回测结果。不负责数据加载和策略创建。

职责明确：
  - data 层负责数据加载
  - optimizer 层负责参数搜索
  - backtest 层仅调用 vnpy 执行回测
"""

from __future__ import annotations

import logging
import typing
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from strategies import Strategy, State
from strategies.utils import load_strategy, serialize_strategy_params
from config.app_config import BacktestConfig
from data.manager import DataManager

from common.formatting import parse_percentage
from common.formulas import profitable_ratio
from common.symbol_utils import parse_contract
from common.types import BacktestResult

if TYPE_CHECKING:
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Exchange, Interval

logger = logging.getLogger(__name__)


# ── 符号解析 & BarData 转换 ───────────────────────────────


def df_to_vnpy_datalines(
    df: pd.DataFrame,
    pure_symbol: str,
    exchange_code: str,
    interval: Interval | None = None,
) -> list[BarData]:
    """将 DataFrame 转换为 vn.py 回测引擎可用的 BarData 列表

    将 K 线 CSV (datetime, open, high, low, close, volume) 转换为
    vnpy BarData 对象列表，可直接注入 BacktestingEngine.history_data

    Args:
        df: K 线数据
        pure_symbol: 纯品种代号 (e.g. m2509)
        exchange_code: 交易所代码 (e.g. DCE)
        interval: vnpy Interval 枚举，None 时回退到 Interval.DAILY

    Returns:
        vnpy BarData 对象列表
    """
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Exchange, Interval

    required_cols = {'datetime', 'open', 'high', 'low', 'close', 'volume'}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"数据缺少必要列: {missing}")

    exchange: Exchange = Exchange(exchange_code)
    bar_interval: Interval = interval if interval is not None else Interval.DAILY

    bars: list[BarData] = [
        BarData(
            symbol=pure_symbol,
            exchange=exchange,
            datetime=pd.Timestamp(row['datetime']).to_pydatetime(),
            interval=bar_interval,
            open_price=row['open'],
            high_price=row['high'],
            low_price=row['low'],
            close_price=row['close'],
            volume=row['volume'],
            gateway_name="CSV",
        )
        for row in df.to_dict(orient='records')
    ]

    logger.info(f"转换完成: {len(bars)} 条 BarData")
    return bars


# ── Engine ───────────────────────────────────────────────


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
            logger.info(f"数据: {len(df)} 条, {data_start} ~ {data_end}")

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
            logger.info(f"\n>>> Walk-Forward 窗口 {wi + 1}/{len(windows)}")
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

        returns: list[float] = []
        sharpes: list[float] = []
        drawdowns: list[float] = []
        win_rates: list[float] = []
        is_returns: list[float] = []
        oos_returns: list[float] = []

        for w in window_results:
            stats = w.get('statistics', {})
            is_stats = w.get('statistics_is', {})
            returns.append(parse_percentage(stats.get('total_return', 0)))
            sharpes.append(float(stats.get('sharpe_ratio', 0)))
            drawdowns.append(parse_percentage(stats.get('max_drawdown', 0)))
            win_rates.append(parse_percentage(stats.get('win_rate', 0)))
            is_returns.append(parse_percentage(is_stats.get('total_return', 0)))
            oos_returns.append(parse_percentage(stats.get('total_return', 0)))

        arr_returns = np.array(returns, dtype=float)

        is_mean = float(np.mean(is_returns)) if is_returns else 0.0
        oos_mean = float(np.mean(oos_returns)) if oos_returns else 0.0

        aggregate = {
            'return_mean': float(np.mean(arr_returns)),
            'return_std': float(np.std(arr_returns)),
            'sharpe_mean': float(np.mean(sharpes)),
            'sharpe_std': float(np.std(sharpes)),
            'max_drawdown_mean': float(np.mean(drawdowns)),
            'max_drawdown_worst': float(np.max(drawdowns)),
            'win_rate_mean': float(np.mean(win_rates)),
            'win_rate_std': float(np.std(win_rates)),
            'positive_window_ratio': profitable_ratio(
                int(np.sum(arr_returns > 0)), len(arr_returns),
            ),
            'stability_score': float(max(0.0, min(
                1.0,
                1.0 - float(np.std(arr_returns)) / max(
                    abs(float(np.mean(arr_returns))), 1e-9
                ),
            ))),
            'is_oos_return_gap': is_mean - oos_mean,
        }

        logger.info(
            f"Walk-Forward 汇总 ({len(windows)} 窗口): "
            f"OOS均收益={aggregate['return_mean']:.2%}, "
            f"夏普={aggregate['sharpe_mean']:.2f}, "
            f"IS-OOS差距={aggregate['is_oos_return_gap']:.2%}, "
            f"盈利窗口比={aggregate['positive_window_ratio']:.0%}"
        )

        return {
            'success': True,
            'symbol': symbol,
            'windows': len(windows),
            'window_results': window_results,
            'aggregate': aggregate,
        }

    # ── 内部方法 ──────────────────────────────────────────────

    def _wrap_injected_strategy(
        self, strategy_name: str, strategy_params: dict[str, Any], symbol: str,
    ) -> type:
        """创建注入了策略实例和 State 的桥接器策略类

        Bridge 在 __init__ 中构造 Strategy 和 State。
        """
        from strategies.bridges import VnpyStrategyBridge

        _captured_name = strategy_name
        _captured_params = strategy_params
        _captured_symbol = symbol
        _captured_period = self.interval
        _captured_capital = self.initial_capital
        _captured_contract_size = self.contract_size

        class _InjectedStrategy(VnpyStrategyBridge):

            def _load_default_core(self, _setting: object | None = None) -> None:
                pass

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self._core = load_strategy(_captured_name)
                config_cls: type | None = None
                for base in getattr(type(self._core), '__orig_bases__', []):
                    origin = typing.get_origin(base)
                    if origin is not None and issubclass(origin, Strategy):
                        args = typing.get_args(base)
                        if args:
                            config_cls = args[0]
                            break
                if config_cls is None:
                    raise TypeError(
                        f"无法从 {type(self._core).__name__} 提取策略配置类型，"
                        f"请确保策略类继承自 Strategy[ConfigType]"
                    )
                strategy_config = config_cls(**_captured_params)
                self._state = State(
                    symbol=_captured_symbol,
                    period=_captured_period,
                    strategy_config=strategy_config,
                    capital=_captured_capital,
                    contract_size=_captured_contract_size,
                )

        return _InjectedStrategy

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
        from vnpy.trader.constant import Exchange, Interval

        c = parse_contract(symbol)
        if c is None:
            raise ValueError(f"无法解析合约代码: {symbol!r}")
        pure_symbol = c.contract_code
        exchange_code = c.exchange
        vt_symbol = f"{pure_symbol}.{Exchange(exchange_code).value}"

        _interval_map = {
            '1m': getattr(Interval, 'MINUTE', Interval.MINUTE),
            '5m': getattr(Interval, 'MINUTE_5', Interval.MINUTE),
            '15m': getattr(Interval, 'MINUTE_15', Interval.MINUTE),
            '30m': getattr(Interval, 'MINUTE_30', Interval.MINUTE),
            '1h': Interval.HOUR,
            'd': Interval.DAILY,
        }
        interval = _interval_map.get(self.interval, Interval.DAILY)

        bars = df_to_vnpy_datalines(df, pure_symbol, exchange_code, interval)

        results: list[dict[str, Any]] = []
        for strategy_name, strategy_params in zip(strategy_names, strategy_params_list):
            strategy_cls = self._wrap_injected_strategy(strategy_name, strategy_params, symbol)

            engine = BacktestingEngine()
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
                logger.error(
                    f"回测执行异常 [{symbol}][{strategy_name}]: {e}",
                    exc_info=True,
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
