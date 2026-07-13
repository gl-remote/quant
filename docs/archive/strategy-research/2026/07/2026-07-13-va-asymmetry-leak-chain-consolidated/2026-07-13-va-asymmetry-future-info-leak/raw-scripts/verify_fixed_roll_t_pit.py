"""验证修复后的工程侧 roll_t_pit 与 ground truth 完全一致。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist
from strategies.classifiers.poc_va import roll_t_pit, MAD_SCALE, T_PIT_DF


def roll_t_pit_gt(series, window, min_periods=None):
    if min_periods is None:
        min_periods = window
    vals = series.to_numpy(dtype=np.float64)
    n = len(vals)
    out = np.full(n, np.nan)
    for i in range(n):
        lo = max(0, i - window + 1)
        win = vals[lo:i+1]
        if len(win) < min_periods:
            continue
        med = np.median(win)
        mad = np.median(np.abs(win - med))
        scale = mad * MAD_SCALE
        if scale < 1e-12:
            out[i] = 0.5
        else:
            z = (vals[i] - med) / scale
            out[i] = t_dist.cdf(z, df=T_PIT_DF)
    return pd.Series(out, index=series.index)


def report(name, s, W, min_p=None):
    gt = roll_t_pit_gt(s, W, min_p)
    impl = roll_t_pit(s, W, min_p)
    df = pd.DataFrame({"gt": gt, "impl": impl})
    valid = df.dropna()
    if len(valid) == 0:
        print(f"[{name}] W={W}: no valid rows")
        return 0.0
    max_err = (valid["gt"] - valid["impl"]).abs().max()
    mean_err = (valid["gt"] - valid["impl"]).abs().mean()
    gt_ext = ((valid["gt"] > 0.9) | (valid["gt"] < 0.1)).sum() / len(valid) * 100
    im_ext = ((valid["impl"] > 0.9) | (valid["impl"] < 0.1)).sum() / len(valid) * 100
    print(f"[{name}] W={W} rows={len(s)} valid={len(valid)} gt_nan_start={df['gt'].isna().sum()}")
    print(f"  max_err={max_err:.2e}  mean_err={mean_err:.2e}")
    print(f"  GT极端%={gt_ext:.2f}  工程侧极端%={im_ext:.2f}")
    return max_err


np.random.seed(42)
maxes = []

# Case 1: 路径B典型模式 N=6 重复
daily = np.random.randn(20) * 0.5 + 1.0
reps = 6
seq = np.repeat(daily, reps) + 1e-10 * (np.arange(20*reps) % reps - (reps-1)/2)
maxes.append(report("路径B重复6次", pd.Series(seq), 10))

# Case 2: 纯随机 200 行
maxes.append(report("纯随机200", pd.Series(np.random.randn(200)), 10))

# Case 3: W=20
maxes.append(report("纯随机500 W=20", pd.Series(np.random.randn(500)), 20))

# Case 4: 短序列（n < W, 但 >= min_periods = 5）
maxes.append(report("短序列n=7 W=10 min_p=5", pd.Series(np.random.randn(7)), 10, min_p=5))

# Case 5: n=W 边界
maxes.append(report("边界n=W=10", pd.Series(np.random.randn(10)), 10))

# Case 6: 单调序列
maxes.append(report("单调上升", pd.Series(np.arange(50, dtype=float)*0.1), 10))

# Case 7: 全常数（MAD=0 → 兜底0.5）
maxes.append(report("全常数 MAD=0", pd.Series(np.ones(20)), 10))

# Case 8: min_periods < window
maxes.append(report("min_periods=3 W=10", pd.Series(np.random.randn(30)), 10, min_p=3))

print("\n==== 所有场景最大误差汇总 ====")
print(f"全局最大误差 = {max(maxes):.2e}")
assert max(maxes) < 1e-12, "FAIL: 误差过大!"
print("PASS: 所有场景与 GT 完全一致 (<1e-12)")
