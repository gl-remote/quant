"""一次性：按 strategy-math-spec §1.2 的六个 tier 区间，对 stage4 timeline 数据重判，
确认 6 个 tier 全部启用后各自能否分到数据（重点：刚从"淘汰"改回的 L_seg2_low_flat）。
"""
import pandas as pd
import numpy as np

PATH = "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet"
df = pd.read_parquet(PATH)

skew = "signed_skew_rank_roll"
atr = "atr_rank_roll"
trend = "trend_rank_roll"
for c in (skew, atr, trend):
    assert c in df.columns, f"缺列 {c}"

# §1.2 六 tier 区间（闭开用 (]/[) 表示；表内写法 (a,b] = a<·<=b, [a,b] = a<=·<=b）
# 每项为 (偏度段, 波动段, 趋势段)
def I(lo, hi, loinc, hiinc):
    return (lo, hi, loinc, hiinc)

tiers = {
    "L_seg3_lowmid_up": (I(0.09, 0.30, False, True), I(0.00, 0.67, True, True),  I(0.75, 1.00, True, True)),
    "L_seg12_high_up":  (I(0.00, 0.19, True,  True),  I(0.67, 1.00, False, True), I(0.75, 1.00, True, True)),
    "L_seg2_low_flat":  (I(0.09, 0.19, False, True),  I(0.00, 0.33, True,  True),  I(0.20, 0.75, False, False)),
    "S_seg12_high_dn":  (I(0.81, 1.00, True,  True),  I(0.67, 1.00, False, True), I(0.00, 0.20, True, True)),
    "S_seg34_high_dn":  (I(0.60, 0.81, True,  True),  I(0.67, 1.00, False, True), I(0.00, 0.20, True, True)),
    "S_seg2_mid_dn":    (I(0.81, 0.91, False, True),  I(0.33, 0.67, False, True), I(0.00, 0.20, True, True)),
}

def hit(x, iv):
    lo, hi, loinc, hiinc = iv
    if loinc:
        if x < lo: return False
    else:
        if x <= lo: return False
    if hiinc:
        if x > hi: return False
    else:
        if x >= hi: return False
    return True

df = df.dropna(subset=[skew, atr, trend]).copy()
n = len(df)
assign = []
for _, r in df.iterrows():
    hit_tiers = [name for name, (s, a, t) in tiers.items()
                 if hit(r[skew], s) and hit(r[atr], a) and hit(r[trend], t)]
    assign.append(hit_tiers[0] if len(hit_tiers) == 1 else ("AMBIG" if len(hit_tiers) > 1 else "NONE"))
df["_tier"] = assign

print("=" * 70)
print(f"总有效行: {n}, 合约数: {df['contract'].nunique()}")
print("=" * 70)
print(f"{'tier':<18}{'行数':>10}{'占比%':>10}")
for name in tiers:
    cnt = (df["_tier"] == name).sum()
    print(f"{name:<18}{cnt:>10}{100*cnt/n:>9.2f}%")
amb = (df["_tier"] == "AMBIG").sum()
non = (df["_tier"] == "NONE").sum()
print("-" * 70)
print(f"{'AMBIG(多命中)':<18}{amb:>10}{100*amb/n:>9.2f}%")
print(f"{'NONE(无命中)':<18}{non:>10}{100*non/n:>9.2f}%")
print("=" * 70)

# 重点：L_seg2_low_flat 启用后是否有覆盖
l2 = (df["_tier"] == "L_seg2_low_flat").sum()
print(f"\n>>> L_seg2_low_flat 启用后覆盖行数 = {l2}  ({100*l2/n:.2f}%)")
if l2 == 0:
    print("    ⚠ 该 tier 在 stage4 数据上 0 命中 —— 启用它不会改变任何信号，"
          "之前'淘汰'可能是因为它本就空。需进一步查是区间过窄还是数据不支撑。")
else:
    print("    ✓ 该 tier 现在能分到数据，启用有效。")
print("=" * 70)
