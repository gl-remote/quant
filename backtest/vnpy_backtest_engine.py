# -*- coding: utf-8 -*-
"""
vn.py 批量回测引擎

基于 vnpy_ctastrategy.backtesting.BacktestingEngine 的回测流水线，
封装数据加载 → 全量回测 → 报告生成。

职责明确：
  - TQBacktestEngine:   单标的图形化分析 (天勤 TqSdk)
  - VnpyBacktestEngine: 批量回测流水线 (vn.py)
"""

import logging
from typing import Any, Optional

import numpy as np

from strategies.core.context import TradingContext

from .data_loader import load_csv_data, df_to_vnpy_datalines, parse_symbol_exchange, filter_dataframe_by_date
from .report import generate_dataset_report, format_console_report
from .aggregator import aggregate_walk_forward, parse_percentage

logger = logging.getLogger(__name__)


class VnpyBacktestEngine:
    """vn.py 批量回测引擎

    基于 vnpy_ctastrategy.backtesting.BacktestingEngine 的回测流水线，
    封装数据加载 → 全量单次回测 → 报告生成。
    Walk-Forward 作为稳健性分析独立提供。

    使用方式:
        engine = VnpyBacktestEngine(config, context=context)
        result = engine.run_full_pipeline(symbol)          # 单次全量回测
        wf_result = engine.run_walk_forward(symbol)        # Walk-Forward 验证
    """

    def __init__(self, config: dict[str, Any], context: Optional[TradingContext] = None):
        """
        Args:
            config: 回测配置字典，结构参考 conf.yaml 中 backtest 段
            context: 交易上下文 (可选)，提供策略实例和交易参数
        """
        self.context = context

        if context is not None:
            self.initial_capital = context.capital
            self.commission_rate = context.commission_rate
            self.slippage = context.slippage
            self.price_tick = context.price_tick
            self.contract_size = context.contract_size
        else:
            self.initial_capital: float = float(config.get('initial_capital', 100000.0))
            self.commission_rate: float = float(config.get('commission_rate', 0.0003))
            self.slippage: float = float(config.get('slippage', 1.0))
            self.price_tick: float = float(config.get('price_tick', 1.0))
            self.contract_size: int = int(config.get('contract_size', 10))

        self.data_dir: str = config.get('data_dir', '.quant_shared_data/csv')
        self.interval: str = config.get('interval', '1m')

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

        report_cfg = config.get('report', {})
        self.report_dir: str = report_cfg.get('output_dir', '.quant_shared_data/reports')
        self.save_trades: bool = report_cfg.get('save_trade_records', True)
        self.save_equity: bool = report_cfg.get('save_equity_curve', True)

    def _wrap_injected_strategy(self, base_cls):
        """创建包装了上下文的桥接器策略类

        _InjectedStrategy 覆写 _load_default_core 为 no-op，
        在 __init__ 返回后直接注入 _core 和 price_tick，
        避免 bridge 的 __init__ 感知 context 参数。
        """
        ctx = getattr(self, '_backtest_context', self.context)

        class _InjectedStrategy(base_cls):
            def _load_default_core(inner_self, setting):
                pass

            def __init__(inner_self, cta_engine, strategy_name, vt_symbol, setting):
                super().__init__(cta_engine, strategy_name, vt_symbol, setting)
                inner_self.price_tick = ctx.price_tick
                inner_self._core = ctx.strategy

        return _InjectedStrategy

    def run_full_pipeline(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """执行完整的回测流水线

        流水线步骤:
          1. 加载CSV数据
          2. 全量单次回测
          3. 生成报告

        Args:
            symbol: 合约代码 (e.g. DCE.m2509)
            start_date: 数据起始日期 (可选过滤)
            end_date: 数据结束日期 (可选过滤)

        Returns:
            回测结果字典，包含:
              - report: 结构化报告 (performance / risk / trades)
              - result: 原始 vnpy 回测结果 (statistics / daily_results)
        """
        logger.info(f"{'=' * 60}")
        logger.info(f"启动 vn.py 回测: {symbol}")
        logger.info(f"资金={self.initial_capital:,.0f} "
                     f"费率={self.commission_rate:.4%} 滑点={self.slippage}")
        logger.info(f"{'=' * 60}")

        # ---- 步骤1: 加载数据 ----
        df = load_csv_data(self.data_dir, symbol)
        if df is None or df.empty:
            logger.error("数据加载失败，终止回测")
            return {'success': False, 'error': '数据加载失败'}

        df = filter_dataframe_by_date(df, start_date, end_date)
        data_start = str(df['datetime'].iloc[0])[:10]
        data_end = str(df['datetime'].iloc[-1])[:10]
        logger.info(f"数据加载完成: {len(df)} 条, "
                     f"{df['datetime'].iloc[0]} ~ {df['datetime'].iloc[-1]}")

        # ---- 步骤2: 全量回测 ----
        logger.info("\n>>> 执行全量回测")
        result = self._run_backtest(df, symbol, 'full')

        # ---- 步骤3: 生成报告 ----
        logger.info("\n>>> 生成回测报告")
        report = self._format_and_save_report(result, symbol, 'full')

        return {
            'success': True,
            'symbol': symbol,
            'result': result,
            'report': report,
            'data_start_date': data_start,
            'data_end_date': data_end,
            'engine_config': {
                'initial_capital': self.initial_capital,
                'commission_rate': self.commission_rate,
                'slippage': self.slippage,
                'price_tick': self.price_tick,
                'contract_size': self.contract_size,
                'kline_interval': self.interval,
            },
        }

    def run_walk_forward(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        train_size: Optional[int] = None,
        val_size: Optional[int] = None,
        test_size: Optional[int] = None,
        step: Optional[int] = None,
    ) -> dict[str, Any]:
        """执行 Walk-Forward 时间序列验证回测 (固定参数, 无优化)

        对数据滚动产生多个窗口，每个窗口在训练集(in-sample)和测试集
        (out-of-sample)上分别回测，最后汇总 OOS 平均表现。相比单次全量
        回测，Walk-Forward 能:
          - 模拟策略在时间推进中的实际表现
          - 评估策略稳健性（各窗口指标的标准差）
          - 对比 IS-OOS 差距识别过拟合风险

        Args:
            symbol: 合约代码
            start_date/end_date: 数据过滤
            train_size/val_size/test_size/step: 窗口参数，
                为 None 时按比例自动计算 (60%/20%/20%, step=10%)

        Returns:
            walk_forward 结果字典:
              - windows: 窗口数
              - window_results: 各窗口 IS/OOS 指标列表
              - aggregate: OOS 聚合统计 + IS-OOS 差距
        """
        from .data_loader import walk_forward_split_by_ratio, walk_forward_split

        df = load_csv_data(self.data_dir, symbol)
        if df is None or df.empty:
            return {'success': False, 'error': '数据加载失败', 'windows': 0}

        df = filter_dataframe_by_date(df, start_date, end_date)

        if train_size is not None and val_size is not None and test_size is not None:
            step_val = step or max(1, test_size // 2)
            windows = walk_forward_split(df, train_size, val_size, test_size, step_val)
        else:
            windows = walk_forward_split_by_ratio(df)

        if not windows:
            return {'success': False, 'error': '无法生成窗口', 'windows': 0}

        logger.info(f"Walk-Forward: {len(windows)} 个窗口, {symbol}")

        window_results = []
        for wi, (train_df, val_df, test_df) in enumerate(windows):
            logger.info(f"\n>>> Walk-Forward 窗口 {wi + 1}/{len(windows)}")
            # In-Sample: 训练集上回测 (观察策略在该时间段的表现)
            train_result = self._run_backtest(train_df, symbol, f'wf_{wi}_train')
            if self.context and self.context.strategy:
                self.context.strategy.reset()
            # Out-of-Sample: 测试集上回测 (真正评估预测能力)
            test_result = self._run_backtest(test_df, symbol, f'wf_{wi}_test')
            if self.context and self.context.strategy:
                self.context.strategy.reset()
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

        # 聚合所有窗口的 OOS 测试集指标
        aggregate = aggregate_walk_forward(window_results)

        # 计算 IS-OOS 平均差距 (过拟合检测)
        is_returns = [
            parse_percentage(w.get('statistics_is', {}).get('total_return', 0))
            for w in window_results
        ]
        oos_returns = [
            parse_percentage(w.get('statistics', {}).get('total_return', 0))
            for w in window_results
        ]
        is_mean = float(np.mean(is_returns)) if is_returns else 0.0
        oos_mean = float(np.mean(oos_returns)) if oos_returns else 0.0
        aggregate['is_oos_return_gap'] = is_mean - oos_mean

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

    def _build_setting(self) -> dict[str, Any]:
        return {'price_tick': self.price_tick}

    def _run_backtest(
        self,
        df: 'pd.DataFrame',
        symbol: str,
        dataset_name: str,
    ) -> dict[str, Any]:
        """在单个数据集上执行 vnpy 回测"""
        from vnpy_ctastrategy.backtesting import BacktestingEngine
        from vnpy.trader.constant import Interval
        from strategies.bridges import VnpyStrategyBridge

        pure_symbol, exchange_code = parse_symbol_exchange(symbol)
        vt_symbol = f"{pure_symbol}.{exchange_code}"

        # 优先使用 vnpy 细分 Interval (MINUTE_5/MINUTE_15 等)，不存在则回退到 MINUTE
        _interval_map = {
            '1m': getattr(Interval, 'MINUTE', Interval.MINUTE),
            '5m': getattr(Interval, 'MINUTE_5', Interval.MINUTE),
            '15m': getattr(Interval, 'MINUTE_15', Interval.MINUTE),
            '30m': getattr(Interval, 'MINUTE_30', Interval.MINUTE),
            '1h': Interval.HOUR,
            'd': Interval.DAILY,
        }
        interval = _interval_map.get(self.interval, Interval.DAILY)

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

        setting = self._build_setting()

        if self.context is None:
            from strategies.ma_strategy import MaStrategyCore, TradingConfig
            from strategies.core.context import TradingContext
            strategy = MaStrategyCore(TradingConfig(
                capital=self.initial_capital,
                contract_size=self.contract_size,
            ))
            local_context = TradingContext(
                strategy=strategy,
                symbol=vt_symbol,
                capital=self.initial_capital,
                price_tick=self.price_tick,
            )
        else:
            local_context = self.context

        local_context.strategy.reset()

        # 临时挂到 self 上供 _wrap_injected_strategy 的闭包捕获
        self._backtest_context = local_context
        strategy_cls = self._wrap_injected_strategy(VnpyStrategyBridge)
        engine.add_strategy(strategy_cls, setting)

        bars = df_to_vnpy_datalines(df, vt_symbol, interval)
        engine.history_data = bars

        engine.run_backtesting()
        daily_results = engine.calculate_result()
        statistics = engine.calculate_statistics()

        return {
            'dataset_name': dataset_name,
            'statistics': statistics,
            'daily_results': daily_results.to_dict('records') if daily_results is not None else [],
        }

    def _format_and_save_report(
        self,
        result: dict[str, Any],
        symbol: str,
        dataset_name: str,
    ) -> dict[str, Any]:
        """格式化并保存单个数据集报告"""
        report = generate_dataset_report(
            statistics=result.get('statistics', {}),
            daily_results=result.get('daily_results', []),
            dataset_name=dataset_name,
            symbol=symbol,
            initial_capital=self.initial_capital,
            output_dir=self.report_dir,
            save_trades=self.save_trades,
            save_equity=self.save_equity,
        )

        console_report = format_console_report(report, f"[{symbol}]")
        print(console_report)
        return report
