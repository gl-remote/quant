"""vn.py 回测引擎 - 基于 vn.py 框架的回测系统

实现完整的回测流水线:
  1. 从本地CSV读取历史数据
  2. 按科学比例随机划分训练/验证/测试集
  3. 分别在三个数据集上独立运行回测
  4. 生成详细的交易报告
  5. 提供三阶段对比分析与过拟合风险评估

vn.py 为强制依赖，不再支持降级模式。
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

logger = logging.getLogger(__name__)


# ============================================================
# 交易记录与绩效统计 (用于 tq-backtest 实盘/模拟跟踪)
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


class BacktestEngine:
    """简单交易跟踪器 - 用于 tq-backtest 实盘/模拟模式"""

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
# vn.py 框架回测引擎
# ============================================================

class VnpyBacktestEngine:
    """vn.py 框架回测引擎

    封装完整的回测流程：数据加载 → 划分 → 回测 → 报告 → 对比

    使用方式:
        engine = VnpyBacktestEngine(config)
        engine.run_full_pipeline()
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 回测配置字典，结构参考 conf.yaml 中 backtest 段:
                - data_dir: CSV数据目录
                - initial_capital: 初始资金
                - commission_rate: 手续费率
                - slippage: 滑点
                - price_tick: 最小价格变动
                - contract_size: 合约乘数
                - interval: K线周期
                - split: 数据集划分参数
                - report: 报告输出参数
        """
        self.data_dir: str = config.get('data_dir', '.quant_shared_data/csv')
        self.initial_capital: float = float(config.get('initial_capital', 100000.0))
        self.commission_rate: float = float(config.get('commission_rate', 0.0003))
        self.slippage: float = float(config.get('slippage', 1.0))
        self.price_tick: float = float(config.get('price_tick', 1.0))
        self.contract_size: int = int(config.get('contract_size', 10))
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

        self.strategy_params: Dict = {}

    def set_strategy_params(self, **kwargs):
        """设置策略参数，将传递给 VnpyMaStrategy

        支持的参数:
            sma_short: int - 短期均线周期
            sma_long: int - 长期均线周期
            stop_loss_ratio: float - 止损比例
            take_profit_ratio: float - 止盈比例
            position_ratio: float - 仓位比例
        """
        self.strategy_params.update(kwargs)
        logger.info(f"策略参数: {self.strategy_params}")

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

    def _run_backtest(
        self,
        df: 'pd.DataFrame',
        symbol: str,
        dataset_name: str,
    ) -> Dict[str, Any]:
        """在单个数据集上执行 vnpy 回测"""
        from vnpy_ctastrategy.backtesting import BacktestingEngine
        from vnpy.trader.constant import Interval
        from strategies.gateways import VnpyMaStrategy

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
            start=df['datetime'].iloc[0],
            end=df['datetime'].iloc[-1],
            rate=self.commission_rate,
            slippage=self.slippage,
            size=self.contract_size,
            pricetick=self.price_tick,
            capital=int(self.initial_capital),
        )

        setting = {
            'sma_short': self.strategy_params.get('sma_short', 5),
            'sma_long': self.strategy_params.get('sma_long', 20),
            'stop_loss_ratio': self.strategy_params.get('stop_loss_ratio', 0.03),
            'take_profit_ratio': self.strategy_params.get('take_profit_ratio', 0.05),
            'position_ratio': self.strategy_params.get('position_ratio', 0.1),
            'price_tick': self.price_tick,
        }
        engine.add_strategy(VnpyMaStrategy, setting)

        bars = df_to_vnpy_datalines(df, vt_symbol)
        engine.history_data = {vt_symbol: bars}

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