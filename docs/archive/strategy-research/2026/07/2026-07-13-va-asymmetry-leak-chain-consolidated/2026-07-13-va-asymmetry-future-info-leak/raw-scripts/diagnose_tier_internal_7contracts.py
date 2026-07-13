#!/usr/bin/env python3
"""快速诊断：SHFE.rb2501 分类器内部中间结果输出。

直接调用策略的 _precompute_va_daily_lookup + _recompute_tier 核心逻辑，
打印 r_s/r_a/r_t/trans/tier/direction 各层值，定位0笔交易的根因。
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))

import numpy as np
import pandas as pd
from collections import deque
from math import log
from strategies.va_asymmetry_composite_strategy import VAAsymmetryCompositeStrategy
from strategies.classifiers.poc_va import (
    ClassifierConfig, TRANS_STABLE, classify_tier,
    compute_transition_series, roll_t_pit, tier_direction,
)

SYMBOL = "SHFE.rb2501"
N = 6

# 1. 预计算 daily lookup
print(f"[1/4] 预计算 {SYMBOL} daily lookup ...")
lookup = VAAsymmetryCompositeStrategy._precompute_va_daily_lookup(SYMBOL)
print(f"      lookup 天数: {len(lookup)}")
sorted_dates = sorted(lookup.keys())
print(f"      首日: {sorted_dates[0]} (有值? {lookup[sorted_dates[0]]})")
print(f"      末前10日:")
for d in sorted_dates[-10:]:
    e = lookup[d]
    print(f"        {d} skew={e['A3_skew_spec']:+.4f}  atr_abs={e['daily_atr_spec']:.2f}  close={e['close_session']:.2f}")

# 2. 模拟每日重复 N 次，构造 skews/atrs/closes deque（maxlen=40*6=240）
print(f"\n[2/4] 构造重复 N={N} 次的滚动缓冲区 ...")
buf_days = 40
maxlen = buf_days * N
skews = deque(maxlen=maxlen)
atrs_abs = deque(maxlen=maxlen)
closes = deque(maxlen=maxlen)
HALF_EPS = 1e-10
mid = 0.5 * (N - 1)
for d in sorted_dates:
    e = lookup[d]
    s, a, c = e["A3_skew_spec"], e["daily_atr_spec"], e["close_session"]
    if np.isfinite(s):
        for j in range(N):
            delta = (j - mid) * HALF_EPS * max(1.0, abs(s))
            skews.append(s + delta)
    if np.isfinite(a):
        for j in range(N):
            delta = (j - mid) * HALF_EPS * max(1.0, abs(a))
            atrs_abs.append(a + delta)
    if np.isfinite(c):
        for j in range(N):
            delta = (j - mid) * HALF_EPS * max(1.0, c)
            closes.append(c + delta)
print(f"      缓冲区最终长度: skew={len(skews)} atr={len(atrs_abs)} close={len(closes)}")

# 3. 用 ClassifierConfig 默认参数重算最后15个"对齐点"（每个对齐点等价于 hourly 推进）
print(f"\n[3/4] 逐对齐点重算 tier（末15点）...")
class_config = ClassifierConfig()
skew_win = class_config.skew_rank_win
atr_win = class_config.atr_rank_win
trend_win = class_config.trend_win
trend_offset = class_config.trend_entry_win - 1
trend_min_len = trend_offset + class_config.trend_win

# 模拟 hourly：每个真实日有 ~6 个对齐点，所以我们从第40天（40*6=240）开始，每6个样本取一次作为对齐点
start_day_idx = max(10, len(sorted_dates) - 20)
for day_idx in range(start_day_idx, len(sorted_dates)):
    d = sorted_dates[day_idx]
    # 每个真实日在缓冲区追加了 N 个重复样本，所以 day_idx=k 对应缓冲区位置 = (k+1)*N - 1
    buf_pos = (day_idx + 1) * N - 1
    if buf_pos >= len(skews) or buf_pos >= len(atrs_abs) or buf_pos >= len(closes):
        continue
    # 取 0..buf_pos 这段喂给分类器
    s_arr = list(skews)[: buf_pos + 1]
    a_arr = list(atrs_abs)[: buf_pos + 1]
    c_arr_full = list(closes)[: buf_pos + 1]
    n_close = len(c_arr_full)
    if len(s_arr) < skew_win or len(a_arr) < atr_win or n_close < trend_min_len:
        continue
    t_vals = []
    for i in range(trend_offset, n_close):
        c0 = float(c_arr_full[i - trend_offset])
        c1 = float(c_arr_full[i])
        if c0 > 0 and c1 > 0:
            t_vals.append(float(log(c1 / c0)))
        else:
            t_vals.append(float("nan"))
    s_skew = pd.Series(s_arr, dtype=float)
    s_atr = pd.Series(a_arr, dtype=float)
    s_trend = pd.Series(t_vals, dtype=float)
    r_s_raw = roll_t_pit(s_skew, skew_win)
    r_s = 1.0 - float(r_s_raw.iloc[-1]) if len(r_s_raw) else float("nan")
    r_a_series = roll_t_pit(s_atr, atr_win)
    r_a = float(r_a_series.iloc[-1]) if len(r_a_series) else float("nan")
    r_t_series = roll_t_pit(s_trend, trend_win)
    r_t = float(r_t_series.iloc[-1]) if len(r_t_series) else float("nan")
    trans = TRANS_STABLE
    if len(r_a_series) > 0 and r_a_series.notna().any():
        trans_df = compute_transition_series(r_a_series)
        trans = str(trans_df["trans"].iloc[-1])
    tier = None
    direction = ""
    if np.isfinite(r_s) and np.isfinite(r_a) and np.isfinite(r_t):
        tier = classify_tier(float(r_s), float(r_a), float(r_t), trans)
        if tier:
            direction = tier_direction(tier)
    today_atr_abs = float(lookup[d].get("daily_atr_spec", float("nan")))
    today_close = float(lookup[d].get("close_session", float("nan")))
    daily_atr_bps = today_atr_abs / today_close * 10000.0 if today_close > 0 else float("nan")
    print(
        f"  d={d} pos={buf_pos:>4d} | "
        f"r_s={r_s:.3f} r_a={r_a:.3f} r_t={r_t:.3f} | "
        f"trans={trans:<13s} | "
        f"tier={str(tier):<20s} dir={direction:<5s} | "
        f"daily_atr_bps={daily_atr_bps:.2f}"
    )

# 4. 对照研究侧 events.parquet：取 SHFE.rb2501 的事件行打印
print(f"\n[4/4] 对照研究侧 events.parquet ...")
ev_path = REPO / "docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side/events.parquet"
if ev_path.exists():
    df = pd.read_parquet(ev_path)
    sub = df[df["contract"] == SYMBOL].copy()
    if sub.empty:
        print(f"      研究侧无 {SYMBOL} 事件")
    else:
        print(f"      研究侧 {SYMBOL}: {len(sub)} 事件 | tier分布: {dict(sub.groupby('tier').size())}")
        cols = ["event_date", "A3_skew_spec", "daily_atr_spec", "close_t",
                "r_s", "r_a", "r_t", "trans", "tier", "direction"]
        cols = [c for c in cols if c in sub.columns]
        print(sub[cols].tail(15).to_string(index=False))
else:
    print(f"      研究侧 parquet 不存在: {ev_path}")
    print("      请先运行 reproduce_research_side.py 生成基线")
