"""验证足量样本下 rank 极端度。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
import numpy as np
import pandas as pd
from strategies.classifiers.poc_va import roll_t_pit

np.random.seed(123)

# 300 天真实日值（足够多的独立样本）× 每日 6 次重复
N_DAYS = 300
N_REP = 6
daily_skew = np.random.randn(N_DAYS) * 0.5 + 1.0
daily_atr = np.abs(np.random.randn(N_DAYS)) * 50 + 100

seq_skew = np.repeat(daily_skew, N_REP) + 1e-10 * (np.arange(N_DAYS*N_REP) % N_REP - (N_REP-1)/2)
seq_atr = np.repeat(daily_atr, N_REP) + 1e-10 * (np.arange(N_DAYS*N_REP) % N_REP - (N_REP-1)/2)

for name, s_values in [("skew", seq_skew), ("atr", seq_atr)]:
    s = pd.Series(s_values)
    r = roll_t_pit(s, 10)
    v = r.dropna()
    ext = ((v > 0.9) | (v < 0.1)).sum() / len(v) * 100
    print(f"{name}: n_days={N_DAYS} → len(seq)={len(s)}  valid={len(v)}")
    print(f"  r 极端%={ext:.2f}  min={v.min():.4f}  max={v.max():.4f}")
    print(f"  r <0.1: {(v<0.1).sum()/len(v)*100:.2f}%  r>0.9: {(v>0.9).sum()/len(v)*100:.2f}%")
    # 分位数
    qs = v.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    print(f"  分位数: 5%={qs[0.05]:.3f} 25%={qs[0.25]:.3f} 50%={qs[0.5]:.3f} 75%={qs[0.75]:.3f} 95%={qs[0.95]:.3f}")
