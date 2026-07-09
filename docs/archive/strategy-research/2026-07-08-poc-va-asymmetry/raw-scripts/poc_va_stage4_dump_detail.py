"""
文件级元信息：
- 创建背景：需要拿到每个 tier·period 的详细数据（mean/n/p_boot/评级/BSC）用于文档
- 用途：一次性辅助脚本 · 打印每个非空格的详细内容
- 注意事项：临时脚本
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

CSV = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4/stage4_step3_144tier_verification.csv"
)

df = pd.read_csv(CSV)
df = df[~df["skipped"].fillna(False)]
df["seg"] = df["tier_id"].apply(lambda t: t.split("_")[0])
df["atr"] = df["tier_id"].apply(lambda t: t.split("_")[1])
df["trend"] = df["tier_id"].apply(lambda t: t.split("_")[2])
df["passed"] = df["grade"].isin(["A", "A-"])

pass_df = df[df["passed"]].sort_values(["period", "trend", "seg", "atr"])
print("全部 A/A- tier·period 明细：")
for _, r in pass_df.iterrows():
    bsc = "✓" if r.get("L3b_bonf_sc", False) else "×"
    dir_char = "多" if r["seg"].startswith("L") else "空"
    print(
        f"  {r['tier_id']}·{r['period']:6s} [{dir_char}] "
        f"n={int(r['n']):>4d} mean={r['mean_bps']:+6.1f} "
        f"p_boot={r['p_boot']:.5f} 品保={r['symbol_retain']:.0%} "
        f"IR={r['ir_single']:+.3f} 时稳={r['time_stab']:.2f} "
        f"grade={r['grade']:>2s} BSC={bsc}"
    )
