"""roll_t_pit MAD 错位 bug 最小验证脚本。

Bug 说明：
  当前向量化 roll_t_pit 中：
    roll_med[i] = median(x[i-W+1 : i+1])           ← 正确
    dev_abs[i] = |x[i] - roll_med[i]|             ← 这里用的是「当前位置自己窗口」的 med
    roll_mad[i] = median(dev_abs[i-W+1 : i+1])    ← 但这里 dev_abs 每个元素用的是「各自窗口」的 med！

  正确定义（每个窗口内部自洽）：
    对窗口 k = [k-W+1, k]：
        med_k = median(x[k-W+1 : k+1])
        mad_k = median( |x[j] - med_k|  for j in k-W+1..k )   ← 所有 j 都用同一个 med_k
        z_k = (x[k] - med_k) / (MAD_SCALE * mad_k)
        result_k = t_CDF(z_k)

  当前实现把 dev_abs[j] = |x[j] - med_j| 混在一起做滚动中位数，相当于拿了错误的偏差绝对值
  （每个 j 用了自己窗口的中位，而不是窗口 k 的中位）。

验证方案：取一组手工数据 + 用逐窗 apply 做 ground truth 对比当前实现 vs 修正后实现。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

T_PIT_DF = 12
MAD_SCALE = 1.4826


def roll_t_pit_current_buggy(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """当前工程侧实现（MAD 错位版）。"""
    if min_periods is None:
        min_periods = window
    roll = series.rolling(window, min_periods=min_periods)
    roll_med = roll.median()
    dev_abs = (series - roll_med).abs()
    mad_min = max(3, window // 4)
    roll_mad = dev_abs.rolling(window, min_periods=mad_min).quantile(0.5)
    scale = roll_mad * MAD_SCALE
    z_arr = ((series - roll_med) / scale.where(scale >= 1e-12)).fillna(0.0).to_numpy(dtype=np.float64)
    result = pd.Series(t_dist.cdf(z_arr, df=T_PIT_DF), index=series.index, dtype=np.float64)
    result.loc[scale < 1e-12] = 0.5
    result.iloc[: min_periods - 1] = np.nan
    return result


def roll_t_pit_ground_truth(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """逐窗口纯 Python apply = 数学定义 ground truth。"""
    if min_periods is None:
        min_periods = window
    vals = series.to_numpy(dtype=np.float64)
    n = len(vals)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - window + 1)
        win = vals[lo : i + 1]
        if len(win) < min_periods:
            continue
        med = np.median(win)
        mad = np.median(np.abs(win - med))
        scale = mad * MAD_SCALE
        if scale < 1e-12:
            out[i] = 0.5
            continue
        z = (vals[i] - med) / scale
        out[i] = t_dist.cdf(z, df=T_PIT_DF)
    return pd.Series(out, index=series.index)


def roll_t_pit_strided_fixed(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """用 numpy stride 2D rolling view 批量正确计算每个窗口自洽的 med + MAD + z + CDF。"""
    if min_periods is None:
        min_periods = window
    vals = series.to_numpy(dtype=np.float64)
    n = len(vals)
    out = np.full(n, np.nan, dtype=np.float64)
    if n < min_periods:
        return pd.Series(out, index=series.index)

    # 用 stride_tricks.as_strided 构造 2D rolling view：
    # shape = (n - window + 1, window)，每一行 = x[i : i+window]
    from numpy.lib.stride_tricks import as_strided

    if n >= window:
        byte_stride = vals.strides[0]
        view = as_strided(
            vals,
            shape=(n - window + 1, window),
            strides=(byte_stride, byte_stride),
            writeable=False,
        )
        # 批量窗口中位数（axis=1）
        med_arr = np.median(view, axis=1)  # shape (n-W+1,)
        # 批量窗口 MAD：每个窗口内 |x - med| 的中位数
        abs_dev = np.abs(view - med_arr[:, None])  # shape (n-W+1, W)
        mad_arr = np.median(abs_dev, axis=1)  # shape (n-W+1,)
        scale_arr = mad_arr * MAD_SCALE
        # 每个窗口最后一个值的 z = (x[i] - med_i) / scale_i
        x_last = view[:, -1]
        safe_scale = np.where(scale_arr >= 1e-12, scale_arr, 1.0)
        z_arr = np.where(scale_arr >= 1e-12, (x_last - med_arr) / safe_scale, 0.0)
        cdf_full = t_dist.cdf(z_arr, df=T_PIT_DF)
        # MAD=0 → 0.5
        cdf = np.where(scale_arr >= 1e-12, cdf_full, 0.5)
        # 填到 out 的尾部 [window-1 : n]
        out[window - 1 : n] = cdf
    else:
        # n < window：退化到逐窗循环（仅 min_periods ≤ n < window 的情况）
        for i in range(min_periods - 1, n):
            win = vals[: i + 1]
            med = np.median(win)
            mad = np.median(np.abs(win - med))
            scale = mad * MAD_SCALE
            if scale < 1e-12:
                out[i] = 0.5
            else:
                z = (vals[i] - med) / scale
                out[i] = t_dist.cdf(z, df=T_PIT_DF)
    return pd.Series(out, index=series.index)


def main() -> None:
    # ---------- Case 1: 每日重复 6 次的模式（路径B缓冲区模式）----------
    print("=" * 80)
    print("Case 1: 每日重复 N=6 次值（路径B典型输入）")
    print("=" * 80)
    np.random.seed(42)
    # 20 个"真实日值"，每个重复 6 次 → 120 个点
    daily_vals = np.random.randn(20) * 0.5 + 1.0
    reps = 6
    seq = np.repeat(daily_vals, reps) + 1e-10 * (np.arange(20 * reps) % reps - (reps - 1) / 2)
    s = pd.Series(seq)
    W = 10

    gt = roll_t_pit_ground_truth(s, W)
    buggy = roll_t_pit_current_buggy(s, W)
    fixed = roll_t_pit_strided_fixed(s, W)

    cmp_df = pd.DataFrame(
        {
            "x": s.values,
            "GT": gt.values,
            "Current(buggy)": buggy.values,
            "Fixed(strided)": fixed.values,
            "|buggy-GT|": (buggy - gt).abs().values,
            "|fixed-GT|": (fixed - gt).abs().values,
        }
    )
    # 只看有效行
    valid = cmp_df.dropna(subset=["GT"])
    print(f"有效行数: {len(valid)}")
    print(
        "最大误差：buggy = %.2e  fixed = %.2e"
        % (valid["|buggy-GT|"].max(), valid["|fixed-GT|"].max())
    )
    print(
        "平均误差：buggy = %.2e  fixed = %.2e"
        % (valid["|buggy-GT|"].mean(), valid["|fixed-GT|"].mean())
    )
    # 极端值占比
    for name, col in [("GT", "GT"), ("Current(buggy)", "Current(buggy)"), ("Fixed", "Fixed(strided)")]:
        v = valid[col].dropna()
        extreme = ((v > 0.90) | (v < 0.10)).sum() / len(v) * 100
        print(f"  {name}: r>0.9 或 r<0.1 占比 = {extreme:.2f}%")
    # 打印尾部 30 行
    print("\n尾部 30 行对比：")
    with pd.option_context("display.width", 160, "display.float_format", "{:.6f}".format):
        print(cmp_df.tail(30).to_string())

    # ---------- Case 2: 纯随机（无重复）----------
    print("\n" + "=" * 80)
    print("Case 2: 纯随机无重复值（常规场景）")
    print("=" * 80)
    np.random.seed(0)
    s2 = pd.Series(np.random.randn(200))
    gt2 = roll_t_pit_ground_truth(s2, W)
    buggy2 = roll_t_pit_current_buggy(s2, W)
    fixed2 = roll_t_pit_strided_fixed(s2, W)
    valid2 = pd.DataFrame({"GT": gt2, "B": buggy2, "F": fixed2}).dropna()
    print(
        "最大误差：buggy = %.2e  fixed = %.2e"
        % ((valid2["B"] - valid2["GT"]).abs().max(), (valid2["F"] - valid2["GT"]).abs().max())
    )
    for name, col in [("GT", "GT"), ("Buggy", "B"), ("Fixed", "F")]:
        v = valid2[col]
        extreme = ((v > 0.90) | (v < 0.10)).sum() / len(v) * 100
        print(f"  {name}: r>0.9 或 r<0.1 占比 = {extreme:.2f}%")


if __name__ == "__main__":
    main()
