#!/usr/bin/env python3
"""单 tier 内收益峰值时间点 t* 的分布 + 合约聚集检验。

对每个 tier (及全样本):
  (1) 每笔事件算 in-sample t* = 累积 raw pnl 峰值距入场的分钟数。
  (2) 分布: n / mean / median / std / p10 / p90 / 单调到终点占比。
  (3) 合约聚集: 按 symbol 做 one-way 分解, eta^2 = SS_between / SS_total
      (symbol 对 t* 变异的解释力; 高=强聚集, 低=随机散布)。
  (4) 列各 symbol 的 t* 均值(仅 n>=3), 看 spread。

口径: pnl_raw = sign*(close-ep)/ep*10000 (忽略成本常数偏移, 不影响峰值位置);
      t* = argmax(pnl_raw over hold window) * 5min。
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from collections import defaultdict

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1

GLOBAL = {}


def tstar_of(contract, g):
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    cp = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not cp.exists():
        return []
    if contract not in GLOBAL:
        b = pd.read_csv(cp, usecols=["datetime", "high", "low", "close"])
        b["datetime"] = pd.to_datetime(b["datetime"])
        b = b.sort_values("datetime").reset_index(drop=True)
        GLOBAL[contract] = b if not b.empty else None
    bars = GLOBAL[contract]
    if bars is None:
        return []
    out = []
    for _, ev in g.iterrows():
        d = ev["direction"]; sign = 1 if d == "long" else -1
        total = (P1.H_L if d == "long" else P1.H_S) * 12
        atr = float(ev["entry_atr_bps"])
        if atr <= 0:
            continue
        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        eidx = idx
        if eidx >= len(bars):
            continue
        ep = float(bars.iloc[eidx]["close"])
        if ep <= 0:
            continue
        future = bars.iloc[eidx: eidx + total]
        if len(future) == 0:
            continue
        closes = future["close"].to_numpy(dtype=float)
        raw = sign * (closes - ep) / ep * 10000.0
        k = int(np.argmax(raw))
        tstar_min = k * 5
        out.append({"symbol": (P1.extract_contract_prefix(contract) or "").lower(),
                    "tier": ev["tier_v40"], "tstar": tstar_min,
                    "mono": k == len(raw) - 1})
    return out


def eta_squared(g):
    """g: DataFrame with tstar, symbol. 返回 eta^2 (symbol 解释力)"""
    if g["symbol"].nunique() < 2 or len(g) < 5:
        return float("nan")
    grand = g["tstar"].mean()
    ss_total = ((g["tstar"] - grand) ** 2).sum()
    ss_between = 0.0
    for s, sg in g.groupby("symbol"):
        ss_between += len(sg) * (sg["tstar"].mean() - grand) ** 2
    return ss_between / ss_total if ss_total > 0 else float("nan")


def report(name, rows):
    t = pd.DataFrame(rows)
    n = len(t)
    if n == 0:
        print(f"  {name}: 无数据")
        return
    ts = t["tstar"]
    print(f"\n  [{name}]  n={n}")
    print(f"     t* 分布: mean={ts.mean():.0f}min  median={ts.median():.0f}min  "
          f"std={ts.std():.0f}min  p10={ts.quantile(.1):.0f}  p90={ts.quantile(.9):.0f}")
    print(f"     单调到终点(无更早峰值)占比: {t['mono'].mean()*100:.1f}%")
    eta = eta_squared(t)
    etas = f"{eta:.3f}" if not np.isnan(eta) else "n/a"
    print(f"     合约聚集 eta^2(symbol) = {etas}  "
          f"(symbol 数={t['symbol'].nunique()})")
    # 各 symbol 的 t* 均值
    sym_means = t.groupby("symbol")["tstar"].agg(["size", "mean", "std"])
    sym_means = sym_means[sym_means["size"] >= 3].sort_values("mean")
    if len(sym_means) >= 2:
        spread = sym_means["mean"].max() - sym_means["mean"].min()
        print(f"     各 symbol t* 均值 (n>=3): 跨 symbol spread={spread:.0f}min")
        for s, r in sym_means.iterrows():
            print(f"        {s:>6} n={int(r['size']):>2}  mean={r['mean']:.0f}  std={r['std']:.0f}")


def main():
    events = P1.load_events()
    print("=" * 78)
    print("单 tier 内收益峰值 t* 分布 + 合约聚集检验 (in-sample)")
    print("=" * 78)

    # 全样本
    all_rows = []
    for c, g in events.groupby("contract"):
        all_rows.extend(tstar_of(c, g))
    print("\n" + "#" * 78)
    print("# 全样本 (对照 P2 择时测试)")
    print("#" * 78)
    report("ALL", all_rows)

    # 逐 tier
    for camp, sub in events.groupby("tier_v40"):
        rows = []
        for c, g in sub.groupby("contract"):
            rows.extend(tstar_of(c, g))
        print("\n" + "#" * 78)
        print(f"# 阵营 {camp}  (方向={sub['direction'].iloc[0]}, n={len(sub)})")
        print("#" * 78)
        report(camp, rows)


if __name__ == "__main__":
    main()
