"""回测引擎模块

提供两套职责清晰的回测引擎:

  TQBacktestEngine  — 天勤单标的图形化回测 (配合 TqSdk GUI)
    - 交易记录与资金曲线跟踪
    - 绩效指标计算 (胜率/夏普/最大回撤)
    - 文本报告生成
    - 用于 tq-backtest 实盘/模拟模式

  VnpyBacktestEngine — vn.py 批量回测流水线
    - CSV 数据加载 + 训练/验证/测试集划分
    - 三阶段独立回测 (委托 vnpy_ctastrategy.backtesting.BacktestingEngine)
    - 报告生成与三阶段对比分析
    - Walk-Forward 时间序列交叉验证

vn.py 为强制依赖。
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import numpy as np

from .data_loader import load_csv_data, split_datasets, df_to_vnpy_datalines, get_dataset_info
from .data_loader import parse_symbol_exchange
from .report import generate_dataset_report, format_console_report
from .comparison import compare_datasets, format_comparison_report
from strategies.core.context import TradingContext

logger = logging.getLogger(__name__)


# ============================================================
# 天勤回测引擎 — 单标的图形窗口展示 (tq-backtest)
# ============================================================

@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: datetime
    symbol: str
    direction: str
    price: float
    quantity: int
    profit: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    """回测结果"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    final_equity: float = 0.0


class TQBacktestEngine:
    """天勤回测引擎 — 单标的图形窗口展示

    用于 tq-backtest 实盘/模拟模式的交易跟踪：
    - 记录每笔交易、计算资金曲线、生成绩效指标
    - 配合天勤 TqSdk 的图形界面使用，提供直观的回测结果可视化

    职责明确：
      - TQBacktestEngine:  单标的图形化分析 (天勤 TqSdk)
      - VnpyBacktestEngine: 批量回测流水线 (vn.py)
    """

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.current_position = 0
        self.entry_price = 0.0
        self.trade_history: List[TradeRecord] = []
        self.equity_curve: List[float] = [initial_capital]
        self.max_equity = initial_capital

    def add_trade(self, trade: TradeRecord):
        self.trade_history.append(trade)
        if trade.direction == 'buy':
            self.current_position += trade.quantity
            self.entry_price = trade.price
            self.current_capital -= trade.price * trade.quantity
        elif trade.direction == 'sell':
            self.current_position -= trade.quantity
            self.current_capital += trade.price * trade.quantity + trade.profit

        equity = self.current_capital + (self.current_position * self.entry_price
                                          if self.current_position > 0 else 0)
        self.equity_curve.append(equity)
        if equity > self.max_equity:
            self.max_equity = equity

    def calculate_metrics(self) -> BacktestResult:
        result = BacktestResult()
        result.final_equity = self.equity_curve[-1] if self.equity_curve else self.initial_capital
        if not self.trade_history:
            return result

        sells = [t for t in self.trade_history if t.direction == 'sell']
        result.total_trades = len(sells)
        winning = [t for t in sells if t.profit > 0]
        losing = [t for t in sells if t.profit < 0]
        result.winning_trades = len(winning)
        result.losing_trades = len(losing)
        if result.total_trades > 0:
            result.win_rate = result.winning_trades / result.total_trades
        result.total_profit = sum(t.profit for t in sells)
        if winning:
            result.avg_profit = sum(t.profit for t in winning) / len(winning)
        if losing:
            result.avg_loss = sum(t.profit for t in losing) / len(losing)
        result.max_drawdown = self._calc_max_drawdown()
        if result.avg_loss != 0:
            result.profit_factor = abs(result.avg_profit / result.avg_loss)
        result.sharpe_ratio = self._calc_sharpe_ratio()
        return result

    def _calc_max_drawdown(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for equity in self.equity_curve[1:]:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _calc_sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        returns = np.diff(self.equity_curve) / np.array(self.equity_curve[:-1])
        if len(returns) == 0:
            return 0.0
        std = np.std(returns)
        return 0.0 if std == 0 else (np.mean(returns) / std) * np.sqrt(252)

    def generate_report(self) -> str:
        r = self.calculate_metrics()
        return (
            f"{'=' * 60}\n"
            f"回测报告\n"
            f"{'=' * 60}\n"
            f"初始资金: {self.initial_capital:,.2f}\n"
            f"最终资金: {r.final_equity:,.2f}\n"
            f"总收益率: {((r.final_equity - self.initial_capital) / self.initial_capital):.2%}\n\n"
            f"交易统计:\n"
            f"  总交易次数: {r.total_trades}\n"
            f"  盈利交易: {r.winning_trades}\n"
            f"  亏损交易: {r.losing_trades}\n"
            f"  胜率: {r.win_rate:.2%}\n\n"
            f"盈亏统计:\n"
            f"  总盈亏: {r.total_profit:,.2f}\n"
            f"  平均盈利: {r.avg_profit:,.2f}\n"
            f"  平均亏损: {r.avg_loss:,.2f}\n"
            + (f"  盈亏比: {r.profit_factor:.2f}\n" if r.profit_factor > 0 else "") +
            f"  最大回撤: {r.max_drawdown:.2%}\n"
            f"  夏普比率: {r.sharpe_ratio:.2f}\n"
            f"{'=' * 60}"
        )


# ============================================================
# vn.py 批量回测引擎
# ============================================================

class VnpyBacktestEngine:
    """vn.py 批量回测引擎

    基于 vnpy_ctastrategy.backtesting.BacktestingEngine 的回测流水线，
    封装数据加载 → 划分 → 单标的回测 → 报告生成。

    使用方式:
        engine = VnpyBacktestEngine(config, context=context)
        result = engine.run_full_pipeline(symbol)  # 单品种

    职责明确：
      - TQBacktestEngine:   单标的图形化分析 (天勤 TqSdk)
      - VnpyBacktestEngine: 批量回测流水线 (vn.py)
    """

    def __init__(self, config: Dict[str, Any], context: Optional[TradingContext] = None):
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

        split_cfg = config.get('split', {})
        self.train_ratio: float = split_cfg.get('train_ratio', 0.6)
        self.val_ratio: float = split_cfg.get('val_ratio', 0.2)
        self.test_ratio: float = split_cfg.get('test_ratio', 0.2)
        self.random_seed: int = split_cfg.get('random_seed', 42)
        self.shuffle: bool = split_cfg.get('shuffle', False)

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
        ctx = self.context

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
    ) -> Dict[str, Any]:
        """执行完整的回测流水线

        流水线步骤:
          1. 加载CSV数据
          2. 划分为训练/验证/测试集
          3. 三阶段独立回测
          4. 分别生成报告
          5. 对比分析

        Args:
            symbol: 合约代码 (e.g. DCE.m2509)
            start_date: 数据起始日期 (可选过滤)
            end_date: 数据结束日期 (可选过滤)

        Returns:
            完整回测结果字典，包含:
              - datasets: 数据集信息
              - train/val/test_results: 各阶段回测统计
              - comparison: 三阶段对比分析
        """
        logger.info(f"{'=' * 60}")
        logger.info(f"启动 vn.py 回测流水线: {symbol}")
        logger.info(f"资金={self.initial_capital:,.0f} "
                     f"费率={self.commission_rate:.4%} 滑点={self.slippage}")
        logger.info(f"{'=' * 60}")

        # ---- 步骤1: 加载数据 ----
        df = load_csv_data(self.data_dir, symbol)
        if df is None or df.empty:
            logger.error("数据加载失败，终止回测")
            return {'success': False, 'error': '数据加载失败'}

        if start_date:
            df = df[df['datetime'] >= start_date]
        if end_date:
            df = df[df['datetime'] <= end_date]
        df = df.reset_index(drop=True)
        logger.info(f"数据过滤后: {len(df)} 条")

        # ---- 步骤2: 划分数据集 ----
        train_df, val_df, test_df = split_datasets(
            df,
            train_ratio=self.train_ratio,
            val_ratio=self.val_ratio,
            test_ratio=self.test_ratio,
            random_seed=self.random_seed,
            shuffle=self.shuffle,
        )

        datasets_info = {
            'train': get_dataset_info(train_df, 'train'),
            'val': get_dataset_info(val_df, 'val'),
            'test': get_dataset_info(test_df, 'test'),
        }

        # ---- 步骤3: 三阶段回测 ----
        logger.info("\n>>> 阶段一: 训练集回测")
        train_result = self._run_backtest(train_df, symbol, 'train')

        logger.info("\n>>> 阶段二: 验证集回测")
        val_result = self._run_backtest(val_df, symbol, 'val')

        logger.info("\n>>> 阶段三: 测试集回测")
        test_result = self._run_backtest(test_df, symbol, 'test')

        # ---- 步骤4: 生成报告 ----
        logger.info("\n>>> 生成回测报告")
        train_report = self._format_and_save_report(train_result, symbol, 'train')
        val_report = self._format_and_save_report(val_result, symbol, 'val')
        test_report = self._format_and_save_report(test_result, symbol, 'test')

        # ---- 步骤5: 对比分析 ----
        logger.info("\n>>> 三阶段对比分析")
        comparison = compare_datasets(train_report, val_report, test_report, symbol)

        comparison_text = format_comparison_report(comparison)
        print(comparison_text)

        comp_path = Path(self.report_dir) / f"{symbol}_comparison.json"
        with open(comp_path, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"对比报告已保存: {comp_path}")

        return {
            'success': True,
            'symbol': symbol,
            'datasets': datasets_info,
            'train': train_result,
            'val': val_result,
            'test': test_result,
            'train_report': train_report,
            'val_report': val_report,
            'test_report': test_report,
            'comparison': comparison,
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
    ) -> Dict[str, Any]:
        """执行 Walk-Forward 时间序列交叉验证回测

        对数据滚动产生多个窗口，每个窗口独立回测并收集测试集指标，
        最后汇总所有窗口的平均表现。相比单次划分，Walk-Forward 能:
          - 模拟策略在时间推进中的实际表现
          - 评估策略稳健性（各窗口指标的标准差）
          - 降低单次划分的偶然性

        Args:
            symbol: 合约代码
            start_date/end_date: 数据过滤
            train_size/val_size/test_size/step: 窗口参数，
                为 None 时按比例自动计算 (60%/20%/20%, step=10%)

        Returns:
            walk_forward 结果字典:
              - windows: 窗口数
              - window_results: 各窗口测试集指标列表
              - aggregate: 聚合统计 (均值/标准差/夏普稳定性等)
        """
        from .data_loader import walk_forward_split_by_ratio, walk_forward_split

        df = load_csv_data(self.data_dir, symbol)
        if df is None or df.empty:
            return {'success': False, 'error': '数据加载失败', 'windows': 0}

        if start_date:
            df = df[df['datetime'] >= start_date]
        if end_date:
            df = df[df['datetime'] <= end_date]
        df = df.reset_index(drop=True)

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
            test_result = self._run_backtest(test_df, symbol, f'wf_{wi}_test')
            if self.context and self.context.strategy:
                self.context.strategy.reset()
            window_results.append({
                'window': wi,
                'train_rows': len(train_df),
                'val_rows': len(val_df),
                'test_rows': len(test_df),
                'test_start': str(test_df['datetime'].iloc[0])[:10],
                'test_end': str(test_df['datetime'].iloc[-1])[:10],
                'statistics': test_result.get('statistics', {}),
            })

        # 聚合所有窗口的测试集指标
        returns = []
        sharpes = []
        drawdowns = []
        win_rates = []
        for wr in window_results:
            stats = wr.get('statistics', {})
            tr = stats.get('total_return', 0)
            sr = stats.get('sharpe_ratio', 0)
            dd = stats.get('max_drawdown', 0)
            wr_rate = stats.get('win_rate', 0)
            returns.append(float(str(tr).rstrip('%')) / 100 if isinstance(tr, str) else float(tr))
            sharpes.append(float(sr))
            drawdowns.append(float(str(dd).rstrip('%')) / 100 if isinstance(dd, str) else float(dd))
            win_rates.append(float(str(wr_rate).rstrip('%')) / 100 if isinstance(wr_rate, str) else float(wr_rate))

        import numpy as np
        aggregate = {
            'return_mean': float(np.mean(returns)),
            'return_std': float(np.std(returns)),
            'sharpe_mean': float(np.mean(sharpes)),
            'sharpe_std': float(np.std(sharpes)),
            'max_drawdown_mean': float(np.mean(drawdowns)),
            'max_drawdown_worst': float(np.max(drawdowns)),
            'win_rate_mean': float(np.mean(win_rates)),
            'win_rate_std': float(np.std(win_rates)),
            'positive_window_ratio': float(np.sum(np.array(returns) > 0) / len(returns)),
            'stability_score': float(1.0 - np.std(returns) / max(abs(np.mean(returns)), 1e-9)),
        }

        logger.info(
            f"Walk-Forward 汇总 ({len(windows)} 窗口): "
            f"均收益={aggregate['return_mean']:.2%}, "
            f"夏普={aggregate['sharpe_mean']:.2f}, "
            f"盈利窗口比={aggregate['positive_window_ratio']:.0%}"
        )

        return {
            'success': True,
            'symbol': symbol,
            'windows': len(windows),
            'window_results': window_results,
            'aggregate': aggregate,
        }

    def _build_setting(self) -> Dict[str, Any]:
        return {'price_tick': self.price_tick}

    def _run_backtest(
        self,
        df: 'pd.DataFrame',
        symbol: str,
        dataset_name: str,
    ) -> Dict[str, Any]:
        """在单个数据集上执行 vnpy 回测"""
        from vnpy_ctastrategy.backtesting import BacktestingEngine
        from vnpy.trader.constant import Interval
        from strategies.bridges import VnpyStrategyBridge

        pure_symbol, exchange = parse_symbol_exchange(symbol)
        vt_symbol = f"{pure_symbol}.{exchange.value}" if hasattr(exchange, 'value') else symbol

        interval_map = {
            '1m': Interval.MINUTE,
            '5m': Interval.MINUTE,
            '15m': Interval.MINUTE,
            '30m': Interval.MINUTE,
            '1h': Interval.HOUR,
            'd': Interval.DAILY,
        }
        interval = interval_map.get(self.interval, Interval.DAILY)

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
            self.context = TradingContext(
                strategy=strategy,
                symbol=vt_symbol,
                capital=self.initial_capital,
                price_tick=self.price_tick,
            )

        self.context.strategy.reset()

        strategy_cls = self._wrap_injected_strategy(VnpyStrategyBridge)
        engine.add_strategy(strategy_cls, setting)

        bars = df_to_vnpy_datalines(df, vt_symbol)
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
        result: Dict,
        symbol: str,
        dataset_name: str,
    ) -> Dict:
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

        console_report = format_console_report(report, f"[{dataset_name.upper()}]")
        print(console_report)
        return report