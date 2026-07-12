#!/usr/bin/env python3
"""
va-asymmetry · 逐环节 diff：旧管线(B0) → 新管线(spec) 每步换一个组件

原理：
  固定数据源 = classifier_v31_timeline_spec.parquet（新旧列都有），
  从 B0 基准（预计算 tier 列 + 旧白名单 + 旧 ATR + 无 open_grace）出发，
  每次只换一个组件，观察事件数、年化、夏普的变化，定位性能劣化源头。

diff 步骤：
  0: B0 ref (预计算 tier 列 + A_TIER_RAW 白名单 + daily_atr_10_bps + no grace)
  1: 重算 tier (signed_skew_rank_roll + atr_rank_roll + trend_rank_roll + old classifier)
      → 验证与步骤 0 一致（预计算 tier 本就是这些列算出的）
  2: swap skew (A3_skew_tick 横截面 rank → old binning → old classifier)
  3: swap trend (trend_ret_M_spec 横截面 rank → old binning → old classifier)
  4: swap skew+trend (both new → old classifier)
  5: swap 分类器 (spec v4.0 六阵营 + new features + daily_atr_spec/close_t bps + no grace)
  6: +open_grace (步骤 5 + 开盘 5min 过滤) → 完整 spec 新管线

运行: uv run python scripts/va_compare_pipeline_diff.py
输出: project_data/va_pipeline_diff/{summary.md, step_*.trades.parquet}
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

import va_composite_p1_cap as P1
from strategies.classifiers.poc_va import evaluate_dataset

TL_PATH = REPO / "project_data" / "logs" / "poc_va_asymmetry_stage4" / "classifier_v31_timeline_spec.parquet"
OUT = REPO / "project_data" / "va_pipeline_diff"
OUT.mkdir(parents=True, exist_ok=True)

CAP = 4.0
DEDUP_H = 8
OPEN_GRACE_MIN = 5.0

# ---- 旧分类器 binning（来自 va_composite_backtest.py） ----
_OLD_SKEW_T = (0.09, 0.19, 0.25, 0.30, 0.70, 0.75, 0.81, 0.91)
_OLD_SKEW_SEG = {"DN_1": "DN1", "DN_2": "DN2", "DN_3": "DN3", "DN_4": "DN4",
                 "UP_1": "UP1", "UP_2": "UP2", "UP_3": "UP3", "UP_4": "UP4"}
_OLD_ATR_SEG = {"low": "atrLow", "mid": "atrMid", "high": "atrHigh"}
_OLD_TREND_SEG = {"down": "down", "flat": "flat", "up": "up"}

# ---- 旧白名单 (与 P1.A_TIER_RAW 相同，直接复用) ----
_OLD_A_TIER = P1.A_TIER_RAW


def _old_skew_label(rank: float) -> str | None:
    if pd.isna(rank):
        return None
    t = _OLD_SKEW_T
    if rank <= t[0]: return "DN_1"
    if rank <= t[1]: return "DN_2"
    if rank <= t[2]: return "DN_3"
    if rank <= t[3]: return "DN_4"
    if rank < t[4]:  return "NEUTRAL"
    if rank < t[5]:  return "UP_4"
    if rank < t[6]:  return "UP_3"
    if rank < t[7]:  return "UP_2"
    return "UP_1"


def _old_atr_regime(rank: float) -> str | None:
    if pd.isna(rank): return None
    if rank <= 0.33: return "low"
    if rank < 0.67:  return "mid"
    return "high"


def _old_trend_regime(rank: float) -> str | None:
    if pd.isna(rank): return None
    if rank <= 0.20: return "down"
    if rank < 0.75:  return "flat"
    return "up"


def _old_tier_name(sl: str | None, ar: str | None, tr: str | None, tf: bool) -> str | None:
    if sl is None or sl == "NEUTRAL" or ar is None or tr is None or pd.isna(tf):
        return None
    d = _OLD_SKEW_SEG.get(sl)
    a = _OLD_ATR_SEG.get(ar)
    t = _OLD_TREND_SEG.get(tr)
    p = "trans" if tf else "stable"
    if d is None or a is None or t is None:
        return None
    return f"{d}_{a}_{t}_{p}"


def global_rank(s: pd.Series) -> pd.Series:
    """全局 pct rank(0~1)，对齐旧 rank 列(signed_skew_rank_roll 等)的计算口径。"""
    return s.rank(pct=True)


def compute_old_tiers(tl: pd.DataFrame, skew_col: str, atr_rank_col: str,
                      trend_rank_col: str, tf_col: str) -> pd.Series:
    """从（可能已 rank 化的）特征列计算旧 tier 标签。"""
    sl = tl[skew_col].apply(_old_skew_label)
    ar = tl[atr_rank_col].apply(_old_atr_regime)
    tr = tl[trend_rank_col].apply(_old_trend_regime)
    tfs = tl[tf_col]
    return pd.Series(
        [_old_tier_name(sl.iloc[i], ar.iloc[i], tr.iloc[i], tfs.iloc[i]) for i in range(len(tl))],
        index=tl.index,
    )


def dedup_8h(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev = df.groupby("contract")["event_time"].shift(1)
    return df[(prev.isna()) | ((df["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))].reset_index(drop=True)


def apply_open_grace(df: pd.DataFrame) -> pd.DataFrame:
    """跳过开盘首根 5min 内的事件。"""
    if OPEN_GRACE_MIN <= 0:
        return df
    so = df.apply(lambda r: _session_open(r["contract"], r["event_time"]), axis=1)
    within = so.notna() & ((df["event_time"] - so) < pd.Timedelta(minutes=OPEN_GRACE_MIN))
    return df[~within].copy()


_SESSION_OPEN_CACHE: dict = {}

def _session_open(contract: str, dt: pd.Timestamp) -> pd.Timestamp | None:
    if contract not in _SESSION_OPEN_CACHE:
        p = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
        if not p.exists():
            _SESSION_OPEN_CACHE[contract] = None
        else:
            b = pd.read_csv(p, usecols=["datetime"])
            b["datetime"] = pd.to_datetime(b["datetime"])
            _SESSION_OPEN_CACHE[contract] = b.sort_values("datetime").reset_index(drop=True)
    bars = _SESSION_OPEN_CACHE[contract]
    if bars is None or bars.empty:
        return None
    day = pd.Timestamp(dt).normalize()
    mask = (bars["datetime"] >= day) & (bars["datetime"] < day + pd.Timedelta(days=1))
    sub = bars.loc[mask, "datetime"]
    return None if sub.empty else sub.min()


# =====================================================================
# Diff 步骤定义
# =====================================================================

def step0_b0_ref(tl: pd.DataFrame) -> pd.DataFrame:
    """B0 基准：预计算 tier 列 + A_TIER_RAW 白名单 + 旧 ATR + no grace。"""
    a = tl[tl["tier"].isin(_OLD_A_TIER)].copy()
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = dedup_8h(a)
    return a


def step1_recompute_tier(tl: pd.DataFrame) -> pd.DataFrame:
    """重算 tier：用旧 rank 列重新计算，应与 step0 一致。"""
    tl = tl.copy()
    tl["tier_computed"] = compute_old_tiers(tl, "signed_skew_rank_roll", "atr_rank_roll",
                                            "trend_rank_roll", "transition_flag")
    a = tl[tl["tier_computed"].isin(_OLD_A_TIER)].copy()
    a["tier"] = a["tier_computed"]
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = dedup_8h(a)
    return a


def step2_skew_tick(tl: pd.DataFrame) -> pd.DataFrame:
    """swap skew: A3_skew_tick 全局 rank → old binning。"""
    tl = tl.copy()
    tl["skew_tick_rank"] = global_rank(tl["A3_skew_tick"])
    tl["tier_computed"] = compute_old_tiers(tl, "skew_tick_rank", "atr_rank_roll",
                                            "trend_rank_roll", "transition_flag")
    a = tl[tl["tier_computed"].isin(_OLD_A_TIER)].copy()
    a["tier"] = a["tier_computed"]
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = dedup_8h(a)
    return a


def step3_trend_ret(tl: pd.DataFrame) -> pd.DataFrame:
    """swap trend: trend_ret_M_spec 全局 rank → old binning。"""
    tl = tl.copy()
    tl["trend_ret_rank"] = global_rank(tl["trend_ret_M_spec"])
    tl["tier_computed"] = compute_old_tiers(tl, "signed_skew_rank_roll", "atr_rank_roll",
                                            "trend_ret_rank", "transition_flag")
    a = tl[tl["tier_computed"].isin(_OLD_A_TIER)].copy()
    a["tier"] = a["tier_computed"]
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = dedup_8h(a)
    return a


def step4_skew_trend_new(tl: pd.DataFrame) -> pd.DataFrame:
    """swap skew+trend: 两个都用新特征全局 rank + old classifier。"""
    tl = tl.copy()
    tl["skew_tick_rank"] = global_rank(tl["A3_skew_tick"])
    tl["trend_ret_rank"] = global_rank(tl["trend_ret_M_spec"])
    tl["tier_computed"] = compute_old_tiers(tl, "skew_tick_rank", "atr_rank_roll",
                                            "trend_ret_rank", "transition_flag")
    a = tl[tl["tier_computed"].isin(_OLD_A_TIER)].copy()
    a["tier"] = a["tier_computed"]
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = dedup_8h(a)
    return a


def step5_spec_no_grace(tl: pd.DataFrame) -> pd.DataFrame:
    """spec v4.0 六阵营 + new features + spec ATR + no grace。"""
    result = evaluate_dataset(
        tl,
        a3_skew_col="A3_skew_tick",
        atr_col="daily_atr_spec",
        trend_col="trend_ret_M_spec",
        norm_method="quantile",
    )
    df = result.dropna(subset=["tier"]).copy()
    df = dedup_8h(df)
    df["entry_atr_bps"] = df["daily_atr_spec"] / df["close_t"] * 10000.0
    return df.reset_index(drop=True)


def step6_spec_full(tl: pd.DataFrame) -> pd.DataFrame:
    """spec v4.0 + new features + spec ATR + open_grace。"""
    df = step5_spec_no_grace(tl)
    df = apply_open_grace(df)
    return df.reset_index(drop=True)


# ---- 模拟 + 指标 ----
def simulate_events(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c, g in events.groupby("contract"):
        rows.extend(P1.simulate_contract(c, g))
    return pd.DataFrame(rows)


def run_one(label: str, events: pd.DataFrame, active_days: int) -> dict:
    raw = simulate_events(events)
    t = P1.compress(raw, CAP)
    t = P1.assign_equity(t)
    m = P1.base_metrics(t, active_days=active_days)
    # OOS 后50%
    times = np.sort(t["_entry_date"].values)
    split = pd.Timestamp(np.quantile(times, 0.5)).date()
    t_oos = t[t["_entry_date"] >= split]
    m_oos = P1.base_metrics(t_oos, active_days=active_days)
    return {
        "label": label,
        "n_events": len(events),
        "n_contracts": events["contract"].nunique(),
        "n_long": int((events["direction"] == "long").sum()),
        "n_short": int((events["direction"] == "short").sum()),
        "ann_ret": m["ann_ret"],
        "sharpe": m["sharpe"],
        "max_dd": m["max_dd"],
        "win_rate": len(t[t["pnl_net_bps"] > 0]) / len(t) if len(t) else 0,
        "ann_ret_oos": m_oos["ann_ret"],
        "sharpe_oos": m_oos["sharpe"],
        "max_dd_oos": m_oos["max_dd"],
        "trades": t,
    }


# =====================================================================
# Main
# =====================================================================
STEPS = [
    ("0: B0 ref (预计算 tier + 旧白名单 + 旧ATR)", step0_b0_ref),
    ("1: 重算 tier (旧 rank 列 + 旧分类器)", step1_recompute_tier),
    ("2: swap skew (A3_skew_tick rank + 旧分类器)", step2_skew_tick),
    ("3: swap trend (trend_ret_M_spec rank + 旧分类器)", step3_trend_ret),
    ("4: swap skew+trend (新特征 rank + 旧分类器)", step4_skew_trend_new),
    ("5: swap 分类器 (spec v4.0 + 新特征 + no grace)", step5_spec_no_grace),
    ("6: +open_grace (完整 spec 新管线)", step6_spec_full),
]


def main():
    print("=" * 80)
    print("va-asymmetry · 逐环节 diff：B0(312/35.42%) → spec(513/22.59%)")
    print("=" * 80)

    print("[加载数据] ...")
    tl = pd.read_parquet(TL_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    ad = P1.active_day_set(tl, "signed_skew_rank_roll")

    results = []
    for label, fn in STEPS:
        print(f"\n--- {label} ---")
        events = fn(tl)
        n = len(events)
        print(f"  事件: {n} | 合约: {events['contract'].nunique()} | "
              f"多: {(events['direction']=='long').sum()} / 空: {(events['direction']=='short').sum()}")
        r = run_one(label, events, ad)
        print(f"  全量: 年化 {r['ann_ret']*100:.2f}% 夏普 {r['sharpe']:.2f} MaxDD {r['max_dd']*100:.2f}% "
              f"胜率 {r['win_rate']*100:.1f}%")
        print(f"  OOS : 年化 {r['ann_ret_oos']*100:.2f}% 夏普 {r['sharpe_oos']:.2f} MaxDD {r['max_dd_oos']*100:.2f}%")
        results.append(r)
        # 写出交易明细
        step_id = label.split(":")[0].strip()
        r["trades"].to_parquet(OUT / f"step_{step_id}_trades.parquet", index=False)

    # ---- 汇总表 ----
    print("\n" + "=" * 80)
    print("汇总对比表")
    print("=" * 80)
    header = f"{'步骤':<6} {'事件':>5} {'合约':>4} {'多':>4} {'空':>4} | {'年化全量':>8} {'夏普全量':>7} {'MaxDD全量':>8} {'胜率':>6} | {'年化OOS':>8} {'夏普OOS':>7} {'MaxDDOOS':>8}"
    print(header)
    print("-" * len(header))
    r0 = results[0]
    for r in results:
        dd = f"  Δ年化{r['ann_ret']-r0['ann_ret']:+.2%} Δ夏普{r['sharpe']-r0['sharpe']:+.2f}" if r != r0 else ""
        print(f"{r['label']:<6} {r['n_events']:>5} {r['n_contracts']:>4} {r['n_long']:>4} {r['n_short']:>4} | "
              f"{r['ann_ret']*100:>7.2f}% {r['sharpe']:>6.2f} {r['max_dd']*100:>7.2f}% {r['win_rate']*100:>5.1f}% | "
              f"{r['ann_ret_oos']*100:>7.2f}% {r['sharpe_oos']:>6.2f} {r['max_dd_oos']*100:>7.2f}%{dd}")

    # 写出 summary
    with open(OUT / "summary.md", "w") as f:
        f.write("# va-asymmetry 逐环节 diff\n\n")
        f.write("| 步骤 | 事件 | 合约 | 多 | 空 | 年化全量 | 夏普全量 | MaxDD全量 | 胜率 | 年化OOS | 夏普OOS | MaxDDOOS |\n")
        f.write("|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|\n")
        for r in results:
            f.write(f"| {r['label']} | {r['n_events']} | {r['n_contracts']} | {r['n_long']} | {r['n_short']} | "
                    f"{r['ann_ret']*100:.2f}% | {r['sharpe']:.2f} | {r['max_dd']*100:.2f}% | {r['win_rate']*100:.1f}% | "
                    f"{r['ann_ret_oos']*100:.2f}% | {r['sharpe_oos']:.2f} | {r['max_dd_oos']*100:.2f}% |\n")
    print(f"\n写出: {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()
