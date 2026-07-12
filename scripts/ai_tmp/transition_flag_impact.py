"""一次性：验证 transition_flag 维度是否重要。
数据无该列，按 poc classifier-math-spec §6.4 自算，再在每个 tier 内对比 flag=0 vs 1 的收益。

算法（§6.4）:
  atr_bucket_session(s,d) = 分档(atr_rank_roll) 低<=0.33 / 中 / 高>=0.67  (session级近似)
  is_crossover(s,d)       = bucket(d) != bucket(prev_session)
  transition_flag(s,t)    = 1 if 过去 n(=3) 个 session 内(含当天)发生过 crossover
"""
import pandas as pd
import numpy as np

try:
    from scipy import stats
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

PATH = "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet"
N_TRANS = 3  # n_transition_window_days

df = pd.read_parquet(PATH)
skew, atr, trend = "signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"
df = df.dropna(subset=[skew, atr, trend, "date"]).copy()

# ---------- 1) session 级 ATR 桶 & transition_flag（per contract）----------
def bucket(x):
    if x <= 0.33: return 0
    if x >= 0.67: return 2
    return 1

# 每个 (contract,date) 一个 session 桶（同日取该日 atr_rank_roll 均值再分档）
sess = (df.groupby(["contract", "date"])[atr].mean().reset_index()
          .sort_values(["contract", "date"]))
sess["bkt"] = sess[atr].apply(bucket)
sess["prev_bkt"] = sess.groupby("contract")["bkt"].shift(1)
sess["crossover"] = (sess["prev_bkt"].notna()) & (sess["bkt"] != sess["prev_bkt"])

# transition_flag: 当天或前 N-1 个 session 内有 crossover（session 计数=行序）
parts = []
for c, g in sess.groupby("contract"):
    g = g.sort_values("date").reset_index(drop=True)
    cross_idx = np.where(g["crossover"].values)[0]
    flag = np.zeros(len(g), dtype=int)
    for ci in cross_idx:
        flag[ci: ci + N_TRANS] = 1  # crossover 影响 [ci, ci+N-1]
    g["transition_flag"] = flag
    parts.append(g)
sess = pd.concat(parts, ignore_index=True)
df = df.merge(sess[["contract", "date", "transition_flag"]], on=["contract", "date"], how="left")

print("=" * 78)
print(f"总行: {len(df)}  合约: {df['contract'].nunique()}")
print(f"transition_flag=1 占比: {df['transition_flag'].mean()*100:.1f}%  "
      f"(poc 洞察R 报 ~46%)")
print("=" * 78)

# ---------- 2) tier 判定（§1.2 六 tier）----------
def I(lo, hi, li, hi_):
    return (lo, hi, li, hi_)
tiers = {
    "L_seg3_lowmid_up": (I(0.09,0.30,0,1), I(0.00,0.67,1,1), I(0.75,1.00,1,1), "L"),
    "L_seg12_high_up":  (I(0.00,0.19,1,1), I(0.67,1.00,0,1), I(0.75,1.00,1,1), "L"),
    "L_seg2_low_flat":  (I(0.09,0.19,0,1), I(0.00,0.33,1,1), I(0.20,0.75,0,0), "L"),
    "S_seg12_high_dn":  (I(0.81,1.00,1,1), I(0.67,1.00,0,1), I(0.00,0.20,1,1), "S"),
    "S_seg34_high_dn":  (I(0.60,0.81,1,1), I(0.67,1.00,0,1), I(0.00,0.20,1,1), "S"),
    "S_seg2_mid_dn":    (I(0.81,0.91,0,1), I(0.33,0.67,0,1), I(0.00,0.20,1,1), "S"),
}
def hit(x, iv):
    lo, hi, li, hi_ = iv
    if (x < lo) if li else (x <= lo): return False
    if (x > hi) if hi_ else (x >= hi): return False
    return True
def classify(r):
    for name,(s,a,t,_) in tiers.items():
        if hit(r[skew],s) and hit(r[atr],a) and hit(r[trend],t):
            return name
    return "NONE"
df["_tier"] = df.apply(classify, axis=1)

# ---------- 3) 每 tier 内 flag=0 vs 1 收益对比 ----------
print(f"\n{'tier':<18}{'dir':<4}{'ret列':<16}"
      f"{'n_stable':>9}{'n_trans':>8}"
      f"{'mean_stable':>12}{'mean_trans':>12}{'Δ(t-s)':>9}{'p':>9}")
print("-" * 98)
for name,(s,a,t,direction) in tiers.items():
    sub = df[df["_tier"] == name]
    retcol = "ret_8h_bps" if direction == "L" else "short_pnl_4h_bps"
    g0 = sub[sub["transition_flag"] == 0][retcol].dropna()
    g1 = sub[sub["transition_flag"] == 1][retcol].dropna()
    m0 = g0.mean() if len(g0) else float("nan")
    m1 = g1.mean() if len(g1) else float("nan")
    if HAVE_SCIPY and len(g0) > 5 and len(g1) > 5:
        _, p = stats.ttest_ind(g1, g0, equal_var=False)
    else:
        p = float("nan")
    print(f"{name:<18}{direction:<4}{retcol:<16}"
          f"{len(g0):>9}{len(g1):>8}"
          f"{m0:>12.1f}{m1:>12.1f}{m1-m0:>9.1f}{p:>9.3f}")

print("\n" + "=" * 78)
print("判读：Δ 大且 p<0.05 → transition_flag 在该 tier 内确实把收益分成两种（该维重要）")
print("      Δ 小或 p>0.05 → 该 tier 内 flag 不改变收益（对该 tier 不重要）")
print("=" * 78)
