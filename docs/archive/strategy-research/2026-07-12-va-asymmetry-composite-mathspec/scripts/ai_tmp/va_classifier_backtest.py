#!/usr/bin/env python3
"""
快速验证 poc_va 分类器表现（研究级，复用 P1 冻结引擎和 timeline_calAC 数据）

运行: uv run python scripts/ai_tmp/va_classifier_backtest.py

前视偏差修复（2026-07-12）：
  - daily_atr_10_bps 和 trend_ret_10d 原用当日 OHLC（含未来全天的 H/L/Close）
  - 已修复为前日值（逐合约 shift(1)），消除日内 look-ahead
  - 默认使用 timeline_calAC_fixed.parquet；可通过 USE_FIXED=False 切回旧口径
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

import va_composite_p1_cap as P1
from strategies.classifiers.poc_va import evaluate_dataset, ClassifierConfig

# ── 数据 ──
USE_FIXED = True  # True=前日ATR/trend(无前视)  False=当日ATR/trend(原口径,含前视)
if USE_FIXED:
    TL = REPO / "project_data/ai_tmp/p0_calib/timeline_calAC_fixed.parquet"
    DATA_LABEL = "fixed (前日ATR/trend, 无前视)"
else:
    TL = REPO / "project_data/ai_tmp/p0_calib/timeline_calAC.parquet"
    DATA_LABEL = "original (当日ATR/trend, 含前视)"

CAP = 4.0
DEDUP_H = 8

print("=" * 70)
print("poc_va 分类器回测验证")
print(f"  数据: {DATA_LABEL}")
print(f"  Cap={CAP}  |  dedup={DEDUP_H}h")
print("=" * 70)

# ── 加载 ──
tl = pd.read_parquet(TL)
tl["event_time"] = pd.to_datetime(tl["event_time"])
print(f"\n[0] 原始数据: {len(tl)} 行, {tl.contract.nunique()} 合约")

# 运行分类器前须按 contract + event_time 排序
tl = tl.sort_values(["contract", "event_time"]).reset_index(drop=True)

# ── 运行分类器 ──
print("\n[1] evaluate_dataset (spec v4.0 六阵营, t-PIT 归一化)...")
result = evaluate_dataset(
    tl,
    a3_skew_col="A3_skew",
    atr_col="daily_atr_10_bps",
    trend_col="trend_ret_10d",
)
print(f"    活跃事件: {result['tier'].notna().sum()} / {len(result)} "
      f"({result['tier'].notna().mean()*100:.1f}%)")
print(f"    方向: 多={(result['direction']=='long').sum()} / 空={(result['direction']=='short').sum()}")
print(f"\n    tier 分布:")
for t, c in result["tier"].value_counts().items():
    print(f"      {t}: {c}")

# ── 与已有 tier_v40_A 对比 ──
if "tier_v40_A" in tl.columns:
    match_mask = result["tier"].notna() & tl["tier_v40_A"].notna()
    if match_mask.sum() > 0:
        agree = (result.loc[match_mask, "tier"].values == tl.loc[match_mask, "tier_v40_A"].values).mean()
        print(f"\n    与 tier_v40_A 活跃集交集: {match_mask.sum()} 行, 一致率: {agree*100:.1f}%")

if "tier_v40_C" in tl.columns:
    match_mask = result["tier"].notna() & tl["tier_v40_C"].notna()
    if match_mask.sum() > 0:
        agree = (result.loc[match_mask, "tier"].values == tl.loc[match_mask, "tier_v40_C"].values).mean()
        print(f"    与 tier_v40_C 活跃集交集: {match_mask.sum()} 行, 一致率: {agree*100:.1f}%")

# ── 构建事件 ──
print(f"\n[2] 构建事件 (dedup={DEDUP_H}h)...")
# evaluate_dataset 返回的 DataFrame 带了新列但 contract 列在 groupby 后丢失，从 tl 补回
result["contract"] = tl["contract"].values
events = result.dropna(subset=["tier"]).copy()
# 保留需要的列
events = events[["contract", "event_time", "tier", "direction"]]
# merge 回 close_t 和 daily_atr_10_bps
events = events.merge(
    tl[["contract", "event_time", "close_t", "daily_atr_10_bps"]],
    on=["contract", "event_time"], how="left"
)
events = events.sort_values(["contract", "event_time"]).reset_index(drop=True)
prev = events.groupby("contract")["event_time"].shift(1)
events = events[(prev.isna()) | ((events["event_time"] - prev) > pd.Timedelta(hours=DEDUP_H))]
events = events.reset_index(drop=True)

# entry_atr_bps: daily_atr_10_bps 已为 bps，直接用
events["entry_atr_bps"] = events["daily_atr_10_bps"]

print(f"    去重后事件: {len(events)} | 合约 {events['contract'].nunique()} | "
      f"多 {(events['direction']=='long').sum()} / 空 {(events['direction']=='short').sum()}")

# ── 模拟 ──
print(f"\n[3] 冻结引擎模拟 (Cap={CAP})...")
rows = []
for c, g in events.groupby("contract"):
    rows.extend(P1.simulate_contract(c, g))
trades = pd.DataFrame(rows)
trades = P1.assign_equity(P1.compress(trades, CAP))
print(f"    交易笔数: {len(trades)} | 合约 {trades['contract'].nunique()}")

# ── 指标 ──
print("\n[4] 指标...")
ad = P1.active_day_set(tl, "signed_skew_rank_roll")
m = P1.base_metrics(trades, active_days=ad)
m["monthly_win"] = P1.monthly_win_rate(trades)
m["ir"] = P1.per_trade_ir(trades)
m["nu_implied"], m["p_nu_pos"] = P1.nu_implied(trades)

print(f"    年化收益: {m['ann_ret']*100:.2f}%")
print(f"    夏普:     {m['sharpe']:.2f}")
print(f"    MaxDD:    {m['max_dd']*100:.2f}%")
print(f"    月度胜率: {m['monthly_win']*100:.1f}%")
print(f"    单笔IR:   {m['ir']:.3f}")
print(f"    ν_implied: {m['nu_implied']:+.3f}  P(ν>0)={m['p_nu_pos']:.3f}")

# ── OOS ──
times = np.sort(trades["_entry_date"].values)
split = pd.Timestamp(np.quantile(times, 0.5)).date()
trades_oos = trades[trades["_entry_date"] >= split]
m_oos = P1.base_metrics(trades_oos, active_days=ad)
m_oos["monthly_win"] = P1.monthly_win_rate(trades_oos)
m_oos["ir"] = P1.per_trade_ir(trades_oos)
m_oos["nu_implied"], m_oos["p_nu_pos"] = P1.nu_implied(trades_oos)

print(f"\n    OOS 切点(后50%): {split}")
print(f"    OOS 年化: {m_oos['ann_ret']*100:.2f}%")
print(f"    OOS 夏普: {m_oos['sharpe']:.2f}")
print(f"    OOS MaxDD: {m_oos['max_dd']*100:.2f}%")
print(f"    OOS 月度胜率: {m_oos['monthly_win']*100:.1f}%")
print(f"    OOS ν_implied: {m_oos['nu_implied']:+.3f}  P(ν>0)={m_oos['p_nu_pos']:.3f}")

# ── 保存交易明细 ──
OUT_DIR = REPO / "project_data/ai_tmp/va_classifier_bt"
OUT_DIR.mkdir(parents=True, exist_ok=True)
trades.to_parquet(OUT_DIR / "trades.parquet", index=False)
trades_oos.to_parquet(OUT_DIR / "trades_oos.parquet", index=False)

# ── 诊断 ──
trades["_entry_date"] = pd.to_datetime(trades["_entry_date"])
print("\n--- 诊断 ---")

# 年度贡献
trades["year"] = trades["_entry_date"].dt.year
print("年度 pnl:")
for y, g in trades.groupby("year"):
    print(f"  {y}: {g['pnl_net_ccy'].sum():+.0f} ({len(g)}笔)")

# 合约集中度
per_c = trades.groupby("contract")["pnl_net_ccy"].sum().sort_values(ascending=False)
top3 = per_c.head(3).sum() / per_c.sum() * 100
top5 = per_c.head(5).sum() / per_c.sum() * 100
print(f"\n合约集中度: top3={top3:.0f}% top5={top5:.0f}%")
print("Top5:")
for c in per_c.head(5).index:
    print(f"  {c}: {per_c[c]:+.0f}")

# 盈亏比
wins = trades[trades["pnl_net_ccy"] > 0]
losses = trades[trades["pnl_net_ccy"] < 0]
wl = abs(wins["pnl_net_ccy"].mean() / losses["pnl_net_ccy"].mean()) if len(losses) > 0 else float("nan")
print(f"\n胜率: {len(wins)/len(trades)*100:.1f}% | 盈亏比: {wl:.2f} | 笔数: {len(trades)}")

# 极端收益
print("最大5笔:")
for _, r in trades.nlargest(5, "pnl_net_ccy").iterrows():
    print(f"  {r['contract']} {r['_entry_date'].date()} {r['direction']}: {r['pnl_net_ccy']:+.0f}")
print("最小5笔:")
for _, r in trades.nsmallest(5, "pnl_net_ccy").iterrows():
    print(f"  {r['contract']} {r['_entry_date'].date()} {r['direction']}: {r['pnl_net_ccy']:+.0f}")

# 方向贡献
print(f"\n方向: 多={trades[trades['direction']=='long']['pnl_net_ccy'].sum():+.0f} "
      f"空={trades[trades['direction']=='short']['pnl_net_ccy'].sum():+.0f}")

# ── 终极判定 ──
print("\n" + "=" * 70)
sharpe_ok = m["sharpe"] > 0
oos_sharpe_ok = m_oos["sharpe"] > 0
print(f"全样本夏普 {m['sharpe']:.2f} {'✅ >0' if sharpe_ok else '❌ ≤0'}")
print(f"OOS 夏普   {m_oos['sharpe']:.2f} {'✅ >0' if oos_sharpe_ok else '❌ ≤0'}")
if sharpe_ok and oos_sharpe_ok:
    print("✅ 分类器有效：全样本 + OOS 均正夏普")
else:
    print("⚠️ 分类器需检查：夏普不满足")
