#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：用户提出新假设——旧 VA reaccept 整体被冻结是因为全局 pool，
  但在"VA 对称（skew neutral）+ 中高波动 + 趋势平稳"的三维子环境中可能仍有效。
- 用途：Gatekeeper 广度优先最简验证：
    层 1：制度土壤检查（三维子池 vs 全局池的分布 & 反转性质）
    层 2：触发器增量（reaccept_proxy vs no_trigger 配对差 + cluster bootstrap）
  先扁平成本快速定性，再切真实成本。触发器用事件级代理近似（无 5m bar 边界信息）。
- 注意事项：
    1. 触发器代理非常粗糙（仅基于 1h close 的相对排名），仅用于 gatekeeper 定性；
       若通过需要用严格 5m bar 检测器重跑。
    2. 缺失 transition_flag，trend_stable 用 trend_rank 中间 60% 近似（严格版需重算 dataset）。
    3. Cluster bootstrap 单位 = (contract, date)（对齐 KF-22）。
    4. 本脚本是临时 gatekeeper 脚本，完成后归档随 experiment 包迁入 archive；
       若通过则提取公共函数入 workspace/common/。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workspace"))

import numpy as np
import pandas as pd
from scipy import stats
from common.contract_specs import CONTRACT_SPECS

# ------------------------------------------------------------------
# 0. 路径 & 常数
# ------------------------------------------------------------------
DATASET_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet")
OUT_DIR = Path("project_data/ai_tmp")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_SUMMARY = OUT_DIR / "va_sym_reaccept_gatekeeper_summary.csv"
OUT_DETAIL = OUT_DIR / "va_sym_reaccept_gatekeeper_events.csv"

# 三维阈值（对齐分类器 v4.0）
SKEW_NEUTRAL: Tuple[float, float] = (0.30, 0.70)
ATR_MIDHIGH: Tuple[float, float] = (0.33, 1.00)  # 开区间左，开/闭与 tier 一致
TREND_STABLE: Tuple[float, float] = (0.20, 0.80)  # 中间 60% 作为趋势平稳近似

# 持有期（对齐旧策略 S1 timeout 的等效 1h bars = 8h，8 bars）
HOLD_BARS = 8

# 扁平成本（debug 快速版：单边 0.025 ATR → 双边 0.05 ATR，对齐 old S1）
FLAT_COST_ATR_BPS = 25.0  # bps，用 daily_atr_10_bps 换算近似

# Bootstrap（Gatekeeper 定性用 500 次，节约时间）
N_BOOTSTRAP = 500
SEED = 20260709

# ------------------------------------------------------------------
# 1. 读取 & 三维筛选
# ------------------------------------------------------------------
def load_and_filter() -> pd.DataFrame:
    df = pd.read_parquet(DATASET_PATH).copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df["date"] = pd.to_datetime(df["date"]).dt.date

    mask = (
        df["signed_skew_rank_roll"].between(*SKEW_NEUTRAL, inclusive="both")
        & df["atr_rank_roll"].between(*ATR_MIDHIGH, inclusive="right")
        & df["trend_rank_roll"].between(*TREND_STABLE, inclusive="both")
    )
    df["pool"] = np.where(mask, "symmetric_subset", "global")
    return df


# ------------------------------------------------------------------
# 2. 成本计算（两口径）
# ------------------------------------------------------------------
def add_cost_columns(df: pd.DataFrame) -> pd.DataFrame:
    def realistic_cost_bps(row: pd.Series) -> float:
        contract = row["contract"]
        price = row["close_t"]
        spec = CONTRACT_SPECS.get_symbol(contract)
        if spec is None:
            return np.nan
        comm = spec.total_commission(price=price, lots=1)
        slip = spec.slippage(lots=1)
        total_cost = 2 * (comm + slip)  # 双边
        notional = price * spec.size
        return float(total_cost / notional * 10000)

    def flat_cost_bps(row: pd.Series) -> float:
        # 近似：daily_atr_10_bps * 0.05（旧 S1 cost=0.05 ATR）
        return float(row["daily_atr_10_bps"] * 0.05)

    df["cost_real_bps"] = df.apply(realistic_cost_bps, axis=1)
    df["cost_flat_bps"] = df.apply(flat_cost_bps, axis=1)
    return df


# ------------------------------------------------------------------
# 3. 层 1：制度土壤检查
# ------------------------------------------------------------------
def soil_check(df: pd.DataFrame) -> dict:
    def summarize(sub: pd.DataFrame, tag: str) -> dict:
        ret = sub["ret_8h_bps"]
        atr = sub["daily_atr_10_bps"]
        # 反转性质：前 1 小时方向与后 8 小时方向的负命中率（均值回归土壤）
        # 用 close_t 相对前一小时 close 的变化（注意 ret_4h / ret_8h 本身是 forward，
        # 所以 backward 用 shift 1 event 内差异；这里简单用 ret_8h 的符号自相关
        # （在同合约内 shift(1)）：符号正相关 = 趋势；负相关 = 均值回归
        sub = sub.sort_values(["contract", "event_time"]).copy()
        shift_ret = sub.groupby("contract")["ret_8h_bps"].shift(1)
        same_sign = np.sign(sub["ret_8h_bps"].fillna(0)) == np.sign(shift_ret.fillna(0))
        valid = sub["ret_8h_bps"].notna() & shift_ret.notna()
        same_rate = float(same_sign[valid].mean()) if valid.sum() > 0 else np.nan

        return {
            "pool": tag,
            "n": len(sub),
            "contracts": sub["contract"].nunique(),
            "dates": sub["event_date"].nunique(),
            "mean_8h_bps": float(ret.mean()),
            "std_8h_bps": float(ret.std()),
            "median_8h_bps": float(ret.median()),
            "hit8h_rate": float((ret > 0).mean()),
            "mean_atr_bps": float(atr.mean()),
            "mean_abs_ret_over_atr": float((ret.abs() / atr.replace(0, np.nan)).mean()),
            "sign_autocorr_same_rate": same_rate,
            "sign_autocorr": float(
                sub.groupby("contract")["ret_8h_bps"].apply(
                    lambda s: s.autocorr(lag=1) if s.notna().sum() > 10 else np.nan
                ).mean()
            ),
        }

    gbl = df[df["pool"] == "global"]
    sub = df[df["pool"] == "symmetric_subset"]
    return {"soil_global": summarize(gbl, "global"), "soil_subset": summarize(sub, "symmetric_subset")}


# ------------------------------------------------------------------
# 4. 层 2：触发器代理 & no_trigger 配对
# ------------------------------------------------------------------
def build_trigger_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    简化触发器代理（仅 gatekeeper 定性）：
    对每个 contract 按时间排序，定义最近 20 event 内的 close 排名 rank20：
      long reaccept_proxy：rank20 <= 0.20（近期低点）且 close_t > close_{t-1}（反弹）
      short reaccept_proxy：rank20 >= 0.80（近期高点）且 close_t < close_{t-1}（回落）
    方向：long 做多 ret_8h_bps（正向），short 做空（取 -ret_8h_bps 同多空一致口径）
    配对：从 no_trigger 池子里匹配同方向、同合约、同 distance（close_t - close_t-1 的分位）的
          相同数量样本（最近邻匹配 1:1，不放回）
    返回事件级 DataFrame，带 trigger/side/pair_id/pnl
    """
    df = df[df["pool"] == "symmetric_subset"].copy()
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)

    # 排名 20
    df["rank20"] = (
        df.groupby("contract")["close_t"]
        .transform(lambda s: s.rolling(20, min_periods=10).rank(pct=True))
    )
    df["close_diff"] = df.groupby("contract")["close_t"].diff(1)
    df["close_diff_atr"] = df["close_diff"] / df["close_t"].replace(0, np.nan) * 10000 / df["daily_atr_10_bps"].replace(0, np.nan)

    def trigger_mask(sub: pd.DataFrame) -> str | None:
        r20, diff = sub["rank20"], sub["close_diff"]
        if pd.isna(r20) or pd.isna(diff):
            return None
        if r20 <= 0.20 and diff > 0:
            return "long"
        if r20 >= 0.80 and diff < 0:
            return "short"
        return None

    df["trigger_side"] = df.apply(trigger_mask, axis=1)
    df["is_reaccept_proxy"] = df["trigger_side"].notna()

    # 方向收益：做多就是 ret_8h_bps，做空是 -ret_8h_bps
    def dir_pnl(row: pd.Series, cost_col: str) -> float:
        r = row["ret_8h_bps"]
        side = row["trigger_side"]
        if side is None:
            return np.nan
        sign = 1.0 if side == "long" else -1.0
        return float(sign * r - row[cost_col])

    for cost_tag in ["flat", "real"]:
        df[f"pnl_{cost_tag}"] = df.apply(
            lambda r: dir_pnl(r, f"cost_{cost_tag}_bps"), axis=1
        )

    # 1:1 配对：从 pool 内非 trigger 事件中，同 contract × 同 trigger_side 方向 ×
    #   同 distance（close_diff_atr 分位桶）最近邻匹配，不放回
    matched_rows: list[pd.Series] = []
    rng = np.random.RandomState(SEED)

    for contract in df["contract"].dropna().unique():
        cdf = df[df["contract"] == contract].reset_index(drop=True)
        for side in ["long", "short"]:
            reaccept = cdf[cdf["is_reaccept_proxy"] & cdf["trigger_side"].eq(side)].copy()
            ntriggers = len(reaccept)
            if ntriggers == 0:
                continue

            # no_trigger 池：所有未触发 + 方向需匹配（long pool：diff >= 0 或任意？这里同方向匹配：
            # long pool 要求 close_diff_atr 和 trigger 同一桶；short 同）
            no_trigger = cdf[~cdf["is_reaccept_proxy"] & cdf["trigger_side"].isna()].copy()

            # 分位桶：5 档
            all_dist = pd.concat([reaccept["close_diff_atr"], no_trigger["close_diff_atr"]]).dropna()
            if len(all_dist) < 10:
                continue
            try:
                bins = np.quantile(all_dist, np.linspace(0, 1, 6))
                bins = np.unique(bins)
                reaccept["dist_bin"] = pd.cut(reaccept["close_diff_atr"], bins=bins, labels=False, include_lowest=True)
                no_trigger = no_trigger.copy()
                no_trigger["dist_bin"] = pd.cut(no_trigger["close_diff_atr"], bins=bins, labels=False, include_lowest=True)
            except Exception:
                continue

            used_no_idx: set = set()
            for _, re in reaccept.iterrows():
                b = re["dist_bin"]
                if pd.isna(b):
                    continue
                candidates = no_trigger[
                    no_trigger["dist_bin"].eq(b) & ~no_trigger.index.isin(used_no_idx)
                ]
                if len(candidates) == 0:
                    # 放宽到相邻桶
                    candidates = no_trigger[
                        no_trigger["dist_bin"].isin([b - 1, b, b + 1])
                        & ~no_trigger.index.isin(used_no_idx)
                    ]
                if len(candidates) == 0:
                    continue
                # 最近邻（按 close_diff_atr 绝对差）
                diff = (candidates["close_diff_atr"] - re["close_diff_atr"]).abs()
                # 随机 tie-break
                minv = diff.min()
                match_idx = diff[diff <= minv * 1.0001].index.to_list()
                pick = candidates.loc[rng.choice(match_idx)]
                used_no_idx.add(pick.name)

                pair_id = f"{contract}_{side}_{len(matched_rows)}"
                rec_row = re.copy()
                rec_row["role"] = "reaccept_proxy"
                rec_row["pair_id"] = pair_id
                rec_row["pair_side"] = side
                no_row = pick.copy()
                no_row["role"] = "no_trigger"
                no_row["pair_id"] = pair_id
                no_row["pair_side"] = side
                # no_trigger 方向：做同样方向（long/short 与 reaccept 同）
                for cost_tag in ["flat", "real"]:
                    sign = 1.0 if side == "long" else -1.0
                    no_row[f"pnl_{cost_tag}"] = float(sign * no_row["ret_8h_bps"] - no_row[f"cost_{cost_tag}_bps"])
                matched_rows.append(rec_row)
                matched_rows.append(no_row)

    if not matched_rows:
        return pd.DataFrame()

    pair_df = pd.DataFrame(matched_rows).reset_index(drop=True)
    return pair_df


# ------------------------------------------------------------------
# 5. Cluster bootstrap（按 (contract, date) 聚类）
# ------------------------------------------------------------------
def cluster_bootstrap_paired_diff(
    pair_df: pd.DataFrame, cost_tag: str, n_boot: int = N_BOOTSTRAP, seed: int = SEED
) -> dict:
    if pair_df.empty:
        return {"n_pairs": 0}
    pairs = pair_df[["pair_id", "role", f"pnl_{cost_tag}", "contract", "event_date"]].copy()
    # 展开到 pair 级
    piv = pairs.pivot(index="pair_id", columns="role", values=f"pnl_{cost_tag}").dropna()
    meta = pairs.groupby("pair_id")[["contract", "event_date"]].first()
    merged = piv.join(meta, how="left").reset_index()
    merged["diff"] = merged["reaccept_proxy"] - merged["no_trigger"]

    rng = np.random.RandomState(seed)
    clusters = merged.groupby(["contract", "event_date"], sort=False).size().reset_index(name="n")
    cluster_keys = clusters[["contract", "event_date"]].values.tolist()
    n_clusters = len(cluster_keys)
    if n_clusters == 0:
        return {"n_pairs": len(merged)}
    boot_means = []
    boot_re_means = []
    boot_nt_means = []
    for _ in range(n_boot):
        sampled = rng.choice(n_clusters, size=n_clusters, replace=True)
        idx_sel: list[int] = []
        for k in sampled:
            c, d = cluster_keys[k]
            sel = merged[(merged["contract"] == c) & (merged["event_date"] == d)].index
            idx_sel.extend(sel.tolist())
        if len(idx_sel) == 0:
            continue
        bdf = merged.loc[idx_sel]
        boot_means.append(float(bdf["diff"].mean()))
        boot_re_means.append(float(bdf["reaccept_proxy"].mean()))
        boot_nt_means.append(float(bdf["no_trigger"].mean()))

    diff_mean = float(merged["diff"].mean())
    re_mean = float(merged["reaccept_proxy"].mean())
    nt_mean = float(merged["no_trigger"].mean())
    boot_arr = np.array(boot_means) if boot_means else np.array([np.nan])
    ci_lo, ci_hi = float(np.quantile(boot_arr, 0.025)), float(np.quantile(boot_arr, 0.975))
    # 单侧 p(diff <= 0)
    pval = float((boot_arr <= 0).mean())
    # 品种保留率：每 contract 的 diff.mean() > 0 比例
    per_contract = merged.groupby("contract")["diff"].mean()
    symbol_retention = float((per_contract > 0).mean()) if len(per_contract) > 0 else np.nan

    return {
        "n_pairs": len(merged),
        "n_clusters": n_clusters,
        f"reaccept_mean_{cost_tag}_bps": re_mean,
        f"no_trigger_mean_{cost_tag}_bps": nt_mean,
        f"paired_diff_mean_{cost_tag}_bps": diff_mean,
        f"paired_diff_CI95_lo_{cost_tag}": ci_lo,
        f"paired_diff_CI95_hi_{cost_tag}": ci_hi,
        f"paired_diff_pval_le0_{cost_tag}": pval,
        f"symbol_retention_{cost_tag}": symbol_retention,
        f"per_contract_n{cost_tag}": int(per_contract.notna().sum()),
        f"reaccept_hit_rate_{cost_tag}": float((merged["reaccept_proxy"] > 0).mean()),
        f"no_trigger_hit_rate_{cost_tag}": float((merged["no_trigger"] > 0).mean()),
    }


# ------------------------------------------------------------------
# 6. 汇总输出
# ------------------------------------------------------------------
def main() -> None:
    print("=" * 72)
    print("Gatekeeper：VA 对称 + 中高波动 + 趋势平稳 · Reaccept 子假设验证")
    print("=" * 72)

    df = load_and_filter()
    print(f"\n[0] 加载数据：total events = {len(df)}, "
          f"symmetric_subset = {(df['pool'] == 'symmetric_subset').sum()}")

    df = add_cost_columns(df)
    soil = soil_check(df)
    print(f"\n[1] 制度土壤检查\n--- global ---")
    gdf = pd.DataFrame([soil["soil_global"]]).T
    gdf.columns = ["value"]
    print(gdf.to_string())
    print("--- symmetric_subset ---")
    sdf = pd.DataFrame([soil["soil_subset"]]).T
    sdf.columns = ["value"]
    print(sdf.to_string())

    # 层 2：触发器配对
    pair_df = build_trigger_pairs(df)
    flat_res = cluster_bootstrap_paired_diff(pair_df, "flat")
    real_res = cluster_bootstrap_paired_diff(pair_df, "real")

    print(f"\n[2] 触发器增量（reaccept_proxy vs no_trigger · 层 2）")
    allres = {**flat_res, **real_res}
    rdf = pd.DataFrame([allres]).T
    rdf.columns = ["value"]
    pd.set_option("display.max_rows", 200)
    print(rdf.to_string())

    # 保存
    summary_rows = []
    for section, payload in [("soil", soil["soil_global"]), ("soil_subset", soil["soil_subset"])]:
        row = {"section": section}
        row.update(payload)
        summary_rows.append(row)
    row = {"section": "paired_result"}
    row.update(allres)
    summary_rows.append(row)
    pd.DataFrame(summary_rows).to_csv(OUT_SUMMARY, index=False)
    if not pair_df.empty:
        cols_out = [
            "pair_id", "pair_side", "role", "contract", "event_time", "event_date",
            "close_t", "ret_8h_bps",
            "signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll",
            "pnl_flat", "pnl_real",
            "cost_flat_bps", "cost_real_bps",
            "rank20", "close_diff_atr",
        ]
        cols_out = [c for c in cols_out if c in pair_df.columns]
        pair_df[cols_out].to_csv(OUT_DETAIL, index=False)

    print(f"\n[save] summary -> {OUT_SUMMARY}")
    if not pair_df.empty:
        print(f"[save] detail  -> {OUT_DETAIL}")

    # 简易判决
    print("\n" + "=" * 72)
    print("=== Gatekeeper 快速判决（严格版判据参考 experiment-plan） ===")
    print("=" * 72)
    n = flat_res.get("n_pairs", 0)
    print(f"配对数 n_pairs = {n}")
    if n > 0:
        ok_flat = all_res.get("paired_diff_CI95_lo_flat", -1) > 0
        ok_real = all_res.get("paired_diff_CI95_lo_real", -1) > 0
        sr_flat = all_res.get("symbol_retention_flat", 0) >= 0.60
        sr_real = all_res.get("symbol_retention_real", 0) >= 0.60
        no_trigger_positive = soil["soil_subset"]["mean_8h_bps"]  # 检查子池本身无偏
        print(f"  土壤 mean_8h（子池无偏要求接近 0，±50bps 内可接受）："
              f"{soil['soil_subset']['mean_8h_bps']:+.2f} bps")
        print(f"  扁平成本：CI95 排 0？{ok_flat} (lo={all_res.get('paired_diff_CI95_lo_flat', np.nan):+.2f}) · "
              f"品保 ≥60%？{sr_flat} ({all_res.get('symbol_retention_flat', np.nan)*100:.1f}%)")
        print(f"  真实成本：CI95 排 0？{ok_real} (lo={all_res.get('paired_diff_CI95_lo_real', np.nan):+.2f}) · "
              f"品保 ≥60%？{sr_real} ({all_res.get('symbol_retention_real', np.nan)*100:.1f}%)")
        print(f"  合并通过？{'✅ PASS（扁平+真实均过）' if (ok_flat and ok_real and sr_flat and sr_real) else '⚠️ 未通过，需决策'}")
    else:
        print("  ⚠️ 未形成任何触发器配对，需调整代理规则或用 5m bar 级严格检测器重跑。")


if __name__ == "__main__":
    main()
