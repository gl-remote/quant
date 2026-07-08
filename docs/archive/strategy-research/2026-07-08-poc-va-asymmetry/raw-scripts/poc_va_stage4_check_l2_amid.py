"""临时脚本 · 查 L2_Amid_Tup 三个 period 的表现"""
import pandas as pd

desc = pd.read_csv(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/stage4_step2_144tier_descriptive.csv"
)
ver = pd.read_csv(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/stage4_step3_144tier_verification.csv"
)

print("=== Step 2 描述性（L2_Amid_Tup 三 period）===")
sub_d = desc[desc["tier_id"] == "L2_Amid_Tup"]
print(sub_d[["tier_id", "period", "n_events", "n_indep_days", "mean_bps", "hit_rate", "top_symbol", "eligible_step3"]].to_string(index=False))

print("\n=== Step 3 严格验证（L2_Amid_Tup 三 period）===")
sub_v = ver[ver["tier_id"] == "L2_Amid_Tup"]
cols = ["tier_id", "period", "n", "n_days", "mean_bps", "ci_lo_95", "ci_hi_95", "p_boot", "p_cf", "L1", "L2", "L3", "L4", "L7", "grade"]
print(sub_v[cols].to_string(index=False))

# 对比同 skew段2 里通过的 tier
print("\n=== 对比 · 同 skew段2 通过格（L2_Ahigh_Tup · L2_Alow_Tflat）===")
for tid in ["L2_Ahigh_Tup", "L2_Alow_Tflat"]:
    sub = ver[ver["tier_id"] == tid]
    print(f"\n{tid}:")
    print(sub[cols].to_string(index=False))
