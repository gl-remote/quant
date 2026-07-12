"""一次性：三个原始特征 归一化后 再看相关性。
归一化 = 逐合约 z-score（消除跨合约量级差），也报全局 z 作对照。
看两层：signed z 相关（线性/单调）、|z| 相关（极端值是否同现）。
"""
import pandas as pd
import numpy as np

PATH = "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet"
df = pd.read_parquet(PATH)

raw = ["A3_skew", "daily_atr_10_bps", "trend_ret_10d"]
znames = [c + "_z" for c in raw]

# 逐合约 z-score（每个合约内减均值/除std）
def zscore_per_group(frame, cols):
    out = frame.copy()
    for c in cols:
        out[c + "_z"] = frame.groupby("contract")[c].transform(lambda s: (s - s.mean()) / s.std())
    return out

# 全局 z-score（线性变换，对 pearson 不变，仅作对照/可视化）
def zscore_global(frame, cols):
    out = frame.copy()
    for c in cols:
        out[c + "_z"] = (frame[c] - frame[c].mean()) / frame[c].std()
    return out

print("=" * 72)
print(f"总行数 {len(df)}, 合约数 {df['contract'].nunique()}")
print("=" * 72)

# ---------- A) 逐合约 z-score ----------
df_p = zscore_per_group(df, raw)
zp = df_p[znames].dropna()
print("\n### A. 逐合约 z-score 后 — SIGNED z 相关 (pooled, pearson)")
print(zp.corr().round(3).to_string())
print("\n### A2. 逐合约 z-score 后 — |z| 相关 (pooled, pearson) [极端值是否同现]")
print(zp.abs().corr().round(3).to_string())

# ---------- B) 全局 z-score（对照） ----------
df_g = zscore_global(df, raw)
zg = df_g[znames].dropna()
print("\n### B. 全局 z-score 后 — SIGNED z 相关 (pooled, pearson)")
print(zg.corr().round(3).to_string())
print("\n### B2. 全局 z-score 后 — |z| 相关 (pooled, pearson)")
print(zg.abs().corr().round(3).to_string())

# ---------- C) per-contract 平均（最干净，避免 pooled 混合） ----------
print("\n" + "=" * 72)
print("### C. per-contract 内 z 相关的 均值/中位数")
for label, use_abs in [("SIGNED z", False), ("|z| (极端值同现)", True)]:
    mats, mats_abs = [], []
    for _, g in df.groupby("contract"):
        gg = g[raw].dropna()
        if len(gg) < 30:
            continue
        z = (gg - gg.mean()) / gg.std()           # 该合约内 z
        mats.append(z.corr().values)
        mats_abs.append(z.abs().corr().values)
    mean_c = np.nanmean(np.array(mats), axis=0)
    med_c = np.nanmedian(np.array(mats), axis=0)
    mean_a = np.nanmean(np.array(mats_abs), axis=0)
    med_a = np.nanmedian(np.array(mats_abs), axis=0)
    sh = [c[:12] for c in raw]
    print(f"\n[{label}] n_contracts={len(mats)}")
    print("  均值(signed):"); print(pd.DataFrame(mean_c, index=sh, columns=sh).round(3).to_string())
    print("  中位数(signed):"); print(pd.DataFrame(med_c, index=sh, columns=sh).round(3).to_string())
    if use_abs:
        print("  均值|z|:"); print(pd.DataFrame(mean_a, index=sh, columns=sh).round(3).to_string())
        print("  中位数|z|:"); print(pd.DataFrame(med_a, index=sh, columns=sh).round(3).to_string())

print("\n" + "=" * 72)
print("完成")
