"""一次性：三个盘前特征的相关性诊断。
验证假设：原始值绝对值(幅度)高度相关，但有符号(方向)相关性较弱。
"""
import pandas as pd
import numpy as np

PATH = "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet"

df = pd.read_parquet(PATH)

rank_cols = ["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"]
raw_cols = ["A3_skew", "daily_atr_10_bps", "trend_ret_10d"]

print("=" * 70)
print(f"总行数: {len(df)}, 合约数: {df['contract'].nunique()}")
print("列检查:", [c for c in rank_cols + raw_cols if c in df.columns])
missing = [c for c in rank_cols + raw_cols if c not in df.columns]
if missing:
    print("!!! 缺列:", missing)
print("=" * 70)

def show_corr(frame, cols, title, method="pearson"):
    sub = frame[cols].dropna()
    print(f"\n### {title}  (n={len(sub)}, method={method})")
    c = sub.corr(method=method)
    print(c.round(3).to_string())
    return c

# 1) rank 层（文档实际喂给分类器的）
show_corr(df, rank_cols, "1. RANK 相关 (pooled, pearson)")
show_corr(df, rank_cols, "1b. RANK 相关 (pooled, spearman)", method="spearman")

# 2) 原始值 有符号 (方向)
show_corr(df, raw_cols, "2. 原始值 有符号相关 (pooled, pearson)")
show_corr(df, raw_cols, "2b. 原始值 有符号相关 (pooled, spearman)", method="spearman")

# 3) 原始值 绝对值 (幅度) —— 用户核心假设
abs_df = df[raw_cols].abs()
abs_df.columns = [c + "_ABS" for c in raw_cols]
show_corr(abs_df, list(abs_df.columns), "3. 原始值 |绝对值| 相关 (pooled, pearson) [用户假设]")
show_corr(abs_df, list(abs_df.columns), "3b. 原始值 |绝对值| 相关 (pooled, spearman)", method="spearman")

# 4) per-contract 平均相关 (rank 是 per-contract 滚动的, pooled 会混合分布)
print("\n" + "=" * 70)
print("### 4. per-contract 相关的均值/中位数 (更干净)")
for label, cols, use_abs in [
    ("RANK", rank_cols, False),
    ("原始有符号", raw_cols, False),
    ("原始|绝对值|", raw_cols, True),
]:
    mats = []
    for _, g in df.groupby("contract"):
        gg = g[cols].abs() if use_abs else g[cols]
        gg = gg.dropna()
        if len(gg) < 30:
            continue
        mats.append(gg.corr().values)
    if not mats:
        print(f"[{label}] 无足够样本")
        continue
    arr = np.array(mats)
    mean_c = np.nanmean(arr, axis=0)
    med_c = np.nanmedian(arr, axis=0)
    names = [c[:14] for c in cols]
    print(f"\n[{label}] per-contract 平均相关 (n_contracts={len(mats)}):")
    print(pd.DataFrame(mean_c, index=names, columns=names).round(3).to_string())
    print(f"[{label}] per-contract 中位数相关:")
    print(pd.DataFrame(med_c, index=names, columns=names).round(3).to_string())

print("\n" + "=" * 70)
print("完成")
