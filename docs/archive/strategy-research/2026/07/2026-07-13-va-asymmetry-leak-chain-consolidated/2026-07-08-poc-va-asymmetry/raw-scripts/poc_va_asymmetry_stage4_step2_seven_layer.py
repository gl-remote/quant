"""
文件级元信息：
- 创建背景：阶段 4 · Step 2 · 对 15 个互斥类别做完整 7 层严格性验证
- 用途：判决每类是否通过 A/B 级 · 输出最终白名单
- 注意事项：Bonferroni family=15 · 阈值 p<0.0033 · 严格 date-cluster bootstrap
  · 反事实 5000 shuffle · 时间前后半分
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage4_data_full import prepare_dataset_full  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402
from poc_va_asymmetry_stage4_step1_exclusive_classes import (  # noqa: E402
    CLASSES, make_class_mask,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4"
)
LOG_DIR.mkdir(parents=True, exist_ok=True)

BOOT_N = 5000
FAMILY_SIZE = 15
BONF_ALPHA = 0.05 / FAMILY_SIZE  # 0.0033
CF_N = 5000
CF_ALPHA = 0.001

IR_THRESHOLD = 0.30
SYMBOL_RETAIN_THRESHOLD = 0.80
TIME_STABILITY_THRESHOLD = 0.50


def cluster_bootstrap_by_date(returns, contract, date, n_boot=BOOT_N, seed=42):
    """严格 date-cluster bootstrap."""
    df = pd.DataFrame({
        "ret": np.asarray(returns),
        "key": list(zip(np.asarray(contract), np.asarray(date))),
    })
    groups = df.groupby("key")
    keys = list(groups.groups.keys())
    n_c = len(keys)
    cluster_rets = [df.loc[groups.groups[k], "ret"].values for k in keys]

    rng = np.random.default_rng(seed)
    boot_means = np.zeros(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n_c, size=n_c)
        picked = [cluster_rets[j] for j in idx]
        boot_means[i] = np.concatenate(picked).mean()

    real = df["ret"].mean()
    return {
        "n": len(df),
        "n_clusters": n_c,
        "mean": real,
        "ci_lo_95": np.quantile(boot_means, 0.025),
        "ci_hi_95": np.quantile(boot_means, 0.975),
        "p_two": 2 * min((boot_means <= 0).mean(), (boot_means >= 0).mean()),
        "se": boot_means.std(),
    }


def counterfactual_test(sub_ret, all_ret, n=CF_N, seed=42):
    """反事实：随机抽同样大小的样本 · 与真实 mean 对比."""
    rng = np.random.default_rng(seed)
    real_mean = sub_ret.mean()
    all_arr = np.asarray(all_ret)
    n_sub = len(sub_ret)
    boot = np.zeros(n)
    for i in range(n):
        idx = rng.integers(0, len(all_arr), size=n_sub)
        boot[i] = all_arr[idx].mean()
    if real_mean > 0:
        p = (boot >= real_mean).mean()
    else:
        p = (boot <= real_mean).mean()
    return {"real_mean": real_mean, "cf_mean": boot.mean(), "p_cf": p}


def symbol_retention(seg, ret_col, min_n=3):
    """品种保留率：mean > 0 的品种占比（要求单品种 n≥min_n）."""
    grp = seg.groupby("contract")[ret_col]
    per_contract = grp.mean()
    counts = grp.size()
    valid = per_contract[counts >= min_n]
    if len(valid) == 0:
        return np.nan
    return (valid > 0).mean()


def time_stability(seg, ret_col):
    """时间前后半分 mean 差 / 全 mean · 越小越稳定."""
    seg2 = seg.sort_values("event_time")
    n = len(seg2)
    if n < 20:
        return np.nan
    mid = n // 2
    first = seg2.iloc[:mid][ret_col].mean()
    second = seg2.iloc[mid:][ret_col].mean()
    full = seg2[ret_col].mean()
    if abs(full) < 1e-6:
        return np.nan
    return abs(first - second) / abs(full)


def per_trade_ir(ret):
    """单笔 IR = mean / std."""
    r = np.asarray(ret)
    s = r.std()
    if s < 1e-6:
        return np.nan
    return r.mean() / s


def verify_class(df, name, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, direction, ret_col):
    """对一个互斥类 · 分 stable / trans · 跑 7 层严格验证."""
    mask = make_class_mask(df, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, direction)
    all_ret = df[ret_col].dropna()
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date

    rows = []
    for tag, seg in [
        ("full", sub),
        ("stable", sub[~sub["transition_flag"]]),
        ("trans", sub[sub["transition_flag"]]),
    ]:
        n = len(seg)
        n_days = seg["event_date"].nunique() if n > 0 else 0

        if n < 15 or n_days < 5:
            rows.append({
                "class": name, "period": tag,
                "n": n, "n_days": n_days,
                "skipped": True,
            })
            continue

        # Layer 2 · date-cluster CI
        boot = cluster_bootstrap_by_date(seg[ret_col], seg["contract"], seg["event_date"])
        # Layer 4 · 反事实
        cf = counterfactual_test(seg[ret_col].values, all_ret.values)
        # Layer 5 · 品种保留
        sr = symbol_retention(seg, ret_col)
        # Layer 6 · 单笔 IR
        ir = per_trade_ir(seg[ret_col].values)
        # Layer 7 · 时间稳定
        ts = time_stability(seg, ret_col)

        # 判决
        L1 = n >= 15 and n_days >= 5
        L2 = boot["ci_lo_95"] > 0 or boot["ci_hi_95"] < 0
        L3 = boot["p_two"] < BONF_ALPHA
        L4 = cf["p_cf"] < CF_ALPHA
        L5 = not np.isnan(sr) and sr >= SYMBOL_RETAIN_THRESHOLD
        L6 = not np.isnan(ir) and abs(ir) >= IR_THRESHOLD
        L7 = not np.isnan(ts) and ts <= TIME_STABILITY_THRESHOLD

        pass_cnt = sum([L1, L2, L3, L4, L5, L6, L7])

        # 分档
        if pass_cnt == 7:
            grade = "A"
        elif pass_cnt == 6:
            grade = "B"
        elif pass_cnt == 5 and n < 30:
            grade = "B"
        else:
            grade = "None"

        rows.append({
            "class": name, "period": tag,
            "n": n, "n_days": n_days,
            "mean_bps": boot["mean"],
            "ci_lo_95": boot["ci_lo_95"],
            "ci_hi_95": boot["ci_hi_95"],
            "p_boot": boot["p_two"],
            "cf_real": cf["real_mean"],
            "cf_bkg": cf["cf_mean"],
            "p_cf": cf["p_cf"],
            "symbol_retain": sr,
            "ir": ir,
            "time_stab": ts,
            "L1": L1, "L2": L2, "L3": L3, "L4": L4, "L5": L5, "L6": L6, "L7": L7,
            "pass_count": pass_cnt,
            "grade": grade,
            "skipped": False,
        })
    return rows


def main():
    print("=" * 110)
    print("阶段 4 · Step 2 · 15 互斥类别 · 7 层严格验证")
    print("=" * 110)
    print(f"\n参数：Bonferroni family={FAMILY_SIZE} · α = {BONF_ALPHA:.4f}"
          f" · CF n={CF_N} α<{CF_ALPHA} · IR≥{IR_THRESHOLD}"
          f" · 品种保留≥{SYMBOL_RETAIN_THRESHOLD:.0%} · 时间稳定≤{TIME_STABILITY_THRESHOLD:.0%}")

    df = prepare_dataset_full()
    df = flag_regime_transition(df)
    print(f"\n数据规模：{len(df)} events · {df['contract'].nunique()} 品种")

    all_rows = []
    for name, direction, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, ret_col in CLASSES:
        print(f"\n验证 {name} ...")
        rows = verify_class(df, name, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi, direction, ret_col)
        all_rows.extend(rows)

    out_df = pd.DataFrame(all_rows)
    out_df.to_csv(LOG_DIR / "stage4_step2_seven_layer_verification.csv", index=False)

    # ================================
    # 主表输出
    # ================================
    print("\n" + "=" * 110)
    print("7 层严格验证结果")
    print("=" * 110)

    display = out_df[~out_df["skipped"]].copy()
    print(f"\n{'类·期':22s} {'n':>4s} {'nday':>4s} {'mean':>7s} "
          f"{'CI 95%':>18s} {'p_boot':>8s} {'p_cf':>8s} "
          f"{'品保':>5s} {'IR':>6s} {'时稳':>5s} "
          f"{'L1':>2s} {'L2':>2s} {'L3':>2s} {'L4':>2s} {'L5':>2s} {'L6':>2s} {'L7':>2s} "
          f"{'评级':>4s}")
    print("-" * 175)
    for _, r in display.iterrows():
        key = f"{r['class']}·{r['period']}"
        ci = f"[{r['ci_lo_95']:>+6.1f},{r['ci_hi_95']:>+6.1f}]"
        sr_str = f"{r['symbol_retain']:.0%}" if not np.isnan(r['symbol_retain']) else "-"
        ir_str = f"{r['ir']:+.3f}" if not np.isnan(r['ir']) else "-"
        ts_str = f"{r['time_stab']:.2f}" if not np.isnan(r['time_stab']) else "-"
        checks = "".join([
            "✅" if r[f"L{i}"] else "❌" for i in range(1, 8)
        ])
        L_flags = " ".join(["✅" if r[f"L{i}"] else "❌" for i in range(1, 8)])
        grade_mark = "🟢" if r["grade"] == "A" else "🟡" if r["grade"] == "B" else "🔴"
        print(f"{key:22s} {int(r['n']):>4d} {int(r['n_days']):>4d} "
              f"{r['mean_bps']:>+7.1f} {ci:>18s} "
              f"{r['p_boot']:>8.4f} {r['p_cf']:>8.4f} "
              f"{sr_str:>5s} {ir_str:>6s} {ts_str:>5s} "
              f"{L_flags} "
              f"{grade_mark}{r['grade']:>2s}")

    # ================================
    # 白名单汇总
    # ================================
    print("\n" + "=" * 110)
    print("阶段 4 白名单")
    print("=" * 110)

    a_grade = display[display["grade"] == "A"]
    b_grade = display[display["grade"] == "B"]
    fail = display[display["grade"] == "None"]

    print(f"\n🟢 A 级（7/7 通过）· {len(a_grade)} 个：")
    for _, r in a_grade.iterrows():
        print(f"  {r['class']}·{r['period']:7s} · n={int(r['n']):>4d} "
              f"· mean {r['mean_bps']:+.1f} · IR {r['ir']:.3f} · 品保 {r['symbol_retain']:.0%}")

    print(f"\n🟡 B 级（6/7 或 5/7+n<30）· {len(b_grade)} 个：")
    for _, r in b_grade.iterrows():
        fails = [f"L{i}" for i in range(1, 8) if not r[f"L{i}"]]
        print(f"  {r['class']}·{r['period']:7s} · n={int(r['n']):>4d} "
              f"· mean {r['mean_bps']:+.1f} · 未过 {','.join(fails)}")

    print(f"\n🔴 未分类（≤5/7）· {len(fail)} 个：")
    for _, r in fail.iterrows():
        fails = [f"L{i}" for i in range(1, 8) if not r[f"L{i}"]]
        print(f"  {r['class']}·{r['period']:7s} · n={int(r['n']):>4d} "
              f"· mean {r['mean_bps']:+.1f} · 未过 {','.join(fails)}")

    # 判决
    print("\n" + "=" * 110)
    print("阶段 4 判决")
    print("=" * 110)

    long_a = a_grade[a_grade["class"].isin(["LP_only", "LL_only"])]
    short_a = a_grade[a_grade["class"].isin(["SP_only", "SC_only", "SL_only"])]

    print(f"\n多头 A 级：{len(long_a)} 个 · 空头 A 级：{len(short_a)} 个 · 合计 A 级 {len(a_grade)} 个")

    if len(a_grade) >= 3 and len(long_a) >= 1 and len(short_a) >= 1:
        print("\n✅ 阶段 4 通过 · 至少 3 类通过 A 级 · 多空双向都有 · 可以冻结分类器 v3.0")
    elif len(a_grade) >= 1:
        print(f"\n⚠️  阶段 4 边缘 · A 级 {len(a_grade)} 个 · 分类器可用但稀疏")
    else:
        print("\n❌ 阶段 4 失败 · 无 A 级通过 · 主题需考虑冻结")

    print(f"\n输出：{LOG_DIR / 'stage4_step2_seven_layer_verification.csv'}")


if __name__ == "__main__":
    main()
