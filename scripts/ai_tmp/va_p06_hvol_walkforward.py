#!/usr/bin/env python3
"""
va-composite · Phase 6 · `H_vol(tier)` 持仓时长分化 —— walk-forward（时间展开）样本外验证

主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 B0 管线（classifier_v31_timeline.parquet + 5m CSV），复用 va_composite_p1_cap 的
      模拟器 / 压仓 / 指标 / 配对门禁（簇自助 P(μ_true>0)）。

背景（P2 workbench §6 实验四，in-sample 强信号）:
  - 逐阵营最优持仓时长方向明确：前载 S_seg34/L_seg3≈6h、S_seg2≈8h、L_seg12≈10–12h。
  - 组合 in-sample：夏普 2.66→2.94、MaxDD −5.09%→−3.63%，ΔSharpe+0.77，但 P(μ_true>0)=0.734 **未过门禁**，
    且全为同批 312 笔挑峰的乐观上界、跨品种细分样本薄 → 必须走 walk-forward / 分层抽样验证。

本脚本设计（对应 P2 workbench §10 对 P6 的指向）:
  1. **候选集**（spec §0.1）：每 tier 持仓时长 = 基线 × {0.5, 0.6, 0.7, 1.0, 1.3, 1.5}
     （多域基线 8h、空域基线 10h）。选择指标用逐笔 IR（同 P2）。
  2. **walk-forward（时间展开，N_FOLDS 块）**：第 i 折为测试，训练 = 之前所有折；
     在训练折上逐 tier 选最优乘数，应用到测试折。展开累计得到 OOS 交易集。
  3. **候选模型**：
       - T（tier 级）：每 tier 一个乘数。
       - C（合约×tier 级 + 收缩估计）：逐 (tier,contract) 原始乘数向 tier 基准收缩 κ=0.5
         （细格样本薄，防过拟合；cell < MIN_CC 事件直接回落 tier 基准）。
  4. **门禁**（spec §0.2，复用 P1.paired_delta）：候选 vs B0（统一 8/10h）在**同一批 OOS 事件**
     上配对，须同时满足 ΔSharpe ≥ 0.2 **且** P(μ_true>0) ≥ 0.95。
  5. **诚实对照**：同时报 in-sample（全样本选+全样本评，与 P2 同口径思路）与 OOS，
     二者之差即过拟合程度。

运行: uv run python scripts/ai_tmp/va_p06_hvol_walkforward.py
输出: project_data/ai_tmp/p6_hvol/summary.md
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ai_tmp"))
import va_composite_p1_cap as P1  # noqa: E402

OUT_DIR = Path("project_data/ai_tmp/p6_hvol")
OUT_DIR.mkdir(parents=True, exist_ok=True)

LONG_H, SHORT_H = 8, 10
MULTS = [0.5, 0.6, 0.7, 1.0, 1.3, 1.5]
CAP = 4.0          # 新默认（spec §0.1 2026-07-11 修订）
N_FOLDS = 4
MIN_TRAIN = 20     # 每 tier 训练事件下限；不足则回落 1.0
MIN_CC = 15        # 每 (tier,contract) 训练事件下限；不足则回落 tier 基准
SHRINK = 0.5       # 合约级收缩系数 κ


# =====================================================================
# 参数化模拟器（mirror P1.simulate_contract，H 由 resolver(tier,contract) 决定）
# =====================================================================
def simulate_resolve(contract, g, hold_resolver, bars_cache):
    spec = P1.CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    if contract not in bars_cache:
        csv_path = P1.MARKET_DIR / f"{contract}.tqsdk.5m.csv"
        if not csv_path.exists():
            bars_cache[contract] = None
        else:
            b = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
            b["datetime"] = pd.to_datetime(b["datetime"])
            b = b.sort_values("datetime").reset_index(drop=True)
            bars_cache[contract] = b if not b.empty else None
    bars = bars_cache[contract]
    if bars is None:
        return []

    rows = []
    for _, ev in g.iterrows():
        direction = ev["direction"]
        sign = 1 if direction == "long" else -1
        K = P1.K_L_SL if direction == "long" else P1.K_S_SL
        base_h = LONG_H if direction == "long" else SHORT_H
        m = hold_resolver(ev["tier_v40"], contract)
        H = max(1, int(round(base_h * m * 12)))
        entry_price = float(ev["close_t"])
        atr_bps = float(ev["entry_atr_bps"])
        if entry_price <= 0 or atr_bps <= 0:
            continue
        atr_price = entry_price * atr_bps / 10000.0
        stop_price = entry_price - sign * K * atr_price
        stop_dist_frac = K * atr_bps / 10000.0
        notional_frac = P1.RISK_PER_TRADE / stop_dist_frac
        qty_raw = notional_frac * P1.EQUITY_INIT / (entry_price * spec.size)

        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        future = bars.iloc[idx: idx + H]
        if len(future) == 0:
            continue
        exit_price = np.nan
        exit_reason = "TIME"
        exit_bar = future.iloc[-1]["datetime"]
        for _, bar in future.iterrows():
            if sign == 1 and bar["low"] <= stop_price:
                exit_price = stop_price
                exit_reason = "SL"
                exit_bar = bar["datetime"]
                break
            if sign == -1 and bar["high"] >= stop_price:
                exit_price = stop_price
                exit_reason = "SL"
                exit_bar = bar["datetime"]
                break
        if np.isnan(exit_price):
            exit_price = float(future.iloc[-1]["close"])
            exit_bar = future.iloc[-1]["datetime"]

        ce = P1.cost_oneway_bps(spec, entry_price, qty_raw)
        cx = P1.cost_oneway_bps(spec, exit_price, qty_raw)
        pnl = sign * (exit_price - entry_price) / entry_price * 10000.0 - ce - cx
        sym = (P1.extract_contract_prefix(contract) or "").lower()
        rows.append({
            "contract": contract, "symbol": sym,
            "symbol_type": P1.SYMBOL_TYPE.get(sym, "C"),
            "entry_bar": ev["event_time"], "exit_bar": exit_bar,
            "direction": int(sign), "tier": ev["tier_v40"],
            "entry_price": entry_price, "exit_price": exit_price,
            "exit_reason": exit_reason, "entry_atr_bps": atr_bps,
            "qty_raw": qty_raw, "qty_actual": qty_raw,
            "pnl_gross_bps": sign * (exit_price - entry_price) / entry_price * 10000.0,
            "cost_entry_bps": ce, "cost_exit_bps": cx,
            "pnl_net_bps": pnl,
            "pnl_net_ccy": pnl / 10000.0 * (qty_raw * entry_price * spec.size),
            "_notional_frac": notional_frac,
            "_entry_date": ev["event_time"].date(),
            "_exit_date": pd.Timestamp(exit_bar).date(),
        })
    return rows


def sim_tier(train_sub, m, bars_cache):
    """对单 tier 在乘数 m 下（其余 tier 回落 1.0）的逐笔结果。"""
    rows = []
    for c, g in train_sub.groupby("contract"):
        res = lambda t, cc, _m=m: _m if t == train_sub["tier_v40"].iloc[0] else 1.0
        rows.extend(simulate_resolve(c, g, res, bars_cache))
    return rows


def select_tier(train, bars_cache):
    best = {}
    for tier, sub in train.groupby("tier_v40"):
        if len(sub) < MIN_TRAIN:
            best[tier] = 1.0
            continue
        bi, bm = -9.0, 1.0
        for m in MULTS:
            rows = sim_tier(sub, m, bars_cache)
            ir = P1.per_trade_ir(pd.DataFrame(rows)) if rows else -9.0
            if ir > bi:
                bi, bm = ir, m
        best[tier] = bm
    return best


def select_contract(train, tier_best, bars_cache):
    cc = {}
    for (tier, contract), sub in train.groupby(["tier_v40", "contract"]):
        base = tier_best.get(tier, 1.0)
        if len(sub) < MIN_CC:
            cc[(tier, contract)] = base
            continue
        bi, bm = -9.0, base
        for m in MULTS:
            rows = []
            for c, g in sub.groupby("contract"):
                rows.extend(simulate_resolve(c, g, lambda t, cc_: m, bars_cache))
            ir = P1.per_trade_ir(pd.DataFrame(rows)) if rows else -9.0
            if ir > bi:
                bi, bm = ir, m
        cc[(tier, contract)] = base + SHRINK * (bm - base)
    return cc


def tier_resolver(tier_best):
    return lambda t, c: tier_best.get(t, 1.0)


def cc_resolver(cc_map, tier_best):
    return lambda t, c: cc_map.get((t, c), tier_best.get(t, 1.0))


def eval_model(trades, ad):
    t = P1.compress(trades, CAP)
    t = P1.assign_equity(t)
    m = P1.base_metrics(t, active_days=ad)
    m["monthly_win"] = P1.monthly_win_rate(t)
    m["ir"] = P1.per_trade_ir(t)
    m["nu"], m["p"] = P1.nu_implied(t)
    return t, m


def metrics_row(name, m):
    return (f"| {name} | {m['ann_ret']*100:6.2f}% | {m['sharpe']:5.2f} | "
            f"{m['max_dd']*100:6.2f}% | {m['monthly_win']*100:5.1f}% | "
            f"{m['ir']:5.3f} | {m['nu']:+.3f} | {m['p']:.3f} |")


def main():
    print("=" * 78)
    print("va-composite · Phase 6 · H_vol(tier) walk-forward 验证  "
          f"[Cap={CAP} · {N_FOLDS}折时间展开 · 收缩κ={SHRINK}]")
    print("=" * 78)

    print("[1/5] 加载 timeline + 事件（冻结 B0 管线）...")
    tl_full = pd.read_parquet(P1.TIMELINE_PATH)
    ad = P1.active_day_set(tl_full, "signed_skew_rank_roll")
    events = P1.load_events().sort_values("event_time").reset_index(drop=True)
    print(f"      事件数 {len(events)} | 合约 {events['contract'].nunique()} | "
          f"多 {(events['direction']=='long').sum()} / 空 {(events['direction']=='short').sum()}")
    print(f"      时间范围 {events['event_time'].min()} → {events['event_time'].max()}")

    bars_cache = {}

    # ---- in-sample（全样本选+全样本评，对照 P2 思路） ----
    print("\n[2/5] in-sample 选择 + 评估（全样本，乐观上界）...")
    tb_full = select_tier(events, bars_cache)
    cc_full = select_contract(events, tb_full, bars_cache)
    ins_rows = {"T": [], "C": [], "B0": []}
    for c, g in events.groupby("contract"):
        ins_rows["T"].extend(simulate_resolve(c, g, tier_resolver(tb_full), bars_cache))
        ins_rows["C"].extend(simulate_resolve(c, g, cc_resolver(cc_full, tb_full), bars_cache))
        ins_rows["B0"].extend(simulate_resolve(c, g, lambda t, cc: 1.0, bars_cache))
    ins_trades = {k: pd.DataFrame(v) for k, v in ins_rows.items()}
    ins_eval = {k: eval_model(df, ad) for k, df in ins_trades.items()}
    ins_paired_T = P1.paired_delta(ins_trades["B0"], ins_trades["T"])
    ins_paired_C = P1.paired_delta(ins_trades["B0"], ins_trades["C"])
    print("      T  in-sample : " + metrics_row("H_vol(T)", ins_eval["T"][1]).strip())
    print("      C  in-sample : " + metrics_row("H_vol(C)", ins_eval["C"][1]).strip())
    print("      B0 in-sample : " + metrics_row("B0(uniform)", ins_eval["B0"][1]).strip())
    print(f"      paired T vs B0: ΔSh={ins_paired_T['dsharpe']:+.2f} P(μ>0)={ins_paired_T['p_nu_pos']:.3f}")
    print(f"      paired C vs B0: ΔSh={ins_paired_C['dsharpe']:+.2f} P(μ>0)={ins_paired_C['p_nu_pos']:.3f}")

    # ---- walk-forward OOS ----
    print(f"\n[3/5] walk-forward（{N_FOLDS}折时间展开）...")
    n = len(events)
    edges = [int(n * i / N_FOLDS) for i in range(N_FOLDS + 1)]
    oos_rows = {"T": [], "C": [], "B0": []}
    fold_log = []
    for i in range(1, N_FOLDS):
        train = events.iloc[edges[0]:edges[i]]
        test = events.iloc[edges[i]:edges[i + 1]]
        tb = select_tier(train, bars_cache)
        cc = select_contract(train, tb, bars_cache)
        for c, g in test.groupby("contract"):
            oos_rows["T"].extend(simulate_resolve(c, g, tier_resolver(tb), bars_cache))
            oos_rows["C"].extend(simulate_resolve(c, g, cc_resolver(cc, tb), bars_cache))
            oos_rows["B0"].extend(simulate_resolve(c, g, lambda t, cc: 1.0, bars_cache))
        fold_log.append((i, tb, len(test)))
        print(f"      折{i}: 训练 {len(train)} / 测试 {len(test)} 笔 | "
              f"选乘 T={ {k: round(v,2) for k,v in tb.items()} }")

    oos_trades = {k: pd.DataFrame(v) for k, v in oos_rows.items()}
    oos_eval = {k: eval_model(df, ad) for k, df in oos_trades.items()}
    oos_paired_T = P1.paired_delta(oos_trades["B0"], oos_trades["T"])
    oos_paired_C = P1.paired_delta(oos_trades["B0"], oos_trades["C"])
    print("      T  OOS : " + metrics_row("H_vol(T)", oos_eval["T"][1]).strip())
    print("      C  OOS : " + metrics_row("H_vol(C)", oos_eval["C"][1]).strip())
    print("      B0 OOS : " + metrics_row("B0(uniform)", oos_eval["B0"][1]).strip())
    print(f"      paired T vs B0: ΔSh={oos_paired_T['dsharpe']:+.2f} P(μ>0)={oos_paired_T['p_nu_pos']:.3f}")
    print(f"      paired C vs B0: ΔSh={oos_paired_C['dsharpe']:+.2f} P(μ>0)={oos_paired_C['p_nu_pos']:.3f}")

    # ---- 写出明细 ----
    print("\n[4/5] 写出交易明细 parquet...")
    for k, df in oos_trades.items():
        df.to_parquet(OUT_DIR / f"oos_{k}.trades.parquet", index=False)
    for k, df in ins_trades.items():
        df.to_parquet(OUT_DIR / f"ins_{k}.trades.parquet", index=False)

    # ---- 门禁判定 + 汇总 ----
    print("[5/5] 门禁判定 + 写 summary...")
    gate_T = (oos_paired_T["dsharpe"] >= 0.2) and (oos_paired_T["p_nu_pos"] >= 0.95)
    gate_C = (oos_paired_C["dsharpe"] >= 0.2) and (oos_paired_C["p_nu_pos"] >= 0.95)

    def mrow(name, m):
        return (f"| {name} | {m['ann_ret']*100:6.2f}% | {m['sharpe']:5.2f} | "
                f"{m['max_dd']*100:6.2f}% | {m['monthly_win']*100:5.1f}% | {m['ir']:5.3f} | "
                f"{m['nu']:+.3f} | {m['p']:.3f} |")

    L = []
    L.append("# va-asymmetry-composite · Phase 6 · `H_vol(tier)` walk-forward 验证报告")
    L.append("")
    L.append(f"> 日期 2026-07-11 · 引擎复用 P1 冻结模拟器 · Cap={CAP}（新默认）· "
             f"{N_FOLDS}折时间展开 · 收缩κ={SHRINK} · 候选乘数 {MULTS}")
    L.append("> 门禁（spec §0.2）：候选 vs B0 配对须 **ΔSharpe≥0.2 且 P(μ_true>0)≥0.95** 同时成立方升格。")
    L.append("")
    L.append("## 1. 主指标（Cap=%.1f，新·可交易日口径）" % CAP)
    L.append("")
    L.append("| 模型 | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) |")
    L.append("|:---|---:|---:|---:|---:|---:|---:|---:|")
    L.append(mrow("B0(uniform) · in-sample", ins_eval["B0"][1]))
    L.append(mrow("H_vol(T) · in-sample", ins_eval["T"][1]))
    L.append(mrow("H_vol(C) · in-sample", ins_eval["C"][1]))
    L.append(mrow("B0(uniform) · OOS", oos_eval["B0"][1]))
    L.append(mrow("H_vol(T) · OOS", oos_eval["T"][1]))
    L.append(mrow("H_vol(C) · OOS", oos_eval["C"][1]))
    L.append("")
    L.append("## 2. 配对增量（候选 vs B0，簇自助 P(μ_true>0)）")
    L.append("")
    L.append("| 模型 | 样本 | ΔSharpe | μ_true | P(μ_true>0) | 门禁 |")
    L.append("|:---|:---|---:|---:|---:|:---:|")
    L.append(f"| H_vol(T) | in-sample | {ins_paired_T['dsharpe']:+.2f} | "
             f"{ins_paired_T['nu_true']*100:+.3f}% | {ins_paired_T['p_nu_pos']:.3f} | "
             f"{'过 ✅' if (ins_paired_T['dsharpe']>=0.2 and ins_paired_T['p_nu_pos']>=0.95) else '未过 ❌'} |")
    L.append(f"| H_vol(C) | in-sample | {ins_paired_C['dsharpe']:+.2f} | "
             f"{ins_paired_C['nu_true']*100:+.3f}% | {ins_paired_C['p_nu_pos']:.3f} | "
             f"{'过 ✅' if (ins_paired_C['dsharpe']>=0.2 and ins_paired_C['p_nu_pos']>=0.95) else '未过 ❌'} |")
    L.append(f"| H_vol(T) | **OOS** | {oos_paired_T['dsharpe']:+.2f} | "
             f"{oos_paired_T['nu_true']*100:+.3f}% | {oos_paired_T['p_nu_pos']:.3f} | "
             f"{'过 ✅' if gate_T else '未过 ❌'} |")
    L.append(f"| H_vol(C) | **OOS** | {oos_paired_C['dsharpe']:+.2f} | "
             f"{oos_paired_C['nu_true']*100:+.3f}% | {oos_paired_C['p_nu_pos']:.3f} | "
             f"{'过 ✅' if gate_C else '未过 ❌'} |")
    L.append("")
    L.append("## 3. 各折所选乘数（训练折内选，测试折外评）")
    L.append("")
    L.append("| 折 | 训练笔数 | 测试笔数 | 选乘 T（tier→乘数） |")
    L.append("|:---:|---:|---:|:---|")
    for i, tb, ntest in fold_log:
        L.append(f"| {i} | {edges[i]-edges[0]} | {ntest} | "
                 f"{ {k: round(v,2) for k,v in tb.items()} } |")
    L.append("")
    L.append("## 4. 结论与处置")
    L.append("")
    L.append(f"- **in-sample 信号**（全样本挑峰，乐观上界）：H_vol(T) ΔSh={ins_paired_T['dsharpe']:+.2f}、"
             f"P={ins_paired_T['p_nu_pos']:.3f}；H_vol(C) ΔSh={ins_paired_C['dsharpe']:+.2f}、"
             f"P={ins_paired_C['p_nu_pos']:.3f}。与 P2 workbench §6 方向一致（前载 tier 缩短）。")
    L.append(f"- **OOS 信号**（walk-forward 真实样本外）：H_vol(T) ΔSh={oos_paired_T['dsharpe']:+.2f}、"
             f"P={oos_paired_T['p_nu_pos']:.3f} → **{'过门 ✅ 升格采用' if gate_T else '未过门 ❌ 仍候选'}**；"
             f"H_vol(C) ΔSh={oos_paired_C['dsharpe']:+.2f}、P={oos_paired_C['p_nu_pos']:.3f} → "
             f"**{'过门 ✅' if gate_C else '未过门 ❌'}**。")
    L.append(f"- in-sample→OOS 的 ΔSharpe / P 衰减幅度即过拟合程度；若 OOS 显著低于 in-sample，")
    L.append("  说明 P2 的 +0.77 含挑峰乐观，须谨慎。")
    if gate_T:
        L.append("- **采用建议**：H_vol(tier) OOS 过门，将前载阵营（S_seg34/L_seg3）持仓缩至 6h≈0.6× 作为")
        L.append("  低风险优先改动回灌 spec §0.1/§3.3；其余 tier 乘数按 OOS 选中值锁定。")
    else:
        L.append("- **采用建议**：OOS 未过门，维持 B0 统一 8/10h；H_vol(tier) 仍为候选轴，")
        L.append("  须经更多样本 / 更稳的 walk-forward（或扩大时间跨度）再评估，不可直接继承 in-sample 结论。")
    L.append("")
    L.append("> 注：合约级 C 因 (tier,合约) 细格样本薄（多 <MIN_CC），收缩后多数回落 tier 基准，")
    L.append("> 故 C≈T 属预期；仅当收缩后能稳定过门，合约级细化才有意义。")
    L.append("")

    (OUT_DIR / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print(f"      写出: {OUT_DIR / 'summary.md'}")
    print("\nPhase 6 终判:")
    print(f"  H_vol(tier) OOS 门禁: {'PASS ✅' if gate_T else 'FAIL ❌'}")
    print(f"  H_vol(contract) OOS 门禁: {'PASS ✅' if gate_C else 'FAIL ❌'}")


if __name__ == "__main__":
    main()
