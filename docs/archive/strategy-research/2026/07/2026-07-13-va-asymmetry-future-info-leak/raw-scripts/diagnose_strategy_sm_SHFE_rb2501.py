#!/usr/bin/env python3
"""诊断脚本：完全模拟策略 on_bar 状态机（SHFE.rb2501）。

流程：
  1. 调用策略 _precompute_va_daily_lookup 读取 CSV → daily lookup
  2. 按日期排序，逐日期模拟 _on_new_day：重复 N=6 次 append当日值 → skews/atrs/closes deque
  3. 对每个日期（相当于R侧事件日），调用 _recompute_tier 核心逻辑（r_s/r_a/r_t/trans/tier）
  4. 输出 tier 非空的日期，与研究侧 events.parquet 对比
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))

import numpy as np
import pandas as pd
from collections import deque
from math import log, isnan
from strategies.va_asymmetry_composite_strategy import VAAsymmetryCompositeStrategy
from strategies.classifiers.poc_va import (
    ClassifierConfig, TRANS_STABLE, classify_tier,
    compute_transition_series, roll_t_pit, tier_direction,
)

SYMBOL = "SHFE.rb2501"
N = 6
buf_days = 40
maxlen = buf_days * N

# ── 1. daily lookup ──
print(f"[1] 预计算 daily lookup ...")
lookup = VAAsymmetryCompositeStrategy._precompute_va_daily_lookup(SYMBOL)
sorted_dates = sorted(lookup.keys())
print(f"    共 {len(sorted_dates)} 天, 区间 {sorted_dates[0]} ~ {sorted_dates[-1]}")

# ── 2. 模拟状态机逐日执行 ──
print(f"\n[2] 逐日模拟 ({len(sorted_dates)} 天) ...")
config = VAAsymmetryCompositeStrategy.Params if hasattr(
    VAAsymmetryCompositeStrategy, "Params") else __import__(
        "dataclasses", fromlist=["dataclass"]).__dict__["dataclass"](
            type("_C", (), {"skew_rank_win":10,"atr_rank_win":10,"trend_win":10,
                             "atr_entry_win":10,"trend_entry_win":10,
                             "daily_repeat_count":6}))()

class_config = ClassifierConfig(
    skew_rank_win=10, atr_rank_win=10, trend_win=10,
    atr_entry_win=10, trend_entry_win=10,
)

skews = deque(maxlen=maxlen)
atrs = deque(maxlen=maxlen)  # 绝对 ATR
closes = deque(maxlen=maxlen)
HALF_EPS = 1e-10
mid = 0.5 * (N - 1)

hit_rows = []
for day_idx, d in enumerate(sorted_dates):
    e = lookup[d]
    s, a, c = e["A3_skew_spec"], e["daily_atr_spec"], e["close_session"]
    # ── 模拟 _on_new_day 重复 append N 次 ──
    if not isnan(s):
        for j in range(N):
            delta = (j - mid) * HALF_EPS * max(1.0, abs(s))
            skews.append(s + delta)
    if not isnan(a):
        for j in range(N):
            delta = (j - mid) * HALF_EPS * max(1.0, abs(a))
            atrs.append(a + delta)
    if not isnan(c):
        for j in range(N):
            delta = (j - mid) * HALF_EPS * max(1.0, c)
            closes.append(c + delta)
    # ── 模拟 _recompute_tier（每个日期重算一次，与 R-side event_date 对齐）──
    skew_win = class_config.skew_rank_win
    atr_win = class_config.atr_rank_win
    trend_win = class_config.trend_win
    trend_offset = class_config.trend_entry_win - 1
    trend_min_len = trend_offset + class_config.trend_win
    n_close = len(closes)
    if not (len(skews) >= skew_win and len(atrs) >= atr_win and n_close >= trend_min_len):
        continue
    s_skew = pd.Series(list(skews), dtype=float)
    s_atr = pd.Series(list(atrs), dtype=float)
    t_vals = []
    for i in range(trend_offset, n_close):
        c0 = float(closes[i - trend_offset])
        c1 = float(closes[i])
        if c0 > 0 and c1 > 0:
            t_vals.append(float(log(c1 / c0)))
        else:
            t_vals.append(float("nan"))
    s_trend = pd.Series(t_vals, dtype=float)
    # 分类（和研究侧一致：r_s = 1 - roll_t_pit(skew)）
    r_s_raw = roll_t_pit(s_skew, skew_win)
    r_s = 1.0 - (float(r_s_raw.iloc[-1]) if len(r_s_raw) and pd.notna(r_s_raw.iloc[-1]) else float("nan"))
    r_a_series = roll_t_pit(s_atr, atr_win)
    r_a = float(r_a_series.iloc[-1]) if len(r_a_series) and pd.notna(r_a_series.iloc[-1]) else float("nan")
    r_t_series = roll_t_pit(s_trend, trend_win)
    r_t = float(r_t_series.iloc[-1]) if len(r_t_series) and pd.notna(r_t_series.iloc[-1]) else float("nan")
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
    if tier is not None:
        daily_atr_bps = a / c * 10000.0 if (not isnan(a) and not isnan(c) and c > 0) else float("nan")
        hit_rows.append({
            "event_date": pd.Timestamp(d), "r_s": r_s, "r_a": r_a, "r_t": r_t,
            "trans": trans, "tier": tier, "direction": direction,
            "A3_skew_spec": s, "daily_atr_abs": a, "close_session": c,
            "daily_atr_bps": daily_atr_bps,
        })

print(f"\n[3] 命中 tier 的日期 (共 {len(hit_rows)} 条):")
if hit_rows:
    df_hit = pd.DataFrame(hit_rows)
    with pd.option_context("display.max_columns", None, "display.width", 200,
                           "display.float_format", lambda x: f"{x:.4f}"):
        print(df_hit.to_string(index=False))
    print(f"\n    tier分布: {dict(df_hit.groupby('tier').size())}")
    print(f"    方向分布: {dict(df_hit.groupby('direction').size())}")
else:
    # tier 全空，打印几个有代表性日期的原始值
    print("    tier 全空！打印诊断：")
    probe_dates = ["2024-10-14", "2024-10-22", "2024-10-25", "2024-11-12", "2024-11-28"]
    for d_str in probe_dates:
        d_ts = pd.Timestamp(d_str).date()
        if d_ts not in lookup:
            continue
        idx = sorted_dates.index(d_ts)
        # 重放前 idx+1 天
        skews2, atrs2, closes2 = deque(maxlen=maxlen), deque(maxlen=maxlen), deque(maxlen=maxlen)
        for di in range(idx + 1):
            e2 = lookup[sorted_dates[di]]
            s2, a2, c2 = e2["A3_skew_spec"], e2["daily_atr_spec"], e2["close_session"]
            if not isnan(s2):
                for j in range(N):
                    skews2.append(s2 + (j - mid) * HALF_EPS * max(1.0, abs(s2)))
            if not isnan(a2):
                for j in range(N):
                    atrs2.append(a2 + (j - mid) * HALF_EPS * max(1.0, abs(a2)))
            if not isnan(c2):
                for j in range(N):
                    closes2.append(c2 + (j - mid) * HALF_EPS * max(1.0, c2))
        nc = len(closes2)
        print(f"\n  诊断日期: {d_str} (idx={idx})")
        print(f"    buflen: skew={len(skews2)} atr={len(atrs2)} close={nc}")
        # print原始 skew 尾部10值和 atr 尾部10值（6×重复结构可见）
        tail10_s = list(skews2)[-min(18, len(skews2)):]
        tail10_a = list(atrs2)[-min(18, len(atrs2)):]
        print(f"    skew tail18: {[f'{v:.3e}' for v in tail10_s]}")
        print(f"    atr  tail18: {[f'{v:.3e}' for v in tail10_a]}")
        # 跑 roll_t_pit
        ss1 = pd.Series(list(skews2), dtype=float)
        aa1 = pd.Series(list(atrs2), dtype=float)
        tv = []
        for i in range(9, nc):
            cc0 = float(closes2[i - 9])
            cc1 = float(closes2[i])
            tv.append(float(log(cc1 / cc0)) if cc0 > 0 and cc1 > 0 else float("nan"))
        tt1 = pd.Series(tv, dtype=float)
        rs_raw = roll_t_pit(ss1, 10)
        ra_s = roll_t_pit(aa1, 10)
        rt_s = roll_t_pit(tt1, 10)
        # tail 10 r 序列
        print(f"    r_s tail10: {rs_raw.tail(10).to_numpy()}")
        print(f"    r_a tail10: {ra_s.tail(10).to_numpy()}")
        print(f"    r_t tail10: {rt_s.tail(10).to_numpy()}")
        rs = 1.0 - (float(rs_raw.iloc[-1]) if pd.notna(rs_raw.iloc[-1]) else float("nan"))
        ra = float(ra_s.iloc[-1]) if pd.notna(ra_s.iloc[-1]) else float("nan")
        rt = float(rt_s.iloc[-1]) if pd.notna(rt_s.iloc[-1]) else float("nan")
        td = compute_transition_series(ra_s)
        tran = str(td["trans"].iloc[-1])
        tier2 = classify_tier(float(rs), float(ra), float(rt), tran) if all(
            np.isfinite(x) for x in (rs, ra, rt)) else None
        print(f"    => r_s={rs:.5f} r_a={ra:.5f} r_t={rt:.5f} trans={tran} tier={tier2}")
        # MAD 细节：窗口最后10个 skew 的 median 和 MAD
        sk_last10 = list(skews2)[-10:]
        sk_med = np.median(sk_last10)
        sk_mad = np.median(np.abs(np.array(sk_last10) - sk_med))
        sk_scale = sk_mad * 1.4826
        print(f"    skew_last10_med={sk_med:.5f} MAD={sk_mad:.3e} scale={sk_scale:.3e} (<1e-12? {sk_scale < 1e-12})")

# ── 4. 对照研究侧 ──
print(f"\n[4] 研究侧 events.parquet 对照 ...")
ev_path = REPO / "docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side/events.parquet"
if ev_path.exists():
    df_r = pd.read_parquet(ev_path)
    sub_r = df_r[df_r["contract"] == SYMBOL].copy()
    print(f"    研究侧命中: {len(sub_r)} 条")
    if not sub_r.empty:
        cols = [c for c in ["event_date", "A3_skew_spec", "daily_atr_spec",
                            "close_t", "r_s", "r_a", "r_t", "trans", "tier",
                            "direction"] if c in sub_r.columns]
        with pd.option_context("display.max_columns", None, "display.width", 200,
                               "display.float_format", lambda x: f"{x:.6f}"):
            print(sub_r[cols].to_string(index=False))
