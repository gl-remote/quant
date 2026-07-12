#!/usr/bin/env python3
"""
va-composite · P0.1 · 管线修正：重建正确口径（drop_duplicates 滚动）的 A/C 双轨秩坐标生成器

位置: scripts/ai_tmp/va_p01_build_ac_tracks.py
主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 timeline（classifier_v31_timeline.parquet）—— 仅复用其**逐日恒定原始量**
      A3_skew / daily_atr_10_bps / trend_ret_10d（已验证每日 max nunique=1，本身正确），
      重新计算其秩坐标，修正旧管线"按逐事件行滚 ROLLING_EVENTS=100"的已知缺陷
      （spec §1.3.0：混淆日内事件与日频信号，同日重复行引入 ≤0.05 秩 jitter，等价仅~17 交易日）。

正确口径（spec §1.3.0）:
  - 先 drop_duplicates(event_date) 得每合约每日 1 个观测；
  - 逐合约（within-contract）按 N 日滚动：
      A（rank）  : r_t = #{x_{t-N+1..t} <= x_t} / N                       ∈ (0,1]
      C（pct）   : percentile = [#(x < x_t) + 0.5·#(x == x_t)] / N        ∈ (0,1]
    （A 与 C 仅在并列(tie)处差异；连续分布下 A≈C，P3 据此确认等价）
  - 窗口 N：skew_rank_win=60 / atr_rank_win=20 / trend_win=20（spec §0.1 默认）

输出:
  project_data/ai_tmp/p0_calib/timeline_calA.parquet  —— 正确口径 A 轨（= 修正版 B0 基线）
  project_data/ai_tmp/p0_calib/timeline_calC.parquet  —— 正确口径 C 轨
  project_data/ai_tmp/p0_calib/timeline_calAC.parquet —— 合并（含双轨 + 双 tier，供巡检）
  project_data/ai_tmp/p0_calib/diag.md                —— 诊断（A/C 相关性、tier 一致率、分布）

注: 旧冻结 timeline 的 tier 是旧口径产物，本脚本完全重算；新 calA 即"正确口径 B0"，
    下游 P1/P5/P6 应改读 calA 重跑（旧口径数字不再有效）。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
from strategies.classifiers.poc_va import POCVAClassifier  # noqa: E402

SRC = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
OUT = Path("project_data/ai_tmp/p0_calib")
OUT.mkdir(parents=True, exist_ok=True)

# spec §0.1 默认 skew_rank_win=60，但本数据集为事件采样（每合约中位仅 ~38 日频观测），
# N=60 时仅 14/143(10%) 合约够长、策略几近瘫痪。故研究期采用数据可行窗口：
# skew=20（≈旧管线等效 ~17 不重复交易日、且修正重复行缺陷、98% 覆盖）。
# 可用环境变量覆盖（如 SKEW_WIN=30 uv run ...）。N=60 为生产目标，需更完整日频数据。
SKEW_WIN = int(__import__("os").environ.get("SKEW_WIN", "20"))
ATR_WIN = int(__import__("os").environ.get("ATR_WIN", "20"))
TREND_WIN = int(__import__("os").environ.get("TREND_WIN", "20"))

# v3.1 tier id -> v4.0 名称（与 va_composite_p1_cap.py 一致）
TIER_TO_V40 = {
    "UP2_atrLow_up_stable": "L_seg3_lowmid_up", "UP3_atrMid_up_stable": "L_seg3_lowmid_up",
    "UP1_atrHigh_up_trans": "L_seg12_high_up",
    "DN1_atrHigh_down_stable": "S_seg12_high_dn", "DN1_atrHigh_down_trans": "S_seg12_high_dn",
    "DN2_atrHigh_down_stable": "S_seg12_high_dn", "DN2_atrHigh_down_trans": "S_seg12_high_dn",
    "DN3_atrHigh_down_stable": "S_seg34_high_dn", "DN3_atrHigh_down_trans": "S_seg34_high_dn",
    "DN4_atrHigh_down_stable": "S_seg34_high_dn", "DN4_atrHigh_down_trans": "S_seg34_high_dn",
    "DN2_atrMid_down_stable": "S_seg2_mid_dn", "DN2_atrMid_down_trans": "S_seg2_mid_dn",
}


# ---------------------------------------------------------------------------
# 滚动归一化（A / C）
# ---------------------------------------------------------------------------
def roll_a(s: pd.Series, N: int) -> pd.Series:
    """A · 滚动排名: r_t = #{w <= x_t} / N，w = 窗口内 N 个观测。"""
    return s.rolling(N, min_periods=N).apply(lambda w: (w <= w[-1]).mean(), raw=True)


def roll_c(s: pd.Series, N: int) -> pd.Series:
    """C · 滚动百分位（平均秩）: [#(x < x_t) + 0.5·#(x == x_t)] / N。"""
    def _f(w):
        x = w[-1]
        lt = (w < x).sum()
        eq = (w == x).sum()
        return (lt + 0.5 * eq) / len(w)
    return s.rolling(N, min_periods=N).apply(_f, raw=True)


def build_daily_coords(daily: pd.DataFrame) -> pd.DataFrame:
    """输入每合约每日 1 行的 daily 帧，输出 6 列秩坐标（A/C × skew/atr/trend）。"""
    out = pd.DataFrame(index=daily.index)
    out["sk_A"] = roll_a(daily["A3_skew"], SKEW_WIN)
    out["atr_A"] = roll_a(daily["daily_atr_10_bps"], ATR_WIN)
    out["tr_A"] = roll_a(daily["trend_ret_10d"], TREND_WIN)
    out["sk_C"] = roll_c(daily["A3_skew"], SKEW_WIN)
    out["atr_C"] = roll_c(daily["daily_atr_10_bps"], ATR_WIN)
    out["tr_C"] = roll_c(daily["trend_ret_10d"], TREND_WIN)
    return out


def classify_track(merged: pd.DataFrame, track: str) -> pd.DataFrame:
    """用指定轨（A/C）的秩坐标重算 v3.1 tier id 并映射到 v4.0。"""
    tmp = merged[["contract", "event_time", "transition_flag",
                  f"sk_{track}", f"atr_{track}", f"tr_{track}"]].copy()
    tmp = tmp.rename(columns={
        f"sk_{track}": "signed_skew_rank_roll",
        f"atr_{track}": "atr_rank_roll",
        f"tr_{track}": "trend_rank_roll",
    })
    tmp = tmp.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
    if tmp.empty:
        return pd.Series(dtype=object, index=merged.index, name="tier_v40")
    res = POCVAClassifier().evaluate_dataset(tmp)
    res = res.dropna(subset=["tier"])
    res["tier_v40"] = res["tier"].map(TIER_TO_V40)
    # evaluate_dataset 保留 tmp 索引（=merged 非 null 子集），直接回填
    full = pd.DataFrame(index=merged.index, columns=["tier", "tier_v40"], dtype=object)
    full.loc[res.index, "tier"] = res["tier"].values
    full.loc[res.index, "tier_v40"] = res["tier_v40"].values
    return full


def main() -> None:
    print("=" * 70)
    print("va-composite · P0.1 · 重建正确口径 A/C 双轨")
    print("=" * 70)

    df = pd.read_parquet(SRC)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    print(f"[0] 源 timeline: {len(df)} 事件行 | {df['contract'].nunique()} 合约 | "
          f"{df['event_date'].min()} ~ {df['event_date'].max()}")

    # 逐日去重；原始量日内恒定，取首值
    feat = ["A3_skew", "daily_atr_10_bps", "trend_ret_10d", "transition_flag"]
    for c in feat:
        nu = df.groupby(["contract", "event_date"])[c].nunique().max()
        assert nu == 1, f"列 {c} 日内非恒定 (max nunique={nu}) —— 假设不成立"
    daily = (df.groupby(["contract", "event_date"], as_index=False)[feat].first()
              .sort_values(["contract", "event_date"]).reset_index(drop=True))
    print(f"[1] 逐日去重后: {len(daily)} 日频行（每合约每日 1 观测）")

    # 每合约日频长度 vs 各候选 skew 窗口覆盖（数据可行性诊断）
    cnt = daily.groupby("contract").size()
    cov_lines = [f"     每合约日频长度: 中位 {int(cnt.median())} 均值 {cnt.mean():.1f} "
                 f"min {cnt.min()} max {cnt.max()}"]
    for N in [10, 20, 30, 40, 60]:
        c = (cnt >= N).sum()
        cov_lines.append(f"       skew窗口 N={N}: 满足>=N日合约 {c}/{len(cnt)} ({c/len(cnt)*100:.0f}%)")
    print("\n".join(cov_lines))

    # 逐合约算 A/C 双轨秩坐标
    print(f"[2] 滚动归一化 (skew={SKEW_WIN}d / atr={ATR_WIN}d / trend={TREND_WIN}d) ...")
    parts = []
    for _, g in daily.groupby("contract"):
        coords = build_daily_coords(g)
        blk = pd.concat([g[["contract", "event_date"]], coords], axis=1)
        parts.append(blk)
    coords_all = pd.concat(parts, ignore_index=True)
    print(f"     秩坐标范围检查: sk_A∈[{coords_all['sk_A'].min():.3f},{coords_all['sk_A'].max():.3f}] "
          f"sk_C∈[{coords_all['sk_C'].min():.3f},{coords_all['sk_C'].max():.3f}]")

    # 回扩到逐事件行
    merged = df.merge(coords_all, on=["contract", "event_date"], how="left")

    # 双轨分类
    print("[3] 双轨重分类 (v3.1 -> v4.0 tier) ...")
    a_cls = classify_track(merged, "A")
    c_cls = classify_track(merged, "C")
    merged = pd.concat([merged,
                        a_cls.rename(columns={"tier": "tier_A", "tier_v40": "tier_v40_A"}),
                        c_cls.rename(columns={"tier": "tier_C", "tier_v40": "tier_v40_C"})], axis=1)

    # ---- 诊断 ----
    print("[4] 诊断 ...")
    valid = merged.dropna(subset=["sk_A", "sk_C", "atr_A", "atr_C", "tr_A", "tr_C"])
    diag_lines = []
    diag_lines.append("# P0.1 · 诊断报告（正确口径 A vs C 双轨）\n")
    diag_lines.append(f"- 源事件: {len(df)} | 日频行: {len(daily)} | 合约: {df['contract'].nunique()}")
    diag_lines.append(f"- 窗口: skew={SKEW_WIN}d atr={ATR_WIN}d trend={TREND_WIN}d\n")
    diag_lines.append("## A/C 秩坐标相关性（Pearson，有效样本 {n}）".format(n=len(valid)))
    for nm, a, c in [("skew", "sk_A", "sk_C"), ("atr", "atr_A", "atr_C"), ("trend", "tr_A", "tr_C")]:
        r = valid[a].corr(valid[c])
        diag_lines.append(f"- {nm}: r = {r:.5f}")
    diag_lines.append("")
    # tier 一致率
    both = merged.dropna(subset=["tier_v40_A", "tier_v40_C"])
    agree = (both["tier_v40_A"] == both["tier_v40_C"]).mean()
    diag_lines.append(f"## tier(v4.0) 一致率（A vs C，双轨均非 None 的样本 {len(both)}）")
    diag_lines.append(f"- 一致率 = **{agree*100:.2f}%**")
    flip = both[both["tier_v40_A"] != both["tier_v40_C"]]
    if len(flip):
        diag_lines.append("- 不一致明细 (A -> C 计数):")
        for (a, c), n in flip.groupby(["tier_v40_A", "tier_v40_C"]).size().items():
            diag_lines.append(f"  - {a} -> {c}: {n}")
    diag_lines.append("")
    diag_lines.append("## tier 分布（v4.0）")
    for trk in ["A", "C"]:
        vc = merged[f"tier_v40_{trk}"].value_counts()
        diag_lines.append(f"### 轨 {trk}（非 None 共 {merged[f'tier_v40_{trk}'].notna().sum()}）")
        for k, v in vc.items():
            diag_lines.append(f"- {k}: {v}")
    diag_lines.append("")
    (OUT / "diag.md").write_text("\n".join(diag_lines), encoding="utf-8")
    print("     写出 diag.md")

    # ---- 写 timeline ----
    print("[5] 写出正确口径 timeline ...")
    base_cols = [c for c in df.columns]  # 保留全部原始列

    # calA：以 A 轨替换 rank 坐标与 tier（= 修正版 B0）
    calA = merged[base_cols].copy()
    calA["signed_skew_rank_roll"] = merged["sk_A"]
    calA["atr_rank_roll"] = merged["atr_A"]
    calA["trend_rank_roll"] = merged["tr_A"]
    calA["skew_label"] = a_cls["tier"].map(lambda t: t.split("_")[0] if isinstance(t, str) else None)
    calA["tier"] = a_cls["tier"]
    calA["tier_v40"] = a_cls["tier_v40"]
    calA.to_parquet(OUT / "timeline_calA.parquet", index=False)

    # calC
    calC = merged[base_cols].copy()
    calC["signed_skew_rank_roll"] = merged["sk_C"]
    calC["atr_rank_roll"] = merged["atr_C"]
    calC["trend_rank_roll"] = merged["tr_C"]
    calC["skew_label"] = c_cls["tier"].map(lambda t: t.split("_")[0] if isinstance(t, str) else None)
    calC["tier"] = c_cls["tier"]
    calC["tier_v40"] = c_cls["tier_v40"]
    calC.to_parquet(OUT / "timeline_calC.parquet", index=False)

    # calAC 合并巡检
    merged.to_parquet(OUT / "timeline_calAC.parquet", index=False)

    print(f"     timeline_calA.parquet : {len(calA)} 行 | A 非None tier {calA['tier'].notna().sum()}")
    print(f"     timeline_calC.parquet : {len(calC)} 行 | C 非None tier {calC['tier'].notna().sum()}")
    print(f"     timeline_calAC.parquet: 合并双轨（含 sk_A/atr_A/tr_A/sk_C/atr_C/tr_C + tier_A/tier_C）")
    print("\nP0.1 完成。下一步：va_p03_compare_ac.py 在其上跑 P3（A vs C 配对确认）。")


if __name__ == "__main__":
    main()
