"""
文件级元信息：
- 创建背景：分析 Step 3 未过 tier 的失败原因分布
- 用途：一次性分析脚本
- 注意事项：临时脚本
"""
import pandas as pd

df = pd.read_csv(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/stage4_step3_144tier_verification.csv"
)

# 全部候选（99）
tot = len(df)
print(f"总候选 tier·period: {tot}")

# 硬门槛 L1-L4 分别失败原因
fail = df[~df["hard_pass"]].copy()
print(f"\nfail 数: {len(fail)} · pass: {len(df) - len(fail)}")

print("\n失败原因分解（L1-L4 每层未过的 tier 数）：")
for L in ["L1", "L2", "L3", "L4"]:
    n_fail = (~fail[L].astype(bool)).sum()
    print(f"  未过 {L}: {n_fail}")

# 只未过某一层
print("\n只因某一层 fail（其余 3 层都过）：")
for L in ["L1", "L2", "L3", "L4"]:
    others = [x for x in ["L1", "L2", "L3", "L4"] if x != L]
    m = (~fail[L].astype(bool)) & fail[others].all(axis=1)
    print(f"  仅 {L} fail: {m.sum()}")

# 仅 L3 fail 的进一步分析：p_boot 有多接近阈值
print("\nBonferroni α = 0.000347")
only_l3 = fail[
    (~fail["L3"].astype(bool))
    & fail["L2"].astype(bool)
    & fail["L4"].astype(bool)
]
print(f"\n仅 L3 fail（Bonferroni 未过 · 其余全过）· {len(only_l3)} 个：")
print(only_l3[["tier_id", "period", "n", "mean_bps", "p_boot"]].sort_values("p_boot").head(30).to_string(index=False))

# p_boot < 0.05 但 > 0.000347 的（"如果 family 小就能过"）
would_pass_005 = fail[(fail["p_boot"] < 0.05) & (fail["p_boot"] >= 0.000347)]
print(f"\np_boot < 0.05 但未过 Bonferroni: {len(would_pass_005)}")
would_pass_001 = fail[(fail["p_boot"] < 0.01) & (fail["p_boot"] >= 0.000347)]
print(f"p_boot < 0.01 但未过 Bonferroni: {len(would_pass_001)}")

# 样本量 n 分布
print("\n候选样本量分布：")
print(df["n"].describe())

# 通过 L1（n≥15,indep≥5）但 fail 的样本量分布
fail_with_n = fail[fail["L1"].astype(bool)]
print(f"\nL1 过（n≥15） 但 fail 的样本量：")
print(fail_with_n["n"].describe())

# 如果样本量 * 5 · 会怎样？CI 收缩 sqrt(5)~2.24 · p_boot 大幅下降
# 粗估：如果 n → 5n · std_err → std_err/sqrt(5) → z_score → z*sqrt(5)
# p_boot ≈ 2 * Φ(-|z|)
import numpy as np
from scipy.stats import norm

def estimate_p_after_scale(p_two, scale=5.0):
    """假设放大 n · p_boot 近似 * sqrt(scale) z 值."""
    if p_two >= 1 or p_two <= 0:
        return p_two
    z = norm.isf(p_two / 2)  # 双侧 → 单侧 z
    z_new = z * np.sqrt(scale)
    return 2 * norm.sf(z_new)

fail["p_boot_x3"] = fail["p_boot"].apply(lambda p: estimate_p_after_scale(p, 3))
fail["p_boot_x5"] = fail["p_boot"].apply(lambda p: estimate_p_after_scale(p, 5))

# 只算 L3 单独 fail 的 · 假设 3x/5x 数据下会不会过 Bonferroni
only_l3_scaled = only_l3.copy()
only_l3_scaled["p_x3"] = only_l3_scaled["p_boot"].apply(lambda p: estimate_p_after_scale(p, 3))
only_l3_scaled["p_x5"] = only_l3_scaled["p_boot"].apply(lambda p: estimate_p_after_scale(p, 5))
would_x3 = (only_l3_scaled["p_x3"] < 0.000347).sum()
would_x5 = (only_l3_scaled["p_x5"] < 0.000347).sum()
print(f"\n仅 L3 fail 的 {len(only_l3)} 个 · 若数据量 x3 → 预计过 Bonferroni: {would_x3}")
print(f"仅 L3 fail 的 {len(only_l3)} 个 · 若数据量 x5 → 预计过 Bonferroni: {would_x5}")

print("\n仅 L3 fail 且 x5 后可过的（值得回补数据）：")
lucky = only_l3_scaled[only_l3_scaled["p_x5"] < 0.000347].sort_values("mean_bps", ascending=False)
print(lucky[["tier_id", "period", "n", "mean_bps", "p_boot", "p_x3", "p_x5"]].head(30).to_string(index=False))
