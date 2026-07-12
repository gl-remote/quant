#!/usr/bin/env python3
"""
va-composite · P0.1（干净版）· 最小修复：只隔离 skew 去重这一个变量

背景: 之前 va_p01_build_ac_tracks.py 把 4 类改动（① skew 去重 ② skew 窗口
100事件→20天 ③ rank 公式 past/N-1→(w<=x)/N ④ min_periods 10→20 + 整轨重分类）
捆在一起，且回测引擎与归档 B0 不同，无法干净归因。本脚本只做【① skew 去重】，
其余（atr/trend 秩、tier 分类公式、warmup、窗口=100/天=20、min_periods=10）
全部对齐旧管线（poc_va_asymmetry_stage2_grid_search.py），以得到单一变量 A/B。

关键事实: 回测引擎 load_events() 只读 `tier` 列（按 A_TIER_RAW 过滤），
不读 signed_skew_rank_roll。故 skew 去重只能通过改变 tier 分类影响结果——
本脚本用同一 POCVAClassifier 在「冻结原秩」与「去重后 skew 秩」上各算一次 tier：

  - timeline_ctrl.parquet   : 用【冻结原秩】(signed/atr/trend 全用旧值) 重算 tier
                              —— 应 100% 等于冻结 tier（校验确定性 + 可复现）
  - timeline_calA_min.parquet: 用【去重后 skew 秩】+ 冻结 atr/trend 秩 重算 tier
                              —— 相对 ctrl 的【唯一差异】= skew 是否去重

输出:
  project_data/ai_tmp/p0_calib/timeline_ctrl.parquet
  project_data/ai_tmp/p0_calib/timeline_calA_min.parquet
  project_data/ai_tmp/p0_calib/calA_min_diag.md
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

ROLLING_EVENTS = 100  # 旧管线 skew 窗口（逐事件行上滚）
ROLLING_DAYS = 20     # 旧管线 atr/trend 窗口（逐日去重后滚，本就不需修）
MIN_PERIODS = 10      # 旧管线 min_periods

A_TIER_RAW = {
    "UP2_atrLow_up_stable", "UP3_atrMid_up_stable",
    "UP1_atrHigh_up_trans",
    "DN1_atrHigh_down_stable", "DN1_atrHigh_down_trans",
    "DN2_atrHigh_down_stable", "DN2_atrHigh_down_trans",
    "DN3_atrHigh_down_stable", "DN3_atrHigh_down_trans",
    "DN4_atrHigh_down_stable", "DN4_atrHigh_down_trans",
    "DN2_atrMid_down_stable", "DN2_atrMid_down_trans",
}


# ---------------------------------------------------------------------------
# 旧管线 rolling_pct_rank（逐字复刻 poc_va_asymmetry_stage2_grid_search.py:148）
# ---------------------------------------------------------------------------
def rolling_pct_rank(series: pd.Series, window: int) -> pd.Series:
    def rank_last(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        past = x.iloc[:-1]
        return (past <= current).sum() / len(past)
    return series.rolling(window, min_periods=MIN_PERIODS).apply(rank_last, raw=False)


def deduped_skew_rank(df: pd.DataFrame) -> pd.Series:
    """【唯一修复】对每合约先 drop_duplicates(event_date)（A3_skew 日内恒定，取首值），
    再按旧公式 / 旧窗口(100)/ 旧 min_periods(10) 滚。返回对齐到每 (contract,event_date) 的秩。"""
    parts = []
    for c, g in df.groupby("contract"):
        gd = g.drop_duplicates("event_date").sort_values("event_time").copy()
        gd["sk_fixed"] = rolling_pct_rank(gd["A3_skew"], ROLLING_EVENTS)
        parts.append(gd[["contract", "event_date", "sk_fixed"]])
    m = pd.concat(parts, ignore_index=True)
    return df.merge(m, on=["contract", "event_date"], how="left")["sk_fixed"]


def classify(df: pd.DataFrame, skew_col: str, label: str) -> pd.Series:
    """用同一 POCVAClassifier 在给定 skew 列 + 冻结 atr/trend 秩上重算 tier。

    返回与 df 同索引的 Series（NaN = 未分类/NEUTRAL）。
    """
    tmp = df[["contract", "event_time", "transition_flag",
              skew_col, "atr_rank_roll", "trend_rank_roll"]].copy()
    tmp = tmp.rename(columns={skew_col: "signed_skew_rank_roll"})
    tmp = tmp.dropna(subset=["signed_skew_rank_roll", "atr_rank_roll", "trend_rank_roll"])
    res = POCVAClassifier().evaluate_dataset(tmp).dropna(subset=["tier"])
    # res 索引是 df 索引的子集；reindex 回 df.index（缺失填 NaN），保证与 df 对齐
    return res["tier"].reindex(df.index)


def main() -> None:
    print("=" * 70)
    print("va-composite · P0.1（干净版）· 最小修复：仅 skew 去重")
    print("=" * 70)

    df = pd.read_parquet(SRC)
    df["event_time"] = pd.to_datetime(df["event_time"])
    if "event_date" not in df.columns:
        df["event_date"] = df["event_time"].dt.date
    print(f"[0] 源 timeline: {len(df)} 行 | {df['contract'].nunique()} 合约")

    # ---- 控制组：用冻结原秩重算 tier（应 100% == 冻结 tier）----
    print("[1] 控制组：冻结原秩 → 重算 tier ...")
    ctrl_tier = classify(df, "signed_skew_rank_roll", "ctrl")
    # 注意：冻结 tier 含 None（NEUTRAL），NaN==NaN 在 pandas 为 False，需显式处理
    both_na = ctrl_tier.isna() & df["tier"].isna()
    agree = (ctrl_tier == df["tier"]).mean()
    agree_true = ((ctrl_tier == df["tier"]) | both_na).mean()
    n_disagree = int(((ctrl_tier != df["tier"]) & ~both_na).sum())
    print(f"    控制组 tier 与冻结 tier 一致率 = {agree_true*100:.2f}% "
          f"(含 None 行 {int(both_na.sum())}；真正不一致 {n_disagree} 行)")
    ctrl_mask = ctrl_tier.isin(A_TIER_RAW)

    # ---- 实验组：去重后 skew 秩 + 冻结 atr/trend 秩 → 重算 tier ----
    print("[2] 实验组：skew 去重（唯一修复）后重算 tier ...")
    sk_fixed = deduped_skew_rank(df)
    df_fixed = df.copy()
    df_fixed["signed_skew_rank_roll"] = sk_fixed
    fix_tier = classify(df_fixed, "signed_skew_rank_roll", "fix")
    fix_mask = fix_tier.isin(A_TIER_RAW)

    # ---- 写出两个 timeline（保留全部原列，仅覆盖 tier / skew 秩）----
    ctrl_out = df.copy()
    ctrl_out["tier"] = ctrl_tier
    ctrl_out["signed_skew_rank_roll"] = df["signed_skew_rank_roll"]  # 原值
    ctrl_out.to_parquet(OUT / "timeline_ctrl.parquet", index=False)

    fix_out = df.copy()
    fix_out["tier"] = fix_tier
    fix_out["signed_skew_rank_roll"] = sk_fixed  # 去重后值
    fix_out.to_parquet(OUT / "timeline_calA_min.parquet", index=False)

    # ---- 诊断 ----
    print("[3] 诊断 ...")
    diag = []
    diag.append("# P0.1（干净版）· 最小修复诊断\n")
    diag.append(f"- 源事件: {len(df)} | 合约: {df['contract'].nunique()}")
    diag.append(f"- 控制组 tier 与冻结 tier 一致率: **{agree*100:.2f}%**（校验分类确定性 + 可复现）\n")
    diag.append("## A_TIER_RAW 事件数（单一变量 A/B）")
    diag.append(f"- 控制组 (冻结 skew 秩)      : {int(ctrl_mask.sum())}")
    diag.append(f"- 实验组 (skew 去重)         : {int(fix_mask.sum())}")
    diag.append(f"- 差异 (fix - ctrl)         : {int(fix_mask.sum() - ctrl_mask.sum())}\n")
    diag.append("## 逐行 tier 变化（ctrl → fix，仅 skew 去重导致）")
    both = pd.DataFrame({"ctrl": ctrl_tier, "fix": fix_tier})
    both["ctrl_A"] = both["ctrl"].isin(A_TIER_RAW)
    both["fix_A"] = both["fix"].isin(A_TIER_RAW)
    # 进入/离开 A 级
    enter = both[(~both["ctrl_A"]) & both["fix_A"]]
    leave = both[both["ctrl_A"] & (~both["fix_A"])]
    flip = both[both["ctrl_A"] & both["fix_A"] & (both["ctrl"] != both["fix"])]
    diag.append(f"- 新进入 A 级: {len(enter)}")
    diag.append(f"- 离开 A 级: {len(leave)}")
    diag.append(f"- 留在 A 级但内部 tier 翻转: {len(flip)}")
    diag.append("")
    diag.append("## 含义")
    diag.append("- 若 fix 与 ctrl 的 A_TIER_RAW 数 + tier 结构几乎一致 → skew 去重仅为 ≤0.05 秩 jitter（spec §1.3.0），")
    diag.append("  旧管线『重复行』缺陷对 B0 影响可忽略；此前 calA 的走弱来自被混淆的其他 3 项改动，非真正的 bug。")
    diag.append("- 若差异显著 → skew 去重确为真实缺陷，需据 fix 重跑 P1/P5。")
    (OUT / "calA_min_diag.md").write_text("\n".join(diag), encoding="utf-8")
    print("     写出 calA_min_diag.md")

    print(f"\n[完成] 控制组 A 事件 {int(ctrl_mask.sum())} | 实验组 A 事件 {int(fix_mask.sum())}")
    print(f"       控制组 tier 复现率 {agree_true*100:.2f}%（真正不一致 {n_disagree} 行）")
    print("       产物: timeline_ctrl.parquet / timeline_calA_min.parquet")


if __name__ == "__main__":
    main()
