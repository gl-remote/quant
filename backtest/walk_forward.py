"""Walk-Forward 时间序列交叉验证工具

提供:
  - validate_window_params:      验证窗口参数合法性
  - WindowParams:                窗口参数 dataclass
  - walk_forward_split:          WF 窗口划分 (按行数)
  - walk_forward_split_by_ratio: WF 窗口划分 (按比例)
"""

from loguru import logger
from dataclasses import dataclass

import pandas as pd

# 参数验证
# ============================================================


@dataclass
class WindowParams:
    """Walk-Forward 窗口参数

    Attributes:
        train_size: 训练集行数
        val_size: 验证集行数
        test_size: 测试集行数
        step: 滑动步长
    """
    train_size: int
    val_size: int
    test_size: int
    step: int


def validate_window_params(
    df_len: int,
    train_size: int,
    val_size: int,
    test_size: int,
    step: int,
) -> WindowParams:
    """验证并规范化 Walk-Forward 窗口参数

    Args:
        df_len: 数据总行数
        train_size: 训练集行数
        val_size: 验证集行数
        test_size: 测试集行数
        step: 滑动步长

    Returns:
        WindowParams 规范化后的参数

    Raises:
        ValueError: 参数不合法
    """
    if df_len < 1:
        raise ValueError("数据量为 0，无法创建窗口")

    min_required = train_size + val_size + test_size
    if df_len < min_required:
        raise ValueError(
            f"数据量不足：需要至少 {min_required} 行，当前 {df_len} 行"
        )

    if step < 1:
        step = max(1, test_size // 2)
        logger.info(f"step 自动调整为 {step}")

    if train_size < 1:
        raise ValueError(f"train_size 必须 >= 1，当前: {train_size}")
    if test_size < 1:
        raise ValueError(f"test_size 必须 >= 1，当前: {test_size}")

    return WindowParams(
        train_size=train_size,
        val_size=val_size,
        test_size=test_size,
        step=step,
    )


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
    params = validate_window_params(n, train_size, val_size, test_size, step)

    windows = []
    start = 0
    while start + params.train_size + params.val_size + params.test_size <= n:
        train_end = start + params.train_size
        val_end = train_end + params.val_size
        test_end = val_end + params.test_size

        train_df = df.iloc[start:train_end].reset_index(drop=True)
        val_df = df.iloc[train_end:val_end].reset_index(drop=True)
        test_df = df.iloc[val_end:test_end].reset_index(drop=True)

        windows.append((train_df, val_df, test_df))
        start += params.step

    logger.info(
        f"Walk-Forward 划分: {len(windows)} 个窗口 "
        f"(train={params.train_size}, val={params.val_size}, "
        f"test={params.test_size}, step={params.step}, 数据量={n})"
    )
    return windows


def walk_forward_split_by_ratio(
    df: pd.DataFrame,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
    step_ratio: float = 0.1,
    min_windows: int = 3,
) -> list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
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

    def _calc_sizes(ratio: float) -> tuple[int, int, int, int]:
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
    for _ in range(max_attempts):
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