"""单合约(SHFE.rb2501) R侧 vs E侧 分类器输入三序列逐元素对比。

Purpose:
    精确定位 A(skew日期) B(atr单位) C(close日期) 三个差异点的实际影响。
    取单个合约SHFE.rb2501，完整重建：
    1) R侧 build_events → merge daily_features → 原始三列(A3_skew_spec,daily_atr_spec,trend_ret_M_spec)
       → evaluate_dataset 内部 r_s/r_a/r_t 计算过程（包含重复6次/每小时推进）
    2) E侧 _on_new_day skew/atr/close deque append ×6 → _recompute_tier 内部序列
       → 逐行 r_s_raw/r_a_raw/r_t_raw 输出
    两者在 (contract, R事件点时刻) 维度对齐，对比每一个 tier/dir 命中点的输入。

Output:
    project_data/ai_tmp/R_E_single_contract_inputs_SHFE.rb2501.parquet
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "workspace"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docs", "workbench", "va-asymmetry-composite", "scripts"))

import pandas as pd
import numpy as np
from math import log
from pathlib import Path
from strategies.classifiers.poc_va import (
    ClassifierConfig, roll_t_pit, compute_transition_series,
    classify_tier, tier_direction, volume_weighted_skew, daily_atr_sma,
    trend_log_return,
)
import reproduce_research_side as R

CONTRACT = "SHFE.rb2501"
R_DIR = "/Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-composite/outputs/reproduce-research-side"
CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")

config = ClassifierConfig()  # 全默认

# ── 1. R侧：完整重建 SHFE.rb2501 的 evaluate_dataset 输入 df ──
print(f"[1/4] R侧重建 {CONTRACT} 事件序列...")
tick = R.get_tick(CONTRACT)
ev = R.build_events(CONTRACT, tick)
daily = R.build_daily_features(CONTRACT)
print(f"  build_events: {len(ev)} 行 hourly 事件  |  daily_features: {len(daily)} 行")
ev = ev.merge(daily, left_on="event_date", right_on="date", how="left")
ev["event_time"] = pd.to_datetime(ev["event_time"])
ev["event_date"] = pd.to_datetime(ev["event_date"])
ev = ev.sort_values("event_time").reset_index(drop=True)
# warmup 过滤（同 reproduce）
ev["signed_skew"] = -ev["A3_skew"]
ev["signed_skew_rank_roll"] = R.rolling_pct_rank(ev["signed_skew"], 100)
daily_g = ev.drop_duplicates("event_date").sort_values("event_date").copy()
daily_g["atr_rank_roll"] = R.rolling_pct_rank(daily_g["daily_atr_10_bps"], R.ROLLING_DAYS)
daily_g["trend_rank_roll"] = R.rolling_pct_rank(daily_g["trend_ret_10d"], R.ROLLING_DAYS)
ev = ev.merge(daily_g[["event_date","atr_rank_roll","trend_rank_roll"]], on="event_date", how="left")
dates = sorted(ev["event_date"].unique())
if len(dates) >= R.WARMUP_DAYS:
    wend = dates[R.WARMUP_DAYS - 1]
    ev = ev[ev["event_date"] > wend].reset_index(drop=True)
ev = ev.dropna(subset=["signed_skew_rank_roll","atr_rank_roll","trend_rank_roll"]).reset_index(drop=True)
print(f"  warmup + rank 非空后: {len(ev)} 行 hourly")
print(f"  列: {list(ev.columns)}")

# 喂给分类器的原始三列（R侧evaluate_dataset输入）
print("\n[2/4] R侧 evaluate_dataset 内部: 每小时重算 tier 过程拆解...")
# 手动复刻 build_coordinates: 把 ev 的三列按 contract(只有1个) 分组，然后:
#   r_s_raw[i] = roll_t_pit(A3_skew_spec[:i+1], 10)[i]  → 1-r_s_raw = r_s
#   r_a_raw[i] = roll_t_pit(daily_atr_spec[:i+1], 10)[i]
#   r_t_raw[i] = roll_t_pit(trend_ret_M_spec[:i+1], 10)[i] （trend列需要先算，注意这里trend_ret_M_spec已经是预计算好的 log(closeD/closeD-9)）
#   然后 trans = compute_transition_series(r_a_raw)
#   然后 classify_tier(r_s, r_a, r_t, trans)
# 注意: ev 每行是 hourly（同天6次 skew/daily_atr/trend 值完全相同），所以 ev 内部本身就是 "每日重复6次" 的序列！
n = len(ev)
r_s_raw = roll_t_pit(ev["A3_skew_spec"].astype(float), config.skew_rank_win)
r_s_series = 1.0 - r_s_raw
r_a_series = roll_t_pit(ev["daily_atr_spec"].astype(float), config.atr_rank_win)
# 注意: trend_ret_M_spec 是预计算的 10 日 log return，直接输入 roll_t_pit 即可（不用再算 close 了）
r_t_series = roll_t_pit(ev["trend_ret_M_spec"].astype(float), config.trend_win)
# compute trans
trans_df = compute_transition_series(r_a_series)
ev["R_r_s_raw"] = r_s_raw
ev["R_r_s"] = r_s_series
ev["R_r_a"] = r_a_series
ev["R_r_t"] = r_t_series
ev["R_trans"] = trans_df["trans"].astype(str).values
ev["R_tier"] = [classify_tier(float(rs), float(ra), float(rt), str(tr))
                if pd.notna(rs) and pd.notna(ra) and pd.notna(rt) else None
                for rs, ra, rt, tr in zip(ev["R_r_s"], ev["R_r_a"], ev["R_r_t"], ev["R_trans"])]
ev["R_dir"] = ev["R_tier"].map(lambda t: tier_direction(str(t)) if isinstance(t, str) else None)
# 只取 R 侧在 events.parquet 中实际命中 tier 的行（980行子集）
ev_tier_hit = ev[ev["R_tier"].notna()].copy().reset_index(drop=True)
print(f"  {CONTRACT} 逐小时独立算 tier 后, tier命中行: {len(ev_tier_hit)} (在 events.parquet 中该合约7行)")
print(f"  原始ev_tier_hit 按DEDUP_H=8h过滤:")
prev = ev_tier_hit["event_time"].shift(1)
ev_tier_hit_dedup = ev_tier_hit[(prev.isna()) | ((ev_tier_hit["event_time"] - prev) > pd.Timedelta(hours=R.DEDUP_H))].reset_index(drop=True)
print(f"  DEDUP后: {len(ev_tier_hit_dedup)} 行")
print(ev_tier_hit_dedup[["event_time","A3_skew_spec","daily_atr_spec","trend_ret_M_spec","R_r_s","R_r_a","R_r_t","R_trans","R_tier","R_dir"]].head(10).to_string())

# ── 3. E侧：模拟 _on_new_day append ×N 缓冲区 + _recompute_tier ──
print("\n[3/4] E侧 模拟 _on_new_day N=6 重复 + 整点/段首 recompute_tier...")
# 从5m CSV重建 session bars（和策略侧 _on_new_day 从 state extra va_session_5m_bars 累积等价）
csv_p = CSV_DIR / f"{CONTRACT}.tqsdk.5m.csv"
bars = pd.read_csv(csv_p, usecols=["datetime","open","high","low","close","volume"])
bars["datetime"] = pd.to_datetime(bars["datetime"])
bars = bars.sort_values("datetime").reset_index(drop=True)
bars["date"] = bars["datetime"].dt.date
# 按自然日切 session（和策略侧一样，按自然日切 = 每日结算一次 skew/closes）
# 注: 策略侧 _on_new_day 结算的是"昨日" session，因为在新day首bar时昨日bars已经全部在va_session_5m_bars中
# 但是！R侧 merge daily 的 A3_skew_spec = date=event_date 当天 session skew（不是前一天），所以 R侧 skew 是"当日"skew
# 让我核对一下: R侧 build_daily_features 中 a3_map[date_val] = volume_weighted_skew(当日所有5m bars)
# 然后 ev.merge(daily, left_on="event_date", right_on="date") → 所以 A3_skew_spec=event_date当天skew（当日session skew，不是前一天）
# 这个是核心差异A: E侧目前append的是"昨日session skew"（_on_new_day 在新day首bar结算昨日），但R侧用的是"当日session skew"
# 先打印几行核对，确认这个差异

# 生成 (date → 当日session skew / atr_abs / close) 表供 E 侧使用
daily_rows = []
for date_val, g in bars.groupby("date"):
    g = g.sort_values("datetime").reset_index(drop=True)
    if len(g) < 20:
        continue
    sk = float(volume_weighted_skew(g["close"].to_numpy(dtype=float), g["volume"].to_numpy(dtype=float)))
    daily_rows.append({
        "date": pd.Timestamp(date_val),
        "sk_session": sk,
        "close_session": float(g["close"].iloc[-1]),
        "open": float(g["open"].iloc[0]),
        "high": float(g["high"].max()),
        "low": float(g["low"].min()),
        "vol_sum": float(g["volume"].sum()),
        "nbars": len(g),
    })
df_daily = pd.DataFrame(daily_rows).sort_values("date").reset_index(drop=True)
df_daily["atr_sma10_abs"] = daily_atr_sma(df_daily["high"], df_daily["low"], df_daily["close_session"], 10)
# trend_ret_M_spec (R侧预计算): log(closeD / close_{D-9})
df_daily["trend_log_M"] = trend_log_return(df_daily["close_session"], 10)
# atr_bps for E侧 (策略侧 DAILY_ATR_BPS 指标≈atr_sma10_abs/close_session*10000)
df_daily["atr_bps_e"] = df_daily["atr_sma10_abs"] / df_daily["close_session"] * 10000.0
print(f"  df_daily: {len(df_daily)} 行")
print(df_daily[["date","sk_session","atr_sma10_abs","atr_bps_e","close_session","trend_log_M"]].head(15).to_string())

# 和 R侧 daily 合并核对是否一致
r_daily = daily.copy().sort_values("date").reset_index(drop=True)
r_daily["date"] = pd.to_datetime(r_daily["date"])
cmp_daily = df_daily.merge(r_daily, on="date", how="inner")
print(f"\n  cmp_daily merged: {len(cmp_daily)} 行")
print(f"  skew 对比 (E sk_session vs R A3_skew_spec):")
dsk = (cmp_daily["sk_session"] - cmp_daily["A3_skew_spec"]).abs()
print(f"    max|Δ| = {dsk.max():.2e}, mean = {dsk.mean():.2e}, match@1e-6 = {(dsk<=1e-6).sum()}/{len(dsk)}")
print(f"  atr 对比 (E atr_sma10_abs vs R daily_atr_spec):")
datr = (cmp_daily["atr_sma10_abs"] - cmp_daily["daily_atr_spec"]).abs()
print(f"    max|Δ| = {datr.max():.2e}, mean = {datr.mean():.2e}, match@1e-6 = {(datr<=1e-6).sum()}/{len(datr)}")
print(f"  trend 对比 (E trend_log_M vs R trend_ret_M_spec):")
dtr = (cmp_daily["trend_log_M"] - cmp_daily["trend_ret_M_spec"]).abs()
print(f"    max|Δ| = {dtr.max():.2e}, mean = {dtr.mean():.2e}, match@1e-6 = {(dtr<=1e-6).sum()}/{len(dtr)}")

# 现在模拟 E侧 _on_new_day: 每日结算 "昨日session skew"（当前策略实现） vs 改为"当日session skew"（对齐R侧）
# 两种模式都跑
HALF_EPS = 1e-10

def simulate_E_input(mode: str):
    """mode = 'yesterday'（当前E实现） | 'today'（对齐R实现）"""
    skews = []
    atrs_abs = []
    atrs_bps = []
    closes = []
    # E_on_new_day 按日期顺序（warmup前也append，但recompute_tier时窗口够才输出有效r值）
    # 先遍历 ev 的所有 event_time 对齐点，每个对齐点"当时"的deque状态
    # 简化：按日期遍历，每日根据 mode append N=6 次 skew/atr/close
    N = 6
    mid = 0.5 * float(N - 1)
    seq_rows = []
    for i, drow in df_daily.iterrows():
        d = drow["date"]
        # _on_new_day 在 d 的首 bar 被触发，结算 d-1 的 session bars
        # mode='yesterday': append d-1 的值
        # mode='today': append d 的值（对齐R A3_skew_spec = d当天值）
        if mode == "yesterday":
            if i == 0:
                sk_v = np.nan; atr_a_v = np.nan; atr_b_v = np.nan; cl_v = np.nan
            else:
                sk_v = df_daily["sk_session"].iloc[i-1]
                atr_a_v = df_daily["atr_sma10_abs"].iloc[i-1]
                atr_b_v = df_daily["atr_bps_e"].iloc[i-1]
                cl_v = df_daily["close_session"].iloc[i-1]
        else:  # today
            sk_v = drow["sk_session"]
            atr_a_v = drow["atr_sma10_abs"]
            atr_b_v = drow["atr_bps_e"]
            cl_v = drow["close_session"]
        for j in range(N):
            delta = (float(j) - mid) * HALF_EPS * max(1.0, abs(sk_v)) if np.isfinite(sk_v) else np.nan
            skews.append(sk_v + delta if np.isfinite(sk_v) else np.nan)
            delta2 = (float(j) - mid) * HALF_EPS * max(1.0, abs(atr_a_v)) if np.isfinite(atr_a_v) else np.nan
            atrs_abs.append(atr_a_v + delta2 if np.isfinite(atr_a_v) else np.nan)
            delta3 = (float(j) - mid) * HALF_EPS * max(1.0, abs(atr_b_v)) if np.isfinite(atr_b_v) else np.nan
            atrs_bps.append(atr_b_v + delta3 if np.isfinite(atr_b_v) else np.nan)
            delta4 = (float(j) - mid) * HALF_EPS * max(1.0, cl_v) if np.isfinite(cl_v) else np.nan
            closes.append(cl_v + delta4 if np.isfinite(cl_v) else np.nan)
        # 注意: R侧 hourly = ev的行数（每日约6行整点），R侧 skew/atr/trend 当日值完全相同（daily merge），没有微扰
        # R侧 skew/atr/trend 序列 = 每日重复6次的d当天值（无1e-10微扰） → 先不用微扰
    skews_s = pd.Series(skews, dtype=float)
    atrs_abs_s = pd.Series(atrs_abs, dtype=float)
    atrs_bps_s = pd.Series(atrs_bps, dtype=float)
    closes_s = pd.Series(closes, dtype=float)
    # trend（策略侧_recompute_tier计算）: 对 closes buffer 的每个索引 i（>=trend_offset=9）算 log(closes[i]/closes[i-9])
    n_closes = len(closes_s)
    trend_offset = config.trend_entry_win - 1  # 9
    t_vals = [np.nan] * n_closes
    for i in range(trend_offset, n_closes):
        c0 = float(closes_s.iloc[i - trend_offset])
        c1 = float(closes_s.iloc[i])
        if c0 > 0 and c1 > 0:
            t_vals[i] = float(log(c1 / c0))
    trend_s = pd.Series(t_vals, dtype=float)
    return skews_s, atrs_abs_s, atrs_bps_s, closes_s, trend_s

# 跑两种E模式，再加上 R侧 ev 的序列（作为真值）
print("\n  三种模式: R_ev_true(每小时序列) | E_today(R对齐: 当日值+N=6重复) | E_yesterday(当前实现: 昨日值+N=6重复)")
R_sk = ev["A3_skew_spec"].astype(float).reset_index(drop=True)
R_at = ev["daily_atr_spec"].astype(float).reset_index(drop=True)
R_tr = ev["trend_ret_M_spec"].astype(float).reset_index(drop=True)

# 把 df_daily 每日重复6次生成 E_today_raw_noperturb（对应R侧当日无perturb）
N = 6
_sk_l = []; _at_l = []; _tr_l = []; _cl_l = []; _date_l = []
for i, drow in df_daily.iterrows():
    d = drow["date"]
    for j in range(N):
        _sk_l.append(float(drow["sk_session"]))
        _at_l.append(float(drow["atr_sma10_abs"]))
        _tr_l.append(float(drow["trend_log_M"]) if pd.notna(drow["trend_log_M"]) else np.nan)
        _cl_l.append(float(drow["close_session"]))
        _date_l.append(d)
E_today_nopert = pd.DataFrame({
    "date": _date_l, "A3_skew": _sk_l, "atr_abs": _at_l, "trend_M": _tr_l, "close": _cl_l,
})
print(f"  R hourly len={len(ev)} event dates={ev['event_date'].nunique()}")
print(f"  E_today_nopert len={len(E_today_nopert)} total dates={df_daily['date'].nunique()}")

# 现在构建对齐表：以 ev 的 event_time 为基准，找到每个 R_ev 行在 E_today_nopert 序列中对应位置（相同date + j=hourly次序）
# 简化: 按 date 分组，对同一天 R 侧的 hourly 行（09:00,10:00,11:00,13:30,14:00...）按顺序对应 E_today_nopert 同一天的j=0..5
ev["date"] = ev["event_date"]
align_rows = []
for (d, grp) in ev.groupby("date", sort=True):
    grp = grp.sort_values("event_time").reset_index(drop=True)
    Etoday_sub = E_today_nopert[E_today_nopert["date"] == d].reset_index(drop=True)
    # 取 min(len(grp), len(Etoday_sub)) 行对应
    k = min(len(grp), len(Etoday_sub))
    for j in range(k):
        r_row = grp.iloc[j]
        e_row = Etoday_sub.iloc[j]
        align_rows.append({
            "contract": CONTRACT, "event_time": r_row["event_time"], "date": d,
            # R侧真值
            "R_skew": float(r_row["A3_skew_spec"]),
            "R_atr_abs": float(r_row["daily_atr_spec"]),
            "R_trend": float(r_row["trend_ret_M_spec"]) if pd.notna(r_row["trend_ret_M_spec"]) else np.nan,
            "R_r_s": float(r_row["R_r_s"]) if pd.notna(r_row["R_r_s"]) else np.nan,
            "R_r_a": float(r_row["R_r_a"]) if pd.notna(r_row["R_r_a"]) else np.nan,
            "R_r_t": float(r_row["R_r_t"]) if pd.notna(r_row["R_r_t"]) else np.nan,
            "R_trans": str(r_row["R_trans"]),
            "R_tier": str(r_row["R_tier"]) if pd.notna(r_row["R_tier"]) else None,
            "R_dir": str(r_row["R_dir"]) if pd.notna(r_row["R_dir"]) else None,
            # E_today_nopert 对齐（当日值，无1e-10微扰）
            "E_today_skew": float(e_row["A3_skew"]),
            "E_today_atr_abs": float(e_row["atr_abs"]),
            "E_today_trend": float(e_row["trend_M"]) if pd.notna(e_row["trend_M"]) else np.nan,
        })
align_df = pd.DataFrame(align_rows)
print(f"  对齐行: {len(align_df)}")

# 在 E_today_nopert 的全序列上跑 roll_t_pit + compute_transition + classify_tier，然后回到对齐行索引
# 先算全序列 r 值
sk_all = E_today_nopert["A3_skew"].astype(float)
at_all = E_today_nopert["atr_abs"].astype(float)
tr_all = E_today_nopert["trend_M"].astype(float)
Et_rs_raw = roll_t_pit(sk_all, 10)
Et_rs = 1.0 - Et_rs_raw
Et_ra = roll_t_pit(at_all, 10)
Et_rt = roll_t_pit(tr_all, 10)
Et_trans_df = compute_transition_series(Et_ra)
E_today_nopert["E_rs"] = Et_rs
E_today_nopert["E_ra"] = Et_ra
E_today_nopert["E_rt"] = Et_rt
E_today_nopert["E_trans"] = Et_trans_df["trans"].astype(str).values
E_today_nopert["E_tier"] = [
    classify_tier(float(rs), float(ra), float(rt), str(tr))
    if pd.notna(rs) and pd.notna(ra) and pd.notna(rt) else None
    for rs, ra, rt, tr in zip(Et_rs, Et_ra, Et_rt, E_today_nopert["E_trans"])
]
E_today_nopert["E_dir"] = E_today_nopert["E_tier"].map(lambda t: tier_direction(t) if t else None)

# 再 merge 回 align_df（按 date + 组内次序 j）
def _add_pos(df, grpby_col="date"):
    out = []
    for _, g in df.groupby(grpby_col, sort=True):
        g = g.copy().reset_index(drop=True)
        g["_j"] = np.arange(len(g))
        out.append(g)
    return pd.concat(out, ignore_index=True)
a_df = _add_pos(align_df)
e_df = _add_pos(E_today_nopert)
m_df = a_df.merge(
    e_df[["date","_j","E_rs","E_ra","E_rt","E_trans","E_tier","E_dir"]],
    on=["date","_j"], how="left", suffixes=("","_E")
)
print(f"\n  align merge: {len(m_df)}")

# 对比 (R侧 vs E_today 对齐) 的 r_s/r_a/r_t/trans/tier/dir 一致性
print(f"\n{'='*80}\n{CONTRACT} R侧 vs E_today(当日skew/atr/close, 每日重复6次, 无微扰) 分类一致性\n{'='*80}")
def _cmp(col, tol=1e-6):
    r_col = f"R_{col}"
    e_col = f"E_{col}"
    if col in ("tier","trans","dir"):
        r = m_df[r_col].fillna("(NA)")
        e = m_df[e_col].fillna("(NA)")
        m = (r == e).sum()
        print(f"  {col:<6}: {m}/{len(r)} = {m/len(r)*100:.1f}%")
        mism = (r != e).sum()
        if mism:
            print(f"       不一致样本(前5):")
            bad = m_df[r != e].head(5)
            print(bad[["event_time",r_col,e_col,"R_skew","E_today_skew","R_r_s","E_rs"]].to_string(index=False))
    else:
        r = pd.to_numeric(m_df[r_col], errors="coerce")
        e = pd.to_numeric(m_df[e_col], errors="coerce")
        bnan = r.isna() != e.isna()
        bval = (~r.isna() & ~e.isna() & ((r - e).abs() > tol))
        bad = (bnan | bval).sum()
        m = len(r) - bad
        print(f"  r_{col:<5}: {m}/{len(r)} = {m/len(r)*100:.1f}%   max|Δ| = {(r-e).abs().max():.2e}")
        if bad:
            print(f"       不一致样本(前3):")
            bidx = (bnan | bval)
            bad_df = m_df[bidx].head(3)
            print(bad_df[["event_time",r_col,e_col]].to_string(index=False))
for c in ["s","a","t","trans","tier","dir"]:
    _cmp(c)

# 再看 tier 命中的行（R侧实际产生信号的行）
m_tier_hit = m_df[m_df["R_tier"].fillna("") != "None"].copy().reset_index(drop=True)
print(f"\n  R侧实际产生 tier 命中的行: {len(m_tier_hit)}")
print(m_tier_hit[["event_time","R_tier","E_tier","R_r_s","E_rs","R_r_a","E_ra","R_r_t","E_rt","R_trans","E_trans"]].head(10).to_string())

# 最后保存
out_dir = "/Users/gaolei/Documents/src/quant/project_data/ai_tmp/R_E_single_contract_inputs"
os.makedirs(out_dir, exist_ok=True)
m_df.to_parquet(f"{out_dir}/{CONTRACT}_R_E_align.parquet", index=False)
E_today_nopert.to_parquet(f"{out_dir}/{CONTRACT}_E_today_seq.parquet", index=False)
ev.to_parquet(f"{out_dir}/{CONTRACT}_R_ev_seq.parquet", index=False)
cmp_daily.to_parquet(f"{out_dir}/{CONTRACT}_cmp_daily.parquet", index=False)
print(f"\n[4/4] 所有明细保存: {out_dir}/")
