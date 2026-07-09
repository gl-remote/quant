#!/usr/bin/env python3
"""
Step 1 · 180 组收窄分组扫描
===========================
维度：skew(4) × trend(5) × atr(3) × holding(3) = 180 组
主排序指标：H4 真实成本下的配对差均值 (paired_diff_mean_H4_real_bps)
统计判据：CI95 lo > 0（cluster bootstrap B=200，clusters=contract×date）
泛化判据：symbol_retention ≥ 50%

流程：
1. 加载 dataset（36625 行）
2. 全 dataset 预计算：rank20, close_diff, close_diff_atr, is_trigger, side, cost_flat, cost_real
   对每个 (side, holding) 计算 pnl_flat, pnl_real（向量化，一次性）
3. 遍历 180 组：
   3.1 mask 子池
   3.2 每 contract × side：非触发样本按 close_diff_atr 与触发样本做最近邻配对（不放回）
   3.3 pair 级聚合 → cluster bootstrap 单次采样，同时算 6 个持有期×成本组合
4. 输出：CSV 宽表 (180 行) + Top-10 排名 + 边缘 heatmap 数据（3 张）

输出：
- project_data/ai_tmp/va_sym_180grid_scan_summary.csv
- project_data/ai_tmp/va_sym_180grid_top10.md
- project_data/ai_tmp/va_sym_180grid_heatmap_skew_trend.csv
- project_data/ai_tmp/va_sym_180grid_heatmap_skew_atr.csv
- project_data/ai_tmp/va_sym_180grid_heatmap_trend_atr.csv
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workspace"))

import numpy as np
import pandas as pd
from common.contract_specs import CONTRACT_SPECS

DATASET_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet")
OUT_DIR = Path("project_data/ai_tmp")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# 分组档位定义（对齐 workbench §5.3）
# ------------------------------------------------------------------
SKEW_BINS = [
    ("skew_wneg", 0.30, 0.40),
    ("skew_xneu", 0.40, 0.50),
    ("skew_wpos", 0.50, 0.60),
    ("skew_mpos", 0.60, 0.70),
]
TREND_BINS = [
    ("trend_lneg", 0.20, 0.35),
    ("trend_low",  0.35, 0.45),
    ("trend_core", 0.45, 0.55),
    ("trend_high", 0.55, 0.65),
    ("trend_lpos", 0.65, 0.80),
]
ATR_BINS = [
    ("atr_mid",   0.33, 0.50),
    ("atr_midhi", 0.50, 0.67),
    ("atr_hi",    0.67, 1.00),
]
HOLD_TAGS = ["H2", "H4", "H8"]

N_BOOTSTRAP = 200
SEED = 20260709
MIN_PAIRS = 10     # 单元格触发/配对 < 10 的标记 insufficient（细分后样本自然稀）
FLAT_COST_ATR = 0.05  # 双边扁平成本（0.05 ATR，粗略）


# ------------------------------------------------------------------
# 1. 预计算：全 dataset 特征 + 6 种 pnl 列
# ------------------------------------------------------------------
def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    print(f"[preprocess] 原始 {len(df)} rows, {df['contract'].nunique()} contracts")
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)

    # rank20 + close_diff
    df["rank20"] = df.groupby("contract")["close_t"].transform(
        lambda s: s.rolling(20, min_periods=10).rank(pct=True)
    )
    df["close_diff"] = df.groupby("contract")["close_t"].diff(1)
    df["close_diff_atr"] = (
        df["close_diff"] / df["close_t"].replace(0, np.nan) * 10000
        / df["daily_atr_10_bps"].replace(0, np.nan)
    )

    # 触发器：L / S / None
    cond_long = (
        df["rank20"].notna() & df["close_diff"].notna()
        & (df["rank20"] <= 0.20) & (df["close_diff"] > 0)
    )
    cond_short = (
        df["rank20"].notna() & df["close_diff"].notna()
        & (df["rank20"] >= 0.80) & (df["close_diff"] < 0)
    )
    df["trigger_side"] = np.where(cond_long, "L", np.where(cond_short, "S", None))
    df["is_trigger"] = df["trigger_side"].notna()
    print(f"[preprocess] 全局触发数：L={cond_long.sum()}, S={cond_short.sum()}")

    # 成本（向量化）
    df["cost_flat_bps"] = df["daily_atr_10_bps"] * FLAT_COST_ATR
    df["cost_real_bps"] = _fast_real_cost(df["contract"].values, df["close_t"].values)

    # 6 种 pnl 列：{H2, H4, H8} × {flat, real}
    #   ret_1h 数据集中没有，用 ret_4h/2 线性估算 H2；H4 = ret_4h_bps；H8 = ret_8h_bps
    #   ret_4h 在原 dataset 是"未 bps 化"的原始收益（诊断脚本显示 abs mean < 0.1）
    r4_raw = df["ret_4h"].values
    if np.nanmean(np.abs(r4_raw)) < 0.1:
        df["ret_4h_bps"] = r4_raw * 10000
    else:
        df["ret_4h_bps"] = r4_raw
    df["ret_2h_bps"] = df["ret_4h_bps"] / 2.0   # 线性估算 · 仅参考形状

    # 方向 sign：L 侧 +1，S 侧 -1
    sign = np.where(df["trigger_side"] == "L", 1.0,
                    np.where(df["trigger_side"] == "S", -1.0, np.nan))
    df["_sign"] = sign  # 触发事件的方向

    # 触发事件的 pnl（触发 = reaccept 组）
    for h, ret_col in zip(HOLD_TAGS, ["ret_2h_bps", "ret_4h_bps", "ret_8h_bps"]):
        df[f"pnl_trig_{h}_flat"] = sign * df[ret_col] - df["cost_flat_bps"]
        df[f"pnl_trig_{h}_real"] = sign * df[ret_col] - df["cost_real_bps"]

    return df


def _fast_real_cost(contracts: np.ndarray, prices: np.ndarray) -> np.ndarray:
    out = np.full(len(contracts), np.nan)
    uniq = pd.unique(pd.Series(contracts))
    for c in uniq:
        spec = CONTRACT_SPECS.get_symbol(c)
        if spec is None:
            continue
        m = contracts == c
        p = prices[m]
        size = spec.size
        if hasattr(spec, "total_commission_np"):
            comm = spec.total_commission_np(p, 1)
        else:
            comm = np.array([spec.total_commission(price=float(x), lots=1) for x in p])
        slip = spec.slippage(lots=1)
        total = 2 * (comm + slip)
        notional = p * size
        out[m] = total / notional * 10000
    return out


# ------------------------------------------------------------------
# 2. 单子组扫描：mask → 配对 → bootstrap
# ------------------------------------------------------------------
def scan_one_cell(
    df: pd.DataFrame,
    skew_lo: float, skew_hi: float,
    trend_lo: float, trend_hi: float,
    atr_lo: float, atr_hi: float,
    rng: np.random.RandomState,
) -> dict:
    mask = (
        df["signed_skew_rank_roll"].between(skew_lo, skew_hi, inclusive="left")
        & df["trend_rank_roll"].between(trend_lo, trend_hi, inclusive="left")
        & df["atr_rank_roll"].between(atr_lo, atr_hi, inclusive="right")
    )
    sub = df.loc[mask]
    if len(sub) == 0:
        return {"n_sub": 0, "n_trig": 0, "n_pairs": 0}

    trig = sub[sub["is_trigger"]]
    no_trig = sub[~sub["is_trigger"]]
    n_sub = len(sub)
    n_trig = len(trig)
    if n_trig < MIN_PAIRS or len(no_trig) < MIN_PAIRS:
        return {"n_sub": n_sub, "n_trig": n_trig, "n_pairs": 0}

    # 每 contract × side 分层 · 最近邻不放回配对
    # 注：no_trigger 池不再按 close_diff 方向过滤（对照组要求：同 contract + 未触发即可）
    # 因为细分后样本量本已稀缺，同方向约束会把大量单元格切到 0
    pairs_data = []
    for contract in trig["contract"].dropna().unique():
        nt_c_all = no_trig[no_trig["contract"] == contract]
        if len(nt_c_all) == 0:
            continue
        for side in ["L", "S"]:
            t_c = trig[(trig["contract"] == contract) & (trig["trigger_side"] == side)]
            if len(t_c) == 0:
                continue
            if len(nt_c_all) < len(t_c):
                continue
            # 最近邻不放回（贪心：按 close_diff_atr 距离排序）
            nt_avail = nt_c_all["close_diff_atr"].values
            nt_index = nt_c_all.index.values
            used = np.zeros(len(nt_avail), dtype=bool)
            sign = 1.0 if side == "L" else -1.0
            for _, row in t_c.iterrows():
                x = row["close_diff_atr"]
                if pd.isna(x):
                    continue
                d = np.abs(nt_avail - x)
                d[used] = np.inf
                pick = int(np.argmin(d))
                if not np.isfinite(d[pick]):
                    continue
                used[pick] = True
                nt_row = df.loc[nt_index[pick]]
                pairs_data.append({
                    "contract": contract,
                    "event_date": row["event_date"],
                    # trig 已有 pnl_trig_*
                    "trig_H2_flat": row["pnl_trig_H2_flat"],
                    "trig_H4_flat": row["pnl_trig_H4_flat"],
                    "trig_H8_flat": row["pnl_trig_H8_flat"],
                    "trig_H2_real": row["pnl_trig_H2_real"],
                    "trig_H4_real": row["pnl_trig_H4_real"],
                    "trig_H8_real": row["pnl_trig_H8_real"],
                    # no_trig 的方向对齐 pnl（sign 与 trig 一致）
                    "nt_H2_flat": sign * nt_row["ret_2h_bps"] - nt_row["cost_flat_bps"],
                    "nt_H4_flat": sign * nt_row["ret_4h_bps"] - nt_row["cost_flat_bps"],
                    "nt_H8_flat": sign * nt_row["ret_8h_bps"] - nt_row["cost_flat_bps"],
                    "nt_H2_real": sign * nt_row["ret_2h_bps"] - nt_row["cost_real_bps"],
                    "nt_H4_real": sign * nt_row["ret_4h_bps"] - nt_row["cost_real_bps"],
                    "nt_H8_real": sign * nt_row["ret_8h_bps"] - nt_row["cost_real_bps"],
                })
    if not pairs_data:
        return {"n_sub": n_sub, "n_trig": n_trig, "n_pairs": 0}

    pdf = pd.DataFrame(pairs_data)
    for h in HOLD_TAGS:
        for ct in ["flat", "real"]:
            pdf[f"diff_{h}_{ct}"] = pdf[f"trig_{h}_{ct}"] - pdf[f"nt_{h}_{ct}"]

    n_pairs = len(pdf)
    if n_pairs < MIN_PAIRS:
        return {"n_sub": n_sub, "n_trig": n_trig, "n_pairs": n_pairs}

    # cluster bootstrap（一次采样，多个 h/ct 共用）
    clusters = pdf.groupby(["contract", "event_date"]).indices  # dict key→idx array
    cluster_keys = list(clusters.keys())
    n_clusters = len(cluster_keys)

    diff_cols = [f"diff_{h}_{ct}" for h in HOLD_TAGS for ct in ["flat", "real"]]
    boot_matrix = np.empty((N_BOOTSTRAP, len(diff_cols)))
    boot_matrix.fill(np.nan)

    diff_arr = pdf[diff_cols].values  # (n_pairs, 6)
    for b in range(N_BOOTSTRAP):
        sampled_idx = rng.choice(n_clusters, size=n_clusters, replace=True)
        idx_list = []
        for k in sampled_idx:
            idx_list.extend(clusters[cluster_keys[k]])
        boot_matrix[b] = np.nanmean(diff_arr[idx_list], axis=0)

    obs = np.nanmean(diff_arr, axis=0)
    ci_lo = np.nanquantile(boot_matrix, 0.025, axis=0)
    ci_hi = np.nanquantile(boot_matrix, 0.975, axis=0)

    # 品种保留率（按 H4 real 为主，也各口径都算）
    per_contract = pdf.groupby("contract")
    result = {
        "n_sub": n_sub, "n_trig": n_trig, "n_pairs": n_pairs, "n_clusters": n_clusters,
    }
    for i, col in enumerate(diff_cols):
        result[f"{col}_mean"] = float(obs[i])
        result[f"{col}_ci_lo"] = float(ci_lo[i])
        result[f"{col}_ci_hi"] = float(ci_hi[i])
        per_c = per_contract[col].mean()
        result[f"{col}_sym_ret"] = float((per_c > 0).mean())
    # 常用衍生
    for h in HOLD_TAGS:
        for ct in ["flat", "real"]:
            k = f"diff_{h}_{ct}"
            result[f"hit_{h}_{ct}_trig"] = float((pdf[f"trig_{h}_{ct}"] > 0).mean())
            result[f"hit_{h}_{ct}_nt"] = float((pdf[f"nt_{h}_{ct}"] > 0).mean())
    return result


# ------------------------------------------------------------------
# 3. 主循环
# ------------------------------------------------------------------
def main():
    t0 = time.time()
    print("=" * 74)
    print("Step 1 · 180 组收窄分组扫描")
    print("=" * 74)

    df = pd.read_parquet(DATASET_PATH)
    df = preprocess(df)
    print(f"[preprocess] elapsed = {time.time()-t0:.1f}s")

    rng = np.random.RandomState(SEED)
    rows = []
    total = len(SKEW_BINS) * len(TREND_BINS) * len(ATR_BINS)
    i = 0
    for sk, sk_lo, sk_hi in SKEW_BINS:
        for tr, tr_lo, tr_hi in TREND_BINS:
            for at, at_lo, at_hi in ATR_BINS:
                i += 1
                t_cell = time.time()
                res = scan_one_cell(df, sk_lo, sk_hi, tr_lo, tr_hi, at_lo, at_hi, rng)
                res["skew"] = sk
                res["trend"] = tr
                res["atr"] = at
                res["skew_range"] = f"[{sk_lo:.2f},{sk_hi:.2f})"
                res["trend_range"] = f"[{tr_lo:.2f},{tr_hi:.2f})"
                res["atr_range"] = f"({at_lo:.2f},{at_hi:.2f}]"
                rows.append(res)
                tag = "SKIP" if res["n_pairs"] < MIN_PAIRS else "OK"
                if i % 10 == 0 or tag == "OK":
                    print(f"  [{i:>3d}/{total}] {sk}×{tr}×{at:12s} "
                          f"n_pairs={res['n_pairs']:>4d} · {tag} "
                          f"({time.time()-t_cell:.1f}s)")

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT_DIR / "va_sym_180grid_scan_summary.csv", index=False)
    print(f"\n[save] {OUT_DIR / 'va_sym_180grid_scan_summary.csv'}")

    # 只看有效子组
    valid = out_df[out_df["n_pairs"] >= MIN_PAIRS].copy()
    print(f"\n有效子组：{len(valid)}/{total}")

    if len(valid) == 0:
        print("⚠️  无有效子组，扫描结束")
        return

    # Top-10 by paired_diff_mean_H4_real
    valid = valid.sort_values("diff_H4_real_mean", ascending=False)
    keep_cols = [
        "skew", "trend", "atr",
        "n_sub", "n_trig", "n_pairs", "n_clusters",
        "diff_H4_real_mean", "diff_H4_real_ci_lo", "diff_H4_real_ci_hi",
        "diff_H4_real_sym_ret",
        "diff_H4_flat_mean", "diff_H4_flat_ci_lo", "diff_H4_flat_sym_ret",
        "diff_H8_real_mean", "diff_H8_real_ci_lo",
        "diff_H2_real_mean", "diff_H2_real_ci_lo",
        "hit_H4_real_trig", "hit_H4_real_nt",
    ]
    top10 = valid[keep_cols].head(10).round(2)

    md_lines = ["# 180 组扫描 · Top 10 (排序：diff_H4_real_mean)\n"]
    md_lines.append(top10.to_markdown(index=False))
    md_lines.append("\n\n## 统计概览\n")
    md_lines.append(f"- 有效子组：{len(valid)}/{total}")
    md_lines.append(f"- H4 real 配对差 CI 排 0（下限 > 0）：{(valid['diff_H4_real_ci_lo'] > 0).sum()} 组")
    md_lines.append(f"- H4 real 品种保留率 ≥ 50%：{(valid['diff_H4_real_sym_ret'] >= 0.50).sum()} 组")
    md_lines.append(f"- H4 real 均值 ≥ 10 bps：{(valid['diff_H4_real_mean'] >= 10).sum()} 组")
    md_lines.append(f"- **三条同时满足**（决策点分支 A 单元格候选）："
                    f"{((valid['diff_H4_real_ci_lo'] > 0) & (valid['diff_H4_real_sym_ret'] >= 0.50) & (valid['diff_H4_real_mean'] >= 10)).sum()} 组")
    (OUT_DIR / "va_sym_180grid_top10.md").write_text("\n".join(md_lines))
    print(f"[save] {OUT_DIR / 'va_sym_180grid_top10.md'}")

    # 边缘 heatmap 三张
    for a, b, name in [("skew", "trend", "skew_trend"),
                        ("skew", "atr", "skew_atr"),
                        ("trend", "atr", "trend_atr")]:
        hm = valid.pivot_table(index=a, columns=b,
                               values="diff_H4_real_mean", aggfunc="mean")
        hm.to_csv(OUT_DIR / f"va_sym_180grid_heatmap_{name}.csv")
        print(f"[save] heatmap_{name}.csv")

    print(f"\n[total] elapsed = {time.time()-t0:.1f}s")

    # 打印 Top 10 快速预览
    print("\n" + "=" * 74)
    print("Top 10 预览（diff_H4_real_mean 降序）")
    print("=" * 74)
    print(top10.to_string(index=False))

    # Step 2 决策点判定
    print("\n" + "=" * 74)
    print("Step 2 · 决策点判定")
    print("=" * 74)
    n_ci_pass = (valid["diff_H4_real_ci_lo"] > 0).sum()
    n_sym_pass = (valid["diff_H4_real_sym_ret"] >= 0.50).sum()
    n_mean_pass = (valid["diff_H4_real_mean"] >= 10).sum()
    n_all_pass = ((valid["diff_H4_real_ci_lo"] > 0)
                  & (valid["diff_H4_real_sym_ret"] >= 0.50)
                  & (valid["diff_H4_real_mean"] >= 10)).sum()
    print(f"  H4 real CI lo > 0 : {n_ci_pass:>3d} / {len(valid)}")
    print(f"  H4 real sym ≥ 50% : {n_sym_pass:>3d} / {len(valid)}")
    print(f"  H4 real mean ≥ 10 : {n_mean_pass:>3d} / {len(valid)}")
    print(f"  三条全过 (单元格): {n_all_pass:>3d} / {len(valid)}")
    if n_all_pass >= 3:
        print("\n  → 可能存在「平台」，人工检查 heatmap 判定分支 A 或 B")
    elif n_all_pass >= 1:
        print("\n  → 散点通过，倾向分支 B（辅助 gate），继续人工审 heatmap")
    else:
        print("\n  → 无子格三判据全过，倾向分支 B / C（不收窄，维持原推荐或搁置）")


if __name__ == "__main__":
    main()
