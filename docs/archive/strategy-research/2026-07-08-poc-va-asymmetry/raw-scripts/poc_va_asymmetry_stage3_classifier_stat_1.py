"""
文件级元信息：
- 创建背景：阶段 3 分类器严格性验证 · 脚本 1（A+B）
  A · 8 组合逐一 CI + Bonferroni 校正
  B · 稳定 vs 转换 mean 差异显著性（Welch t-test + 置换检验）
- 输出：project_data/logs/poc_va_asymmetry_stage3/classifier_stat_1_ci_diff.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import (  # noqa: E402
    prepare_dataset, cluster_bootstrap,
)
from poc_va_asymmetry_stage3_task3_regime_transition import (  # noqa: E402
    flag_regime_transition,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3"
)

FAMILY_SIZE = 8
BONFERRONI_P = 0.05 / FAMILY_SIZE  # 0.00625


def permutation_test(a, b, n_perm=5000, seed=42):
    """双样本置换检验 · H0: a 和 b 来自同一分布"""
    rng = np.random.default_rng(seed)
    a = np.asarray(a); b = np.asarray(b)
    real_diff = a.mean() - b.mean()
    combined = np.concatenate([a, b])
    n_a = len(a)
    count = 0
    for _ in range(n_perm):
        rng.shuffle(combined)
        d = combined[:n_a].mean() - combined[n_a:].mean()
        if abs(d) >= abs(real_diff):
            count += 1
    return real_diff, count / n_perm


def analyze_combo(df, name, mask, ret_col, need_split=True):
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"])
    if len(sub) < 20:
        return None
    stable = sub[~sub["transition_flag"]]
    trans = sub[sub["transition_flag"]]

    result = {"combo": name}

    # A · 逐组合 CI（稳定/转换 分别）
    for tag, seg in [("stable", stable), ("trans", trans), ("full", sub)]:
        if len(seg) < 20:
            result[f"{tag}_n"] = len(seg)
            for k in ["mean", "ci_lo", "ci_hi", "p", "hit", "pass_bonf"]:
                result[f"{tag}_{k}"] = np.nan
            continue
        r = cluster_bootstrap(seg, ret_col)
        hit = (seg[ret_col] > 0).mean()
        pass_bonf = "✅" if r["p_two"] < BONFERRONI_P and r["ci_lo"] > 0 else "❌"
        result[f"{tag}_n"] = r["n_events"]
        result[f"{tag}_mean"] = r["real_mean"]
        result[f"{tag}_ci_lo"] = r["ci_lo"]
        result[f"{tag}_ci_hi"] = r["ci_hi"]
        result[f"{tag}_p"] = r["p_two"]
        result[f"{tag}_hit"] = hit
        result[f"{tag}_pass_bonf"] = pass_bonf

    # B · 稳定 vs 转换 差异显著性
    if need_split and len(stable) >= 20 and len(trans) >= 20:
        # Welch's t-test
        t_stat, p_welch = stats.ttest_ind(
            stable[ret_col], trans[ret_col], equal_var=False)
        # 置换检验
        real_d, p_perm = permutation_test(stable[ret_col].values,
                                            trans[ret_col].values, n_perm=5000)
        result["diff_mean"] = real_d
        result["welch_t"] = t_stat
        result["welch_p"] = p_welch
        result["perm_p"] = p_perm
        result["diff_signif"] = "✅" if p_perm < 0.05 else "❌"
    else:
        for k in ["diff_mean", "welch_t", "welch_p", "perm_p", "diff_signif"]:
            result[k] = np.nan

    return result


def main():
    print("=" * 100)
    print("阶段 3 分类器严格性 · 脚本 1（A + B）")
    print(f"family size = {FAMILY_SIZE} · Bonferroni p < {BONFERRONI_P:.5f}")
    print("=" * 100)

    print("\n[准备数据] ...")
    df = prepare_dataset()
    df = flag_regime_transition(df)

    # 8 组合定义（含 5 主线的 稳定/转换 拆分 + 3 空头补充）
    signals = [
        # (name, direction, sk_low, sk_high, atr_low, atr_high, trend_low, trend_high, ret_col)
        # 多头首选 (skew<=0.10, atr<=0.70, trend>=0.75) - 8h
        ("多头首选", "long", 0.10, 0.70, 0.75, "ret_8h_bps"),
        # 多头宽松 (skew<=0.30, atr<=0.70, trend>=0.75) - 8h
        ("多头宽松", "long", 0.30, 0.70, 0.75, "ret_8h_bps"),
        # 空头首选 (skew>=0.70, atr>0.80, trend<=0.20) - 4h
        ("空头首选", "short", 0.70, 0.80, 0.20, "short_pnl_4h_bps"),
        # 空头宽松 (skew>=0.70, atr>0.50, trend<=0.20) - 4h
        ("空头宽松", "short", 0.70, 0.50, 0.20, "short_pnl_4h_bps"),
        # 空头收敛 (skew>=0.70, atr>0.67, trend<=0.20) - 4h · 洞察 Q 建议
        ("空头收敛", "short", 0.70, 0.67, 0.20, "short_pnl_4h_bps"),
    ]

    all_rows = []
    for name, direction, sk, at, tr, ret_col in signals:
        print(f"\n{'='*90}\n【{name}】\n{'='*90}")
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= at) &
                    (df["trend_rank_roll"] >= tr))
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > at) &
                    (df["trend_rank_roll"] <= tr))
        r = analyze_combo(df, name, mask, ret_col)
        if r is None:
            print("样本不足")
            continue
        all_rows.append(r)

        print(f"\n  {'期别':10s} {'n':>5s} {'mean':>8s} {'hit':>6s} "
              f"{'CI下':>8s} {'CI上':>8s} {'p':>8s} Bonf")
        for tag, lbl in [("full", "全事件"), ("stable", "稳定期"), ("trans", "转换期")]:
            n = r.get(f"{tag}_n", np.nan)
            if pd.isna(n) or n < 20:
                print(f"  {lbl:10s} {'-':>5s}  {'样本不足':<25s}")
                continue
            print(f"  {lbl:10s} {int(n):>5d} "
                  f"{r[f'{tag}_mean']:>+8.2f} {r[f'{tag}_hit']:>6.1%} "
                  f"{r[f'{tag}_ci_lo']:>+8.2f} {r[f'{tag}_ci_hi']:>+8.2f} "
                  f"{r[f'{tag}_p']:>8.4f}  {r[f'{tag}_pass_bonf']}")

        if not pd.isna(r.get("diff_mean")):
            print(f"\n  稳定 vs 转换 差异：{r['diff_mean']:+.2f} bps")
            print(f"    Welch t-test:  t={r['welch_t']:+.2f} · p={r['welch_p']:.4f}")
            print(f"    Permutation:   p={r['perm_p']:.4f}  {r['diff_signif']}")

    # 汇总
    print("\n" + "=" * 100)
    print("汇总 · Bonferroni 校正后严格显著（p<0.00625 · CI 排 0）")
    print("=" * 100)
    print(f"\n{'组合':20s} {'稳定期':>12s} {'转换期':>12s} {'全事件':>12s} {'稳定vs转换':>15s}")
    n_stable_pass = 0
    n_trans_pass = 0
    for r in all_rows:
        stable_ok = r.get("stable_pass_bonf", "-")
        trans_ok = r.get("trans_pass_bonf", "-")
        full_ok = r.get("full_pass_bonf", "-")
        diff_ok = r.get("diff_signif", "-")
        print(f"{r['combo']:20s} {str(stable_ok):>12s} {str(trans_ok):>12s} "
              f"{str(full_ok):>12s} {str(diff_ok):>15s}")
        if stable_ok == "✅": n_stable_pass += 1
        if trans_ok == "✅": n_trans_pass += 1

    print(f"\n稳定期严格显著数: {n_stable_pass}/{len(all_rows)}")
    print(f"转换期严格显著数: {n_trans_pass}/{len(all_rows)}")

    pd.DataFrame(all_rows).to_csv(LOG_DIR / "classifier_stat_1_ci_diff.csv", index=False)
    print(f"\n输出：{LOG_DIR / 'classifier_stat_1_ci_diff.csv'}")


if __name__ == "__main__":
    main()
