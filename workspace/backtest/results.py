"""
回测结果聚合与统计

提供:
  - aggregate_walk_forward: Walk-Forward 窗口结果聚合
  - WalkForwardAggregate: 聚合统计 dataclass
  - WalkForwardWindowResult: 单窗口结果 dataclass
  - WalkForwardResult: Walk-Forward 整体结果 dataclass

从 VnpyBacktestEngine.run_walk_forward 中提取，
使聚合逻辑可独立测试和复用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from common.formatting import parse_percentage
from common.formulas import profitable_ratio


@dataclass
class WalkForwardAggregate:
    """Walk-Forward 聚合统计

    Attributes:
        return_mean: OOS 平均收益
        return_std: OOS 收益标准差
        sharpe_mean: 平均夏普比率
        sharpe_std: 夏普标准差
        max_drawdown_mean: 平均最大回撤
        max_drawdown_worst: 最差最大回撤
        win_rate_mean: 平均胜率
        win_rate_std: 胜率标准差
        positive_window_ratio: 盈利窗口占比
        stability_score: 稳定性得分 (0-1)
        is_oos_return_gap: IS-OOS 收益差距
    """

    return_mean: float = 0.0
    return_std: float = 0.0
    sharpe_mean: float = 0.0
    sharpe_std: float = 0.0
    max_drawdown_mean: float = 0.0
    max_drawdown_worst: float = 0.0
    win_rate_mean: float = 0.0
    win_rate_std: float = 0.0
    positive_window_ratio: float = 0.0
    stability_score: float = 0.0
    is_oos_return_gap: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "return_mean": self.return_mean,
            "return_std": self.return_std,
            "sharpe_mean": self.sharpe_mean,
            "sharpe_std": self.sharpe_std,
            "max_drawdown_mean": self.max_drawdown_mean,
            "max_drawdown_worst": self.max_drawdown_worst,
            "win_rate_mean": self.win_rate_mean,
            "win_rate_std": self.win_rate_std,
            "positive_window_ratio": self.positive_window_ratio,
            "stability_score": self.stability_score,
            "is_oos_return_gap": self.is_oos_return_gap,
        }


@dataclass
class WalkForwardWindowResult:
    """Walk-Forward 单窗口结果

    Attributes:
        window: 窗口索引（从 0 开始）
        train_rows: 训练集行数
        val_rows: 验证集行数
        test_rows: 测试集行数
        train_start: 训练集起始日期（YYYY-MM-DD）
        train_end: 训练集结束日期
        test_start: 测试集起始日期
        test_end: 测试集结束日期
        statistics: 测试集（OOS）统计
        statistics_is: 训练集（IS）统计
        daily_results: 测试集每日结果
        trades: 测试集成交记录
    """

    window: int
    train_rows: int
    val_rows: int
    test_rows: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    statistics: dict[str, Any] = field(default_factory=dict)
    statistics_is: dict[str, Any] = field(default_factory=dict)
    daily_results: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WalkForwardResult:
    """Walk-Forward 整体结果

    Attributes:
        success: 是否成功
        windows: 窗口数
        symbol: 合约代码
        error: 失败原因（success 为 False 时有效）
        window_results: 各窗口结果
        aggregate: 聚合统计
    """

    success: bool
    windows: int
    symbol: str = ""
    error: str | None = None
    window_results: list[WalkForwardWindowResult] = field(default_factory=list)
    aggregate: WalkForwardAggregate | None = None


def aggregate_walk_forward(
    window_results: list[WalkForwardWindowResult],
) -> WalkForwardAggregate:
    """对 Walk-Forward 各窗口结果进行聚合统计

    Args:
        window_results: 窗口结果列表（WalkForwardWindowResult）

    Returns:
        WalkForwardAggregate 聚合统计
    """
    returns: list[float] = []
    sharpes: list[float] = []
    drawdowns: list[float] = []
    win_rates: list[float] = []
    is_returns: list[float] = []
    oos_returns: list[float] = []

    for w in window_results:
        stats = w.statistics
        is_stats = w.statistics_is
        returns.append(parse_percentage(stats.get("total_return", 0)))
        sharpes.append(float(stats.get("sharpe_ratio", 0)))
        drawdowns.append(parse_percentage(stats.get("max_drawdown", 0)))
        win_rates.append(parse_percentage(stats.get("win_rate", 0)))
        is_returns.append(parse_percentage(is_stats.get("total_return", 0)))
        oos_returns.append(parse_percentage(stats.get("total_return", 0)))

    arr_returns = np.array(returns, dtype=float)
    is_mean = float(np.mean(is_returns)) if is_returns else 0.0
    oos_mean = float(np.mean(oos_returns)) if oos_returns else 0.0

    return WalkForwardAggregate(
        return_mean=float(np.mean(arr_returns)),
        return_std=float(np.std(arr_returns)),
        sharpe_mean=float(np.mean(sharpes)),
        sharpe_std=float(np.std(sharpes)),
        max_drawdown_mean=float(np.mean(drawdowns)),
        max_drawdown_worst=float(np.max(drawdowns)),
        win_rate_mean=float(np.mean(win_rates)),
        win_rate_std=float(np.std(win_rates)),
        positive_window_ratio=profitable_ratio(
            int(np.sum(arr_returns > 0)),
            len(arr_returns),
        ),
        stability_score=float(
            max(
                0.0,
                min(
                    1.0,
                    1.0 - float(np.std(arr_returns)) / max(abs(float(np.mean(arr_returns))), 1e-9),
                ),
            )
        ),
        is_oos_return_gap=is_mean - oos_mean,
    )
