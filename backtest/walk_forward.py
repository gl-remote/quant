"""Walk-Forward 时间序列交叉验证与回测数据工具

提供:
  - parse_symbol_exchange:      品种代码 → 交易所映射
  - filter_dataframe_by_date:   日期范围过滤
  - df_to_vnpy_datalines:       DataFrame → vnpy BarData
  - walk_forward_split:         WF 窗口划分 (按行数)
  - walk_forward_split_by_ratio: WF 窗口划分 (按比例)
"""

import logging
import pandas as pd
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def parse_symbol_exchange(symbol: str) -> tuple[str, str]:
    """解析品种代码中的交易所信息，统一返回字符串类型

    Args:
        symbol: 完整合约代码 (e.g. DCE.m2509)

    Returns:
        (pure_symbol, exchange_code) 均为字符串
    """
    if '.' in symbol:
        parts = symbol.split('.')
        pure_symbol = parts[-1]
        exchange_code = parts[0]
    else:
        pure_symbol = symbol
        exchange_code = 'CFFEX'

    return pure_symbol, exchange_code


# ── 日期过滤 ──────────────────────────────────────────────

def filter_dataframe_by_date(
    df: 'pd.DataFrame',
    start_date: str | None = None,
    end_date: str | None = None,
) -> 'pd.DataFrame':
    """按日期范围过滤 DataFrame，重置索引

    纯函数，不修改原 DataFrame。

    Args:
        df: 含 'datetime' 列的 K 线 DataFrame
        start_date: 可选起始日期 (闭区间)
        end_date: 可选结束日期 (闭区间)

    Returns:
        过滤后的 DataFrame (copy, reindexed)
    """
    if start_date:
        df = df[df['datetime'] >= start_date]
    if end_date:
        df = df[df['datetime'] <= end_date]
    return df.reset_index(drop=True)


# ── BarData 转换 ─────────────────────────────────────────

def df_to_vnpy_datalines(df: pd.DataFrame, symbol: str, interval=None) -> list:
    """将 DataFrame 转换为 vn.py 回测引擎可用的 BarData 列表

    将 K 线 CSV (datetime, open, high, low, close, volume) 转换为
    vnpy BarData 对象列表，可直接注入 BacktestingEngine.history_data

    Args:
        df: K 线数据
        symbol: 合约代码 (vnpy 格式: 品种.交易所, e.g. m2509.DCE)
        interval: vnpy Interval 枚举，None 时回退到 Interval.DAILY

    Returns:
        vnpy BarData 对象列表
    """
    required_cols = {'datetime', 'open', 'high', 'low', 'close', 'volume'}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"数据缺少必要列: {missing}")

    try:
        from vnpy.trader.object import BarData
        from vnpy.trader.constant import Exchange, Interval
    except ImportError:
        logger.warning("vnpy 未安装，返回字典格式数据")
        bars = []
        for _, row in df.iterrows():
            dt = row['datetime']
            if isinstance(dt, str):
                dt = pd.to_datetime(dt)
            bars.append({
                'symbol': symbol,
                'datetime': dt,
                'open_price': float(row['open']),
                'high_price': float(row['high']),
                'low_price': float(row['low']),
                'close_price': float(row['close']),
                'volume': float(row['volume']),
            })
        return bars

    pure_symbol, exchange_code = parse_symbol_exchange(symbol)
    exchange = Exchange(exchange_code) if Exchange else exchange_code
    bar_interval = interval if interval is not None else Interval.DAILY

    bars = []
    for _, row in df.iterrows():
        dt = row['datetime']
        if isinstance(dt, str):
            dt = pd.to_datetime(dt)
        bar = BarData(
            symbol=pure_symbol,
            exchange=exchange,
            datetime=dt,
            interval=bar_interval,
            open_price=float(row['open']),
            high_price=float(row['high']),
            low_price=float(row['low']),
            close_price=float(row['close']),
            volume=float(row['volume']),
            gateway_name="CSV",
        )
        bars.append(bar)

    logger.info(f"转换完成: {len(bars)} 条 BarData")
    return bars


# ============================================================
# Walk-Forward 时间序列交叉验证
# ============================================================

def walk_forward_split(
    df: pd.DataFrame,
    train_size: int = 200,
    val_size: int = 40,
    test_size: int = 40,
    step: int = 40,
) -> list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Walk-Forward 时间序列交叉验证 — 生成多个滚动窗口

    按时间顺序滚动生成 (训练集, 验证集, 测试集) 三元组。
    每个窗口在前一个窗口基础上向前滑动 step 行。

    Args:
        df: 按时间排序的完整历史数据集
        train_size: 每个窗口的训练集行数
        val_size: 每个窗口的验证集行数
        test_size: 每个窗口的测试集行数
        step: 窗口滑动步长 (行数)，越小窗口越多

    Returns:
        [(train_df, val_df, test_df), ...] 按时间顺序排列的窗口列表
    """
    n = len(df)
    min_required = train_size + val_size + test_size
    if n < min_required:
        raise ValueError(
            f"数据量不足：需要至少 {min_required} 行，当前 {n} 行"
        )

    windows = []
    start = 0
    while start + min_required <= n:
        train_end = start + train_size
        val_end = train_end + val_size
        test_end = val_end + test_size

        train_df = df.iloc[start:train_end].reset_index(drop=True)
        val_df = df.iloc[train_end:val_end].reset_index(drop=True)
        test_df = df.iloc[val_end:test_end].reset_index(drop=True)

        windows.append((train_df, val_df, test_df))
        start += step

    logger.info(
        f"Walk-Forward 划分: {len(windows)} 个窗口 "
        f"(train={train_size}, val={val_size}, test={test_size}, step={step}, "
        f"数据量={n})"
    )
    return windows


def walk_forward_split_by_ratio(
    df: pd.DataFrame,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
    step_ratio: float = 0.1,
    min_windows: int = 3,
) -> List[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Walk-Forward 时间序列交叉验证 — 基于比例参数

    将 walk_forward_split 的行数参数转换为比例参数，
    自动计算合适的窗口大小，保证至少 min_windows 个窗口。

    Args:
        df: 按时间排序的完整历史数据集
        train_ratio: 训练集占窗口总长度的比例 (默认 0.6)
        val_ratio: 验证集占窗口总长度的比例 (默认 0.2)
        test_ratio: 测试集占窗口总长度的比例 (默认 0.2)
        step_ratio: 滑动步长占窗口总长度的比例 (默认 0.1)
        min_windows: 最少需要的窗口数

    Returns:
        [(train_df, val_df, test_df), ...] 按时间顺序排列的窗口列表

    Raises:
        ValueError: 比例之和不为 1.0 或数据量不足以产生至少 1 个窗口
    """
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-9:
        raise ValueError(f"比例之和必须为 1.0，当前: {total_ratio}")

    n = len(df)
    if n < 1:
        raise ValueError("数据量为 0，无法划分窗口")

    def _calc_sizes(ratio: float) -> tuple:
        window_total = int(n / (1 + (min_windows - 1) * ratio))
        if window_total < 1:
            return 0, 0, 0, 0
        train_size = int(window_total * train_ratio)
        val_size = int(window_total * val_ratio)
        test_size = window_total - train_size - val_size
        step = max(1, int(window_total * ratio))
        return train_size, val_size, test_size, step

    def _count_windows(ts: int, vs: int, tes: int, st: int) -> int:
        wsize = ts + vs + tes
        if wsize > n or st < 1:
            return 0
        return (n - wsize) // st + 1

    effective_ratio = step_ratio
    train_size, val_size, test_size, step = _calc_sizes(effective_ratio)

    max_attempts = 10
    for attempt in range(max_attempts):
        actual_windows = _count_windows(train_size, val_size, test_size, step)
        if actual_windows < min_windows:
            effective_ratio *= 0.8
            train_size, val_size, test_size, step = _calc_sizes(effective_ratio)
            if train_size < 1:
                break
        else:
            break

    if train_size < 1:
        raise ValueError(f"数据量 {n} 不足以产生至少 {min_windows} 个窗口")

    actual_window = train_size + val_size + test_size
    actual_windows = _count_windows(train_size, val_size, test_size, step)
    if actual_windows < min_windows:
        logger.warning(
            f"Walk-Forward 只能产生 {actual_windows} 个窗口 (min_windows={min_windows})，"
            f"数据量 {n} 不足，使用实际窗口数"
        )

    logger.info(
        f"Walk-Forward (按比例): 窗口总行={actual_window} "
        f"(train={train_size}, val={val_size}, test={test_size}), "
        f"step={step}, 窗口数={actual_windows}, 数据量={n}"
    )

    return walk_forward_split(df, train_size, val_size, test_size, step)
