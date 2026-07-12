"""
文件级元信息：
- 创建背景：阶段 1 · gross 层证据链已建立（W1 × A3_skew × q=8% × ret_8h
  · UP-DN diff -36 bps · Bonferroni 通过）。用户要求测算真实成本后的
  利润空间。
- 用途：读 long_events.csv + workspace/common/contract_specs.py → 每合约
  真实 single-side cost = 佣金（按 entry price）+ 滑点（size × tick ×
  slip_tick）→ 分品种展开 UP/DN 的 gross mean 与 net mean，评估单边
  （DN 做多 / UP 做空）与双边（UP 做空 + DN 做多）净期望。
- 注意事项：临时研究脚本。命中率、年化夏普为粗估（无仓位管理，仅统计
  条件收益期望）。KF-5 教训：跨品种平均掩盖极端差异，必须分品种展开。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, "/Users/gaolei/Documents/src/quant")
from workspace.common.contract_specs import CONTRACT_SPECS

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

# 目标组合
WINDOW = "W1"
METRIC = "A3_skew"
QUANTILE = 0.08  # 每侧 8%（对应每合约每天 ~1 次触发）
HORIZONS = ["ret_1h", "ret_2h", "ret_4h", "ret_8h"]


def get_single_side_cost_bps(symbol: str, entry_price: float) -> float:
    """单边成本（bps of entry price）= 佣金 + 滑点。

    佣金：spec.total_commission(price, lots=1)（元/手）
    滑点：spec.slippage(lots=1)（元/手，= size × tick × slip_tick）
    换算 bps：cost_yuan / (entry_price × size) × 1e4
    """
    spec = CONTRACT_SPECS.get_symbol(symbol)
    if spec is None:
        return float("nan")
    commission = spec.total_commission(entry_price, lots=1)
    slippage = spec.slippage(lots=1)
    total_yuan_per_lot = commission + slippage
    contract_value = entry_price * spec.size  # 合约总值（元/手）
    if contract_value <= 0:
        return float("nan")
    return total_yuan_per_lot / contract_value * 1e4  # bps


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    print(f"Loaded long table: rows={len(df)}", flush=True)

    sub = df[df["window"] == WINDOW].copy()

    # 每合约的成本估算：用该合约整个样本的 close_t 中位数作为代表 entry price
    print("\n=== 每合约真实单边成本估算 ===")
    print(f"{'symbol':16s} {'median_price':>13s} {'size':>6s} {'tick':>6s} "
          f"{'comm_yuan':>10s} {'slip_yuan':>10s} {'total_bps':>10s}")
    per_contract_cost: dict[str, float] = {}
    for contract, g in sub.groupby("contract", sort=False):
        price = float(g["close_t"].median())
        cost_bps = get_single_side_cost_bps(contract, price)
        per_contract_cost[contract] = cost_bps
        spec = CONTRACT_SPECS.get_symbol(contract)
        if spec is not None:
            comm = spec.total_commission(price, lots=1)
            slip = spec.slippage(lots=1)
            print(f"{contract:16s} {price:>13.2f} {spec.size:>6d} {spec.tick:>6.2f} "
                  f"{comm:>10.2f} {slip:>10.2f} {cost_bps:>10.2f}")

    # 应用 q=8% 阈值筛选 UP/DN
    print(f"\n=== 分品种 · {WINDOW} × {METRIC} × q=±{QUANTILE:.0%} · net after single-side cost ===")

    rows: list[dict] = []
    for contract, g in sub.groupby("contract", sort=False):
        vals = g[METRIC].dropna()
        if len(vals) < 100:
            continue
        hi = vals.quantile(1 - QUANTILE)
        lo = vals.quantile(QUANTILE)
        cost_bps = per_contract_cost[contract]

        for h in HORIZONS:
            up = g.loc[g[METRIC] >= hi, h].dropna().to_numpy()
            dn = g.loc[g[METRIC] <= lo, h].dropna().to_numpy()
            if len(up) < 10 or len(dn) < 10:
                continue

            # gross mean in bps
            mean_up_bps = float(up.mean()) * 1e4
            mean_dn_bps = float(dn.mean()) * 1e4
            hit_up = float((up > 0).mean())
            hit_dn = float((dn > 0).mean())

            # 单边策略：
            # DN 组做多：gross = +mean_dn_bps；net = mean_dn_bps - cost_bps
            # UP 组做空：gross = -mean_up_bps；net = -mean_up_bps - cost_bps
            net_dn_long = mean_dn_bps - cost_bps
            net_up_short = (-mean_up_bps) - cost_bps
            # 双边（合计一笔往返成本 = 2 × single_side_cost）
            net_both = (mean_dn_bps - mean_up_bps) - 2 * cost_bps

            rows.append(
                {
                    "contract": contract,
                    "horizon": h,
                    "n_up": len(up),
                    "n_dn": len(dn),
                    "mean_up_bps": mean_up_bps,
                    "mean_dn_bps": mean_dn_bps,
                    "hit_up": hit_up,
                    "hit_dn": hit_dn,
                    "single_side_cost_bps": cost_bps,
                    "net_dn_long_bps": net_dn_long,
                    "net_up_short_bps": net_up_short,
                    "net_both_bps": net_both,
                }
            )

    result = pd.DataFrame(rows)
    out_path = LOG_DIR / "profit_space.csv"
    result.to_csv(out_path, index=False)

    # 只看 ret_8h（最强组合）
    print(f"\n--- ret_8h · 分合约展开 ---")
    view_8h = result[result["horizon"] == "ret_8h"].copy()
    view_8h = view_8h.sort_values("net_both_bps")
    show_cols = [
        "contract",
        "n_up",
        "n_dn",
        "mean_up_bps",
        "mean_dn_bps",
        "hit_dn",
        "single_side_cost_bps",
        "net_dn_long_bps",
        "net_up_short_bps",
        "net_both_bps",
    ]
    print(view_8h[show_cols].to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # 聚合摘要（pooled 视角）
    print(f"\n--- ret_8h · 池化汇总 ---")
    all_up = np.concatenate(
        [
            sub[
                (sub["contract"] == c)
                & (sub[METRIC] >= sub.loc[sub["contract"] == c, METRIC].quantile(1 - QUANTILE))
            ]["ret_8h"]
            .dropna()
            .to_numpy()
            for c in sub["contract"].unique()
        ]
    )
    all_dn = np.concatenate(
        [
            sub[
                (sub["contract"] == c)
                & (sub[METRIC] <= sub.loc[sub["contract"] == c, METRIC].quantile(QUANTILE))
            ]["ret_8h"]
            .dropna()
            .to_numpy()
            for c in sub["contract"].unique()
        ]
    )
    pooled_mean_up = float(all_up.mean()) * 1e4
    pooled_mean_dn = float(all_dn.mean()) * 1e4

    avg_cost = float(view_8h["single_side_cost_bps"].mean())
    med_cost = float(view_8h["single_side_cost_bps"].median())
    print(f"跨合约成本 avg={avg_cost:.2f} bps · median={med_cost:.2f} bps · "
          f"range=[{view_8h['single_side_cost_bps'].min():.2f}, "
          f"{view_8h['single_side_cost_bps'].max():.2f}] bps")
    print(f"gross mean_up  = {pooled_mean_up:.2f} bps")
    print(f"gross mean_dn  = {pooled_mean_dn:.2f} bps")
    print(f"gross diff     = {pooled_mean_dn - pooled_mean_up:.2f} bps")
    print(f"---")
    print(f"每合约单边净期望（用该合约自身成本）：")
    print(f"  DN 做多 net median = {view_8h['net_dn_long_bps'].median():.2f} bps · "
          f"mean = {view_8h['net_dn_long_bps'].mean():.2f} bps")
    print(f"  UP 做空 net median = {view_8h['net_up_short_bps'].median():.2f} bps · "
          f"mean = {view_8h['net_up_short_bps'].mean():.2f} bps")
    print(f"  双边   net median = {view_8h['net_both_bps'].median():.2f} bps · "
          f"mean = {view_8h['net_both_bps'].mean():.2f} bps")

    # 正 net 合约数
    n_total = len(view_8h)
    n_dn_pos = int((view_8h["net_dn_long_bps"] > 0).sum())
    n_up_pos = int((view_8h["net_up_short_bps"] > 0).sum())
    n_both_pos = int((view_8h["net_both_bps"] > 0).sum())
    print(f"\n正 net 合约数：")
    print(f"  DN 做多: {n_dn_pos}/{n_total}")
    print(f"  UP 做空: {n_up_pos}/{n_total}")
    print(f"  双边:    {n_both_pos}/{n_total}")

    # 年化粗估（假设每天 1 次机会 · 250 交易日）
    print(f"\n年化粗估（假设每合约每天 1 次机会 · 250 交易日）：")
    print(f"  DN 做多 median 年化 net = {view_8h['net_dn_long_bps'].median() * 250 / 100:.2f} % / 年")
    print(f"  DN 做多 mean   年化 net = {view_8h['net_dn_long_bps'].mean() * 250 / 100:.2f} % / 年")
    print(f"  双边 median 年化 net    = {view_8h['net_both_bps'].median() * 250 / 100:.2f} % / 年")
    print(f"  双边 mean   年化 net    = {view_8h['net_both_bps'].mean() * 250 / 100:.2f} % / 年")

    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
