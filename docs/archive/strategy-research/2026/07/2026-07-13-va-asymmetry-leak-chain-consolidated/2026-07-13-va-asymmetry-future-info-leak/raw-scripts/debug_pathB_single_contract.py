"""路径B单合约 debug 脚本：直接驱动策略 on_bar 看 tier/r 值/交易信号。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))

import pandas as pd
import numpy as np
from collections import deque

# 导入策略
from strategies.va_asymmetry_composite_strategy import (
    VAAsymmetryCompositeStrategy,
    VAAsymmetryCompositeParams,
)
from strategies.classifiers.poc_va import (
    ClassifierConfig,
    roll_t_pit,
    compute_transition_series,
    classify_tier,
    tier_direction,
)

# ── 找一个数据充足的 5m CSV ──
CSV = "/Users/gaolei/Documents/src/quant/project_data/market_data/csv/SHFE.rb2501.tqsdk.5m.csv"
print(f"加载 {CSV}")
bar_df = pd.read_csv(CSV)
print(f"  总 {len(bar_df)} 行，列: {list(bar_df.columns)}")

# 只要 datetime, open, high, low, close, volume
bar_df = bar_df.rename(columns={c: c.lower() for c in bar_df.columns})
# 确认列
print(bar_df.head(3))
print(bar_df.dtypes)

# 解析 datetime
dt_col = None
for c in ("datetime", "date_time", "timestamp"):
    if c in bar_df.columns:
        dt_col = c
        break
bar_df["dt"] = pd.to_datetime(bar_df[dt_col])
bar_df = bar_df.sort_values("dt").reset_index(drop=True)
bar_df = bar_df.set_index("dt")
print(f"\n  时间范围: {bar_df.index.min()} ~ {bar_df.index.max()}")

# ── 构造 1d ATR daily_atr_bps ──
# 先用 5m bar 聚合日 bar：open=first, high=max, low=min, close=last, volume=sum
day_df = bar_df.resample("1D").agg({
    "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
}).dropna(subset=["open"])
print(f"  聚合 {len(day_df)} 个交易日")

# 计算 TR / ATR(10) / daily_atr_bps
day_df["prev_close"] = day_df["close"].shift(1)
day_df["tr"] = pd.concat([
    (day_df["high"] - day_df["low"]).abs(),
    (day_df["high"] - day_df["prev_close"]).abs(),
    (day_df["low"] - day_df["prev_close"]).abs(),
], axis=1).max(axis=1)
day_df["atr_10"] = day_df["tr"].rolling(10, min_periods=10).mean()
day_df["daily_atr_bps"] = day_df["atr_10"] / day_df["prev_close"] * 10000  # bps
print(f"  daily_atr_bps 有效值: {day_df['daily_atr_bps'].notna().sum()}")

# ── 模拟策略缓冲区逻辑 ──
# 按之前路径B策略实现：每个交易日完成时，结算 A3_skew + daily_atr_bps，然后重复 append N=6 次
# 然后每段首/整点重算 tier

N_REPEAT = 6
W_SKEW = W_ATR = W_TREND = 10
TREND_ENTRY_WIN = 10  # trend_ret_M 的 M = trend_entry_win

skews = deque(maxlen=40 * N_REPEAT)
atrs = deque(maxlen=40 * N_REPEAT)
closes = deque(maxlen=40 * N_REPEAT)

records = []  # 记录每个对齐点的 r_s/r_a/r_t/trans/tier/dir

# 按 (年, 月, 日) 分组 session
bar_df["date"] = bar_df.index.date
prev_date = None

for d, session in bar_df.groupby("date", sort=True):
    # 新交易日：先结算上一个 session
    if prev_date is not None:
        # 结算 prev session 的 A3_skew
        session_closes = session_prev["close"].to_numpy(dtype=float)
        session_vols = session_prev["volume"].to_numpy(dtype=float)
        # A3_skew：量加权偏度
        from strategies.classifiers.poc_va import volume_weighted_skew
        a3 = volume_weighted_skew(session_closes, session_vols)
        # 前一交易日的 daily_atr_bps
        prev_day_row = day_df.loc[day_df.index.date == prev_date]
        atr_bps = float("nan")
        if len(prev_day_row) > 0:
            v = prev_day_row["daily_atr_bps"].iloc[0]
            if pd.notna(v):
                atr_bps = float(v)
        # close = 上一 session 最后的 close
        prev_close = float(session_prev["close"].iloc[-1]) if len(session_prev) else float("nan")
        # 重复 append N 次 + 微扰
        HALF_EPS = 1e-10
        mid = 0.5 * (N_REPEAT - 1)
        if np.isfinite(a3):
            for j in range(N_REPEAT):
                delta = (float(j) - mid) * HALF_EPS * max(1.0, abs(a3))
                skews.append(a3 + delta)
        if np.isfinite(atr_bps):
            for j in range(N_REPEAT):
                delta = (float(j) - mid) * HALF_EPS * max(1.0, abs(atr_bps))
                atrs.append(atr_bps + delta)
        if np.isfinite(prev_close):
            for j in range(N_REPEAT):
                delta = (float(j) - mid) * HALF_EPS * max(1.0, prev_close)
                closes.append(prev_close + delta)
    # 重算 tier（每个"对齐点"一次）—— 研究侧当日 6 个整点 = 6 次重算
    # 我们直接对当前缓冲区算 6 次 tier（等价 hourly_idx 同值推进 6 次）
    if len(skews) >= W_SKEW and len(atrs) >= W_ATR and len(closes) >= (TREND_ENTRY_WIN + W_TREND - 1):
        s_skew = pd.Series(list(skews), dtype=float)
        s_atr = pd.Series(list(atrs), dtype=float)
        t_vals = []
        off = TREND_ENTRY_WIN - 1
        for i in range(off, len(closes)):
            c0 = float(closes[i - off])
            c1 = float(closes[i])
            if c0 > 0 and c1 > 0:
                t_vals.append(float(np.log(c1 / c0)))
            else:
                t_vals.append(float("nan"))
        s_trend = pd.Series(t_vals, dtype=float)
        # 算当前 r_s / r_a / r_t / trans
        r_s_raw = roll_t_pit(s_skew, W_SKEW)
        r_s = 1.0 - (float(r_s_raw.iloc[-1]) if len(r_s_raw) and pd.notna(r_s_raw.iloc[-1]) else float("nan"))
        r_a_ser = roll_t_pit(s_atr, W_ATR)
        r_a = float(r_a_ser.iloc[-1]) if len(r_a_ser) and pd.notna(r_a_ser.iloc[-1]) else float("nan")
        r_t_ser = roll_t_pit(s_trend, W_TREND)
        r_t = float(r_t_ser.iloc[-1]) if len(r_t_ser) and pd.notna(r_t_ser.iloc[-1]) else float("nan")
        trans = "stable"
        if len(r_a_ser) and r_a_ser.notna().any():
            tdf = compute_transition_series(r_a_ser)
            trans = str(tdf["trans"].iloc[-1])
        tier = None
        if np.isfinite(r_s) and np.isfinite(r_a) and np.isfinite(r_t):
            tier = classify_tier(float(r_s), float(r_a), float(r_t), trans)
        direction = tier_direction(tier)
        records.append({
            "date": d,
            "r_s": r_s, "r_a": r_a, "r_t": r_t,
            "trans": trans, "tier": tier, "dir": direction,
            "skew_buf_len": len(skews), "atr_buf_len": len(atrs), "close_buf_len": len(closes),
        })
        # 模拟研究侧每小时推进一次 trans/age：再重算 5 次（共 6 次/日）
        for extra in range(5):
            # 在重复 6 行的情况下，每小时推进相当于把"最新的一行"（最后 append 的）
            # 再 append 一遍？不，研究侧 hourly_idx 同日值不变 → rank/trans 基于相同的
            # 重复行序列推进。我们这里简单做法：取当前 r_a_ser，compute_transition_series
            # 后，记录 age 的推进情况 + 再 classify 一次看 tier 是否变化
            tdf = compute_transition_series(r_a_ser)
            trans_2 = str(tdf["trans"].iloc[-1])
            age_2 = int(tdf["age"].iloc[-1])
            tier_2 = None
            if np.isfinite(r_s) and np.isfinite(r_a) and np.isfinite(r_t):
                tier_2 = classify_tier(float(r_s), float(r_a), float(r_t), trans_2)
            direction_2 = tier_direction(tier_2)
            records.append({
                "date": d,
                "r_s": r_s, "r_a": r_a, "r_t": r_t,
                "trans": trans_2, "tier": tier_2, "dir": direction_2,
                "skew_buf_len": len(skews), "atr_buf_len": len(atrs), "close_buf_len": len(closes),
                "hourly_idx": extra + 1,
                "age": age_2,
            })

    prev_date = d
    session_prev = session

# ── 统计汇总 ──
print(f"\n{'='*70}")
print(f"路径B修复 roll_t_pit 后单合约 (SHFE.rb2501) tier 生成统计")
print(f"{'='*70}")
rdf = pd.DataFrame(records)
print(f"  总对齐点记录数: {len(rdf)}")
print(f"  交易日日数:      {rdf['date'].nunique()}")
# r 值极端占比
for col in ("r_s", "r_a", "r_t"):
    v = rdf[col].dropna()
    ext = ((v > 0.9) | (v < 0.1)).sum() / len(v) * 100 if len(v) else 0
    print(f"  {col} 极端(>0.9 或 <0.1)占比: {ext:.2f}%  (n={len(v)}, min={v.min():.3f}, max={v.max():.3f})")
# tier 非 None 占比
has_tier = rdf["tier"].notna().sum()
has_dir = (rdf["dir"] != "").sum()
print(f"\n  tier非None: {has_tier} / {len(rdf)} = {has_tier/len(rdf)*100:.2f}%")
print(f"  dir非空:   {has_dir} / {len(rdf)} = {has_dir/len(rdf)*100:.2f}%")
# tier 分布
if has_tier > 0:
    print("  tier 分布:")
    print(rdf["tier"].value_counts().to_string())
# dir 分布
print("  dir 分布:")
print(rdf["dir"].value_counts(dropna=False).to_string())
# 打印最近 30 行
print(f"\n最近 30 条记录:")
with pd.option_context("display.width", 180, "display.max_columns", 20, "display.float_format", "{:.4f}".format):
    print(rdf.tail(30).to_string())
