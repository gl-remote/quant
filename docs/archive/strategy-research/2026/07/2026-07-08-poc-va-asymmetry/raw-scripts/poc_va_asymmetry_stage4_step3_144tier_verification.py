"""
文件级元信息：
- 创建背景：experiment-plan v9.1 §4.4 · 阶段 4 · Step 3 · 144 tier 严格性验证
- 用途：对 Step 2 描述性扫描通过 (n≥15 ∧ indep≥5 ∧ mean>0) 门槛的候选 tier，
  跑 7 层严格性验证 · 输出 A/A-/未过评级 · 冻结阶段 4 分类器 v4.0 白名单。
- 注意事项：
  * v9.1 修订：多重比较校正从 Bonferroni family=144 (α=0.000347) 改为
    FDR (Benjamini-Hochberg) α=0.05 · 更符合"结构性切片"的相关检验族
  * 保留 Bonferroni family=18 (α=0.0028) 作为 sanity check · 不硬拒
  * 严格 date-cluster bootstrap 5000（KF-22）· 反事实 5000 次
  * 单方向 mean>0 判据（多头 ret_8h_bps · 空头 short_pnl_4h_bps · 都是"越正越赚"）
  * 复用 stage4_step2_seven_layer.py 里的 cluster_bootstrap_by_date / counterfactual_test /
    symbol_retention / time_stability / per_trade_ir
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage4_data_full import prepare_dataset_full  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402
from poc_va_asymmetry_stage4_step2_144tier_descriptive import (  # noqa: E402
    build_tiers, make_tier_mask,
)
from poc_va_asymmetry_stage4_step2_seven_layer import (  # noqa: E402
    cluster_bootstrap_by_date, counterfactual_test,
    symbol_retention, time_stability, per_trade_ir,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ================================
# 阶段 4 严格性参数（v9.1 §4.4）
# ================================
FDR_ALPHA = 0.05                       # BH 假发现率控制
BONF_SC_FAMILY = 18                    # sanity check · 方向×ATR×trend
BONF_SC_ALPHA = 0.05 / BONF_SC_FAMILY  # ≈ 0.00278
BOOT_N = 5000
CF_N = 5000
CF_ALPHA = 0.001

SYMBOL_RETAIN_THRESHOLD = 0.80         # 观察阈值
IR_THRESHOLD = 0.30                    # 观察阈值
TIME_STABILITY_THRESHOLD = 0.50        # A / A- 区分线

DESCRIPTIVE_CSV = LOG_DIR / "stage4_step2_144tier_descriptive.csv"


def load_step2_candidates() -> pd.DataFrame:
    """加载 Step 2 结果 · 筛出 eligible ∧ mean>0 的候选."""
    if not DESCRIPTIVE_CSV.exists():
        raise FileNotFoundError(
            f"未找到 Step 2 输出 · 请先跑 stage4_step2_144tier_descriptive.py"
            f"\n预期路径: {DESCRIPTIVE_CSV}"
        )
    desc = pd.read_csv(DESCRIPTIVE_CSV)
    cand = desc[desc["eligible_step3"] & (desc["mean_bps"] > 0)].copy()
    return cand


def verify_tier_period(df: pd.DataFrame, tier: dict, period: str) -> dict:
    """对一个 (tier, period) 组合跑 bootstrap + CF · 只输出原始统计 · 不判决 L3.

    L3 (FDR) 需要拿到全部候选的 p_boot 后统一 BH 校正 · 在 apply_fdr 里做。
    """
    mask = make_tier_mask(df, tier)
    ret_col = tier["ret_col"]
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date

    if period == "stable":
        seg = sub[~sub["transition_flag"]]
    elif period == "trans":
        seg = sub[sub["transition_flag"]]
    else:
        seg = sub

    n = len(seg)
    n_days = seg["event_date"].nunique() if n > 0 else 0

    all_ret = df[ret_col].dropna()

    base = {
        "tier_id": tier["tier_id"],
        "direction": tier["direction"],
        "period": period,
    }

    if n < 15 or n_days < 5:
        base.update({
            "n": n, "n_days": n_days, "skipped": True,
        })
        return base

    boot = cluster_bootstrap_by_date(
        seg[ret_col], seg["contract"], seg["event_date"], n_boot=BOOT_N,
    )
    cf = counterfactual_test(seg[ret_col].values, all_ret.values, n=CF_N)
    sr = symbol_retention(seg, ret_col)
    ir = per_trade_ir(seg[ret_col].values)
    ts = time_stability(seg, ret_col)

    # L1 · L2 · L4 · L7 立即可判 · L3 (FDR) 需要全体校正后再判
    L1 = (n >= 15) and (n_days >= 5)
    L2 = (boot["ci_lo_95"] > 0) or (boot["ci_hi_95"] < 0)
    L4 = cf["p_cf"] < CF_ALPHA
    L5 = (not np.isnan(sr)) and (sr >= SYMBOL_RETAIN_THRESHOLD)
    L6 = (not np.isnan(ir)) and (abs(ir) >= IR_THRESHOLD)
    L7 = (not np.isnan(ts)) and (ts <= TIME_STABILITY_THRESHOLD)
    # Sanity check: Bonferroni family=18
    L3b = boot["p_two"] < BONF_SC_ALPHA

    base.update({
        "n": n, "n_days": n_days,
        "mean_bps": boot["mean"],
        "ci_lo_95": boot["ci_lo_95"],
        "ci_hi_95": boot["ci_hi_95"],
        "p_boot": boot["p_two"],
        "cf_real": cf["real_mean"],
        "cf_bkg": cf["cf_mean"],
        "p_cf": cf["p_cf"],
        "symbol_retain": sr,
        "ir_single": ir,
        "time_stab": ts,
        "L1": L1, "L2": L2, "L4": L4, "L5": L5, "L6": L6, "L7": L7,
        "L3b_bonf_sc": L3b,
        "skipped": False,
    })
    return base


def apply_fdr_and_grade(records: list[dict]) -> pd.DataFrame:
    """对全部非 skipped 记录 · 按 p_boot 升序 · Benjamini-Hochberg FDR 校正.

    BH 阈值：找 max{i : p(i) ≤ (i / N) * α} · 令 threshold_p = p(i*).
    p_boot ≤ threshold_p 的记录 L3 通过。
    """
    df = pd.DataFrame(records)
    active = df[~df["skipped"].fillna(False)].copy()

    # 只对硬门槛"方向对的"候选做 FDR（Step 2 已确保 mean_bps > 0）
    # 但保守起见 · 只让 L1 ∧ L2 已过的进 FDR（p<0.5 的强候选）
    # 实际实现：全部一起 BH · 因为 Step 2 已经筛出 mean>0 的候选
    active = active.sort_values("p_boot").reset_index(drop=True)
    n_total = len(active)
    active["rank"] = np.arange(1, n_total + 1)
    active["bh_threshold"] = active["rank"] / n_total * FDR_ALPHA
    # 找最大 rank i 满足 p(i) ≤ bh_threshold(i)
    valid = active[active["p_boot"] <= active["bh_threshold"]]
    if len(valid) == 0:
        threshold_p = 0.0
    else:
        threshold_p = valid["p_boot"].max()
    active["L3"] = active["p_boot"] <= threshold_p
    active["fdr_threshold_p"] = threshold_p

    # 硬门槛通过 = L1 ∧ L2 ∧ L3 (FDR) ∧ L4
    active["hard_pass"] = (
        active["L1"] & active["L2"] & active["L3"] & active["L4"]
    )
    # 评级
    def grade(row):
        if not row["hard_pass"]:
            return "fail"
        return "A" if row["L7"] else "A-"

    active["grade"] = active.apply(grade, axis=1)

    # skipped 保留
    skipped = df[df["skipped"].fillna(False)].copy()
    if len(skipped) > 0:
        skipped["grade"] = "skip"
        skipped["L3"] = False
        skipped["hard_pass"] = False
        skipped["fdr_threshold_p"] = threshold_p

    out = pd.concat([active, skipped], ignore_index=True)
    return out


def main():
    print("=" * 110)
    print("阶段 4 · Step 3 · 144 tier 严格性验证（experiment-plan v9.1 §4.4 · FDR 校正）")
    print("=" * 110)
    print(f"\n参数：FDR (BH) α={FDR_ALPHA:.2f}"
          f" · Bonferroni SC family={BONF_SC_FAMILY} α={BONF_SC_ALPHA:.4f}"
          f" · Bootstrap={BOOT_N} · CF={CF_N}"
          f"\n      IR 观察阈值≥{IR_THRESHOLD} · 品保观察阈值≥{SYMBOL_RETAIN_THRESHOLD:.0%}"
          f" · 时稳线={TIME_STABILITY_THRESHOLD:.0%}")

    # ================================
    # 1. 加载候选
    # ================================
    cand = load_step2_candidates()
    print(f"\nStep 2 候选（eligible ∧ mean>0）: {len(cand)} 个 (tier,period) 组合")
    print(f"  多头: {(cand['direction']=='long').sum()} · 空头: {(cand['direction']=='short').sum()}")

    # 建 tier 字典（tier_id → tier 定义）
    all_tiers = {t["tier_id"]: t for t in build_tiers()}

    # ================================
    # 2. 数据加载
    # ================================
    df = prepare_dataset_full()
    df = flag_regime_transition(df)
    print(f"\n数据规模：{len(df)} events · {df['contract'].nunique()} 品种")

    # ================================
    # 3. 遍历候选跑 bootstrap + CF（不做 L3 判决）
    # ================================
    print("\n" + "─" * 110)
    print(f"Step 3a · 遍历 {len(cand)} 个候选 · 每个跑 date-cluster bootstrap + 反事实")
    print("─" * 110)

    results = []
    total = len(cand)
    for i, row in enumerate(cand.itertuples(index=False), 1):
        tier = all_tiers[row.tier_id]
        if tier["direction"] != row.direction:
            print(f"⚠️  方向不一致 {row.tier_id} · 跳过")
            continue
        rec = verify_tier_period(df, tier, row.period)
        results.append(rec)
        if i % 20 == 0 or i == total:
            print(f"  [{i:>3}/{total}] done")

    # ================================
    # 4. BH FDR 校正 · 计算最终评级
    # ================================
    print("\n" + "─" * 110)
    print("Step 3b · Benjamini-Hochberg FDR 校正 + 硬门槛判决")
    print("─" * 110)

    out_df = apply_fdr_and_grade(results)
    out_path = LOG_DIR / "stage4_step3_144tier_verification.csv"
    out_df.to_csv(out_path, index=False)

    fdr_thr = out_df["fdr_threshold_p"].dropna().iloc[0] if len(out_df) > 0 else 0.0
    print(f"\nBH 阈值 p_boot ≤ {fdr_thr:.5f}")
    n_pass_l3 = out_df["L3"].sum() if "L3" in out_df.columns else 0
    print(f"L3 (FDR) 通过：{n_pass_l3} / {(~out_df['skipped'].fillna(False)).sum()}")

    # ================================
    # 5. 主表输出
    # ================================
    print("\n" + "=" * 110)
    print("Step 3c · 全部结果（按 grade 排 · 再按 mean 降序）")
    print("=" * 110)
    display = out_df[~out_df["skipped"].fillna(False)].copy()
    display = display.sort_values(
        ["grade", "mean_bps"], ascending=[True, False]
    )

    print(f"\n{'tier·period':>26s} {'dir':>5s} "
          f"{'n':>5s} {'nd':>4s} {'mean':>7s} "
          f"{'CI 95%':>18s} {'p_boot':>9s} {'p_cf':>8s} "
          f"{'品保':>5s} {'IR':>6s} {'时稳':>5s} "
          f"{'L1|2|3|4|7':>11s} {'BSC':>4s} {'评级':>5s}")
    print("-" * 155)
    layer_keys = ["L1", "L2", "L3", "L4", "L7"]
    for _, r in display.iterrows():
        key = f"{r['tier_id']}·{r['period']}"
        ci = f"[{r['ci_lo_95']:>+6.1f},{r['ci_hi_95']:>+6.1f}]"
        sr_str = f"{r['symbol_retain']:.0%}" if not np.isnan(r['symbol_retain']) else "-"
        ir_str = f"{r['ir_single']:+.3f}" if not np.isnan(r['ir_single']) else "-"
        ts_str = f"{r['time_stab']:.2f}" if not np.isnan(r['time_stab']) else "-"
        L_str = "".join(["+" if r[k] else "-" for k in layer_keys])
        bsc = "✓" if r.get("L3b_bonf_sc", False) else "×"
        mark = "🟢" if r["grade"] == "A" else "🟡" if r["grade"] == "A-" else "🔴"
        print(f"{key:>26s} {r['direction']:>5s} "
              f"{int(r['n']):>5d} {int(r['n_days']):>4d} "
              f"{r['mean_bps']:>+7.1f} {ci:>18s} "
              f"{r['p_boot']:>9.5f} {r['p_cf']:>8.4f} "
              f"{sr_str:>5s} {ir_str:>6s} {ts_str:>5s} "
              f"{L_str:>11s} {bsc:>4s} {mark}{r['grade']:>4s}")

    # ================================
    # 6. 白名单汇总
    # ================================
    print("\n" + "=" * 110)
    print("Step 3d · 阶段 4 白名单（A / A- 级）")
    print("=" * 110)

    a_grade = display[display["grade"] == "A"]
    am_grade = display[display["grade"] == "A-"]
    fail = display[display["grade"] == "fail"]

    print(f"\n🟢 A 级（L1-L4 硬门槛全过 ∧ L7 时稳）· {len(a_grade)} 个：")
    for _, r in a_grade.iterrows():
        bsc = " · BSC✓" if r.get("L3b_bonf_sc", False) else ""
        print(f"  {r['tier_id']}·{r['period']:6s} [{r['direction']}] "
              f"n={int(r['n']):>4d} mean {r['mean_bps']:+.1f} bps "
              f"p_boot {r['p_boot']:.5f} IR {r['ir_single']:+.3f} "
              f"品保 {r['symbol_retain']:.0%}{bsc}")

    print(f"\n🟡 A- 级（L1-L4 全过 但 L7 时稳警示）· {len(am_grade)} 个：")
    for _, r in am_grade.iterrows():
        bsc = " · BSC✓" if r.get("L3b_bonf_sc", False) else ""
        print(f"  {r['tier_id']}·{r['period']:6s} [{r['direction']}] "
              f"n={int(r['n']):>4d} mean {r['mean_bps']:+.1f} bps "
              f"p_boot {r['p_boot']:.5f} 时稳 {r['time_stab']:.2f}{bsc}")

    print(f"\n🔴 未过（硬门槛 fail）· {len(fail)} 个（按 mean 排前 15）：")
    fail_disp = fail.sort_values("mean_bps", ascending=False).head(15)
    for _, r in fail_disp.iterrows():
        missing = [L for L in ["L1", "L2", "L3", "L4"] if not r[L]]
        print(f"  {r['tier_id']}·{r['period']:6s} n={int(r['n']):>4d} "
              f"mean {r['mean_bps']:+.1f} 未过 {','.join(missing)} p_boot={r['p_boot']:.4f}")

    # ================================
    # 7. 阶段 4 最终判决
    # ================================
    print("\n" + "=" * 110)
    print("Step 3e · 阶段 4 最终判决（experiment-plan v9.1 §4.6）")
    print("=" * 110)

    long_a = a_grade[a_grade["direction"] == "long"]
    short_a = a_grade[a_grade["direction"] == "short"]
    long_am = am_grade[am_grade["direction"] == "long"]
    short_am = am_grade[am_grade["direction"] == "short"]
    total_ok = len(a_grade) + len(am_grade)

    print(f"\n多头 A 级 {len(long_a)} · A- 级 {len(long_am)}")
    print(f"空头 A 级 {len(short_a)} · A- 级 {len(short_am)}")
    print(f"合计 A/A- 级 {total_ok} 个 tier·period")

    # Sanity check：Bonferroni family=18 通过数
    bsc_pass = display[display.get("L3b_bonf_sc", False) & display["hard_pass"]]
    print(f"\nSanity check（Bonferroni family=18 · α={BONF_SC_ALPHA:.4f}）通过: {len(bsc_pass)} 个")
    if len(bsc_pass) > 0:
        print("  → 即使用最严格的 Bonferroni 也能通过的高置信度 tier:")
        for _, r in bsc_pass.sort_values("mean_bps", ascending=False).iterrows():
            print(f"    {r['tier_id']}·{r['period']:6s} p_boot={r['p_boot']:.5f}")

    if len(a_grade) >= 4 and len(long_a) >= 1 and len(short_a) >= 1:
        verdict = "✅ 通过 · 至少 4 个 A 级 · 多空双向都有 · 可冻结分类器 v4.0"
    elif total_ok >= 3 and (len(long_a) + len(long_am) >= 1) and (len(short_a) + len(short_am) >= 1):
        verdict = "⚠️  边缘通过 · 至少 3 个 A/A- · 主题降级为「稀疏可用」"
    else:
        verdict = "❌ 失败 · 分类器无严格证据 · 保留 v3.0 · 三维深化归为「探索性发现」"

    print(f"\n判决：{verdict}")

    print(f"\n输出：{out_path}")


if __name__ == "__main__":
    main()
