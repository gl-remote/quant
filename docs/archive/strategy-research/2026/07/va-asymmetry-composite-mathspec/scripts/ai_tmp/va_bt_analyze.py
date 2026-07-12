#!/usr/bin/env python3
"""仅分析已保存的 trades（避免重跑模拟）"""
import sys; from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace")); sys.path.insert(0, str(REPO / "scripts" / "ai_tmp"))

import pandas as pd, numpy as np
import va_composite_p1_cap as P1

fp = REPO / "project_data/ai_tmp/va_classifier_bt/trades.parquet"
if not fp.exists():
    print("先跑 va_classifier_backtest.py 生成 trades")
    sys.exit(1)

trades = pd.read_parquet(fp)
trades["_entry_date"] = pd.to_datetime(trades["_entry_date"])

# ── 年度贡献 ──
trades["year"] = trades["_entry_date"].dt.year
print("=== 年度 pnl ===")
for y, g in trades.groupby("year"):
    print(f"  {y}: {g['pnl_net_ccy'].sum():+.0f} ({len(g)}笔)")

# ── 合约集中度 ──
per_c = trades.groupby("contract")["pnl_net_ccy"].sum().sort_values(ascending=False)
total_pnl = per_c.sum()
for pct in [3, 5, 10]:
    share = per_c.head(pct).sum() / total_pnl * 100
    print(f"\ntop{pct}合约占比: {share:.1f}%")
print("Top5:")
for c in per_c.head(5).index:
    print(f"  {c}: {per_c[c]:+.0f}")
print("Bottom5:")
for c in per_c.tail(5).index:
    print(f"  {c}: {per_c[c]:+.0f}")

# ── 盈亏比 ──
wins = trades[trades["pnl_net_ccy"] > 0]
losses = trades[trades["pnl_net_ccy"] < 0]
wl = abs(wins["pnl_net_ccy"].mean() / losses["pnl_net_ccy"].mean()) if len(losses) > 0 else float("nan")
print(f"\n胜率: {len(wins)/len(trades)*100:.1f}% ({len(wins)}/{len(trades)}) | 盈亏比: {wl:.2f}")

# ── 极端单笔 ──
print("\n=== 最大 5 笔 ===")
for _, r in trades.nlargest(5, "pnl_net_ccy").iterrows():
    print(f"  {r['contract']} {r['_entry_date'].date()} {r['direction']}: {r['pnl_net_ccy']:+.0f} ({r['pnl_net_bps']:+.0f}bps)")
print("=== 最大亏损 5 笔 ===")
for _, r in trades.nsmallest(5, "pnl_net_ccy").iterrows():
    print(f"  {r['contract']} {r['_entry_date'].date()} {r['direction']}: {r['pnl_net_ccy']:+.0f} ({r['pnl_net_bps']:+.0f}bps)")

# ── 方向 ──
print(f"\n方向: 多={trades[trades['direction']=='long']['pnl_net_ccy'].sum():+.0f} "
      f"空={trades[trades['direction']=='short']['pnl_net_ccy'].sum():+.0f}")

# ── 单笔收益分布 ──
print(f"\n单笔收益(ccy): mean={trades['pnl_net_ccy'].mean():.0f} median={trades['pnl_net_ccy'].median():.0f} "
      f"std={trades['pnl_net_ccy'].std():.0f}")
print(f"单笔收益(bps): mean={trades['pnl_net_bps'].mean():.1f} median={trades['pnl_net_bps'].median():.1f}")

# ── 月度序列 ──
trades["month"] = trades["_entry_date"].dt.to_period("M")
monthly = trades.groupby("month")["pnl_net_ccy"].sum()
print(f"\n月度 pnl: 正={int((monthly>0).sum())}/{len(monthly)} = {(monthly>0).mean()*100:.0f}%")
print(f"月均: {monthly.mean():.0f} 月std: {monthly.std():.0f}")
print(f"最差月: {monthly.idxmin()} {monthly.min():+.0f}")
print(f"最好月: {monthly.idxmax()} {monthly.max():+.0f}")
