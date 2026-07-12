#!/usr/bin/env python3
"""
va-composite · Phase 1 · 主杠杆 Cap（名义暴露）扫描

位置: scripts/ai_tmp/va_composite_p1_cap.py
主题: docs/research/themes/va-asymmetry-composite/
依赖: 冻结 B0 管线（classifier_v31_timeline.parquet + 5m CSV），旧口径不动（走 A 方案）

核心杠杆逻辑（spec §7.2 + experiment-plan §0.2）:
  - Cap = MAX_NOTIONAL（总名义上限，占权益比例）。B0=1.0；P_nominal=2.0。
  - compress(): scale = (Cap / daily_notional_frac).clip(upper=1.0)
    => Cap>1.0 只放松压缩（让日均 653% 被砍的交易日恢复满仓），不放大单笔。
  - 模拟只跑一次（Cap 无关），之后对每个 Cap 复用压仓+指标+配对检验，效率高。

配对增量评估（experiment-plan §0.1）:
  - 候选相对 B0 在同一批事件上配对，构造每日增量序列 d_t = pnl_cap(t) − pnl_B0(t)。
  - 采用门限（spec §0.2）:
      ΔSharpe(d) ≥ 0.2  AND  P(μ_true(d) > 0) ≥ 0.95
    两条件同时满足方采用；否则记为「候选未过门」。
  - 归因（spec §9）: μ_g = mean(d_ret)*252, σ_g² = var(d_ret)*252,
    μ_true = μ_g − σ_g²/2；P(μ_true>0) 用 (contract, exit_date) 簇自助法。

运行: uv run python scripts/ai_tmp/va_composite_p1_cap.py
输出:
  - project_data/ai_tmp/p1_cap/cap{K}.trades.parquet  每个 Cap 的交易明细
  - project_data/ai_tmp/p1_cap/summary.md             配对增量报告 + Gate 判定
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "workspace"))
from common.contract_specs import CONTRACT_SPECS  # noqa: E402
from common.symbol_utils import extract_contract_prefix  # noqa: E402

TIMELINE_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet")
MARKET_DIR = Path("project_data/market_data/csv")
OUT_DIR = Path("project_data/ai_tmp/p1_cap")
OUT_DIR.mkdir(parents=True, exist_ok=True)
EQUITY_INIT = 1_000_000.0  # 简化权益模型（§10 阶段0-2 允许）
ANNUAL_FACTOR = 252  # 年化因子: 一年 252 个交易日 (标准口径; 与 Sharpe 的 sqrt(252) 一致)

CAPS = [1.0, 1.2, 2.0, 4.0, 5.0]  # B0 + 候选（spec §0.2）；5.0 为用户指定试跑档


# =====================================================================
# CONTRACT LAYER（src: strategy-math-spec.md v0.1）—— 与冻结 B0 完全一致
# =====================================================================
A_TIER_RAW = {
    "UP2_atrLow_up_stable", "UP3_atrMid_up_stable",
    "UP1_atrHigh_up_trans",
    "DN1_atrHigh_down_stable", "DN1_atrHigh_down_trans",
    "DN2_atrHigh_down_stable", "DN2_atrHigh_down_trans",
    "DN3_atrHigh_down_stable", "DN3_atrHigh_down_trans",
    "DN4_atrHigh_down_stable", "DN4_atrHigh_down_trans",
    "DN2_atrMid_down_stable", "DN2_atrMid_down_trans",
}
TIER_TO_V40 = {
    "UP2_atrLow_up_stable": "L_seg3_lowmid_up", "UP3_atrMid_up_stable": "L_seg3_lowmid_up",
    "UP1_atrHigh_up_trans": "L_seg12_high_up",
    "DN1_atrHigh_down_stable": "S_seg12_high_dn", "DN1_atrHigh_down_trans": "S_seg12_high_dn",
    "DN2_atrHigh_down_stable": "S_seg12_high_dn", "DN2_atrHigh_down_trans": "S_seg12_high_dn",
    "DN3_atrHigh_down_stable": "S_seg34_high_dn", "DN3_atrHigh_down_trans": "S_seg34_high_dn",
    "DN4_atrHigh_down_stable": "S_seg34_high_dn", "DN4_atrHigh_down_trans": "S_seg34_high_dn",
    "DN2_atrMid_down_stable": "S_seg2_mid_dn", "DN2_atrMid_down_trans": "S_seg2_mid_dn",
}
SYMBOL_TYPE: dict[str, str] = {}
for p in ["if", "ih", "ic", "im", "t", "tf", "ts", "au", "ag"]:
    SYMBOL_TYPE[p] = "A"
for p in ["rb", "hc", "i", "j", "jm", "ta", "ma", "pp", "l", "v", "eb", "eg", "sc", "fu", "bu"]:
    SYMBOL_TYPE[p] = "B"
for p in ["cu", "al", "zn", "ni", "sn", "pb", "m", "y", "p", "c", "cs", "cf", "sr", "oi", "rm", "fg"]:
    SYMBOL_TYPE[p] = "C"

RISK_PER_TRADE = 0.02
DEDUP_HOURS = 8
K_L_SL, H_L = 1.0, 8
K_S_SL, H_S = 2.5, 10


def cost_oneway_bps(spec, price: float, lots: int = 1) -> float:
    ccy = spec.total_commission(price=price, lots=1) + spec.slippage(lots=1)
    return ccy / (price * spec.size) * 10000.0


# =====================================================================
# 数据加载 + 信号构建
# =====================================================================
def load_events() -> pd.DataFrame:
    tl = pd.read_parquet(TIMELINE_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    a = tl[tl["tier"].isin(A_TIER_RAW)].copy()
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["tier_v40"] = a["tier"].map(TIER_TO_V40)
    a = a.dropna(subset=["tier_v40"])
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = a.sort_values("event_time")
    a = a.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev_time = a.groupby("contract")["event_time"].shift(1)
    a = a[(prev_time.isna()) | ((a["event_time"] - prev_time) > pd.Timedelta(hours=DEDUP_HOURS))]
    return a.reset_index(drop=True)


def simulate_contract(contract: str, g: pd.DataFrame) -> list[dict]:
    spec = CONTRACT_SPECS.get_symbol(contract)
    if spec is None:
        return []
    csv_path = MARKET_DIR / f"{contract}.tqsdk.5m.csv"
    if not csv_path.exists():
        return []
    bars = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    bars = bars.sort_values("datetime").reset_index(drop=True)
    if bars.empty:
        return []

    rows: list[dict] = []
    for _, ev in g.iterrows():
        direction = ev["direction"]
        sign = 1 if direction == "long" else -1
        K = K_L_SL if direction == "long" else K_S_SL
        H = H_L if direction == "long" else H_S
        entry_price = float(ev["close_t"])
        atr_bps = float(ev["entry_atr_bps"])
        if entry_price <= 0 or atr_bps <= 0:
            continue
        atr_price = entry_price * atr_bps / 10000.0
        stop_price = entry_price - sign * K * atr_price
        stop_dist_frac = K * atr_bps / 10000.0
        notional_frac = RISK_PER_TRADE / stop_dist_frac
        qty_raw = notional_frac * EQUITY_INIT / (entry_price * spec.size)

        idx = int(bars["datetime"].searchsorted(ev["event_time"]))
        future = bars.iloc[idx: idx + H * 12]
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

        cost_entry_bps = cost_oneway_bps(spec, entry_price, qty_raw)
        cost_exit_bps = cost_oneway_bps(spec, exit_price, qty_raw)
        gross_ret = sign * (exit_price - entry_price) / entry_price
        pnl_gross_bps = gross_ret * 10000.0
        pnl_net_bps = pnl_gross_bps - cost_entry_bps - cost_exit_bps
        notional_ccy = qty_raw * entry_price * spec.size
        pnl_net_ccy = pnl_net_bps / 10000.0 * notional_ccy

        sym = (extract_contract_prefix(contract) or "").lower()
        rows.append({
            "contract": contract,
            "symbol": sym,
            "symbol_type": SYMBOL_TYPE.get(sym, "C"),
            "entry_bar": ev["event_time"],
            "exit_bar": exit_bar,
            "direction": int(sign),
            "tier": ev["tier"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "entry_atr_bps": atr_bps,
            "qty_raw": qty_raw,
            "qty_actual": qty_raw,
            "pnl_gross_bps": pnl_gross_bps,
            "cost_entry_bps": cost_entry_bps,
            "cost_exit_bps": cost_exit_bps,
            "pnl_net_bps": pnl_net_bps,
            "pnl_net_ccy": pnl_net_ccy,
            "_notional_frac": notional_frac,
            "_entry_date": ev["event_time"].date(),
            "_exit_date": pd.Timestamp(exit_bar).date(),
        })
    return rows


# =====================================================================
# 风控压仓（§7.2）—— 参数化 MAX_NOTIONAL（Cap）
# =====================================================================
def compress(trades: pd.DataFrame, max_notional: float) -> pd.DataFrame:
    daily = trades.groupby("_entry_date")["_notional_frac"].sum()
    scale = (max_notional / daily).clip(upper=1.0)
    scale_map = scale.to_dict()
    t = trades.copy()
    t["scale"] = t["_entry_date"].map(scale_map).fillna(1.0)
    t["qty_actual"] = t["qty_raw"] * t["scale"]
    t["pnl_net_ccy"] = t["pnl_net_ccy"] * t["scale"]
    return t


def assign_equity(trades: pd.DataFrame) -> pd.DataFrame:
    t = trades.sort_values("exit_bar").reset_index(drop=True)
    eq = EQUITY_INIT
    befs, afts = [], []
    for pnl in t["pnl_net_ccy"]:
        befs.append(eq)
        eq = eq + pnl
        afts.append(eq)
    t["equity_before"] = befs
    t["equity_after"] = afts
    return t


# =====================================================================
# 指标（§9 归因）
# =====================================================================
def active_day_set(df: pd.DataFrame, sk_col: str = "signed_skew_rank_roll") -> set:
    """逐合约: 仅取 skew 秩'拿到值'(非NaN)的那一天(交易日, 剔周末), 跨合约取并集。

    用作年化分母 —— 只计入 'skew 拿到值、可正式交易' 的交易日
    (即逐合约有有效 skew 秩的那一天; 不含预热空窗与周末)。
    df 需含 contract / event_date(可比较) / sk_col。
    """
    days: set = set()
    for _, g in df.groupby("contract"):
        v = g[g[sk_col].notna()]
        for d in v["event_date"]:
            ts = pd.Timestamp(d)
            if ts.weekday() < 5:  # 剔周末
                days.add(ts.date())
    return days


def base_metrics(trades: pd.DataFrame, active_days=None, df=None,
                 sk_col: str = "signed_skew_rank_roll") -> dict:
    """回测指标。

    active_days: 提供(集合/列表)则用 '可交易日' 口径年化(剔周末+预热空窗);
                 否则若给 df 则自动从 df[sk_col] 推导; 都没有则回退旧日历日口径。
    """
    t = trades.copy()
    t["day"] = t["_exit_date"]
    daily_pnl = t.groupby("day")["pnl_net_ccy"].sum()
    ret = daily_pnl / EQUITY_INIT
    if len(ret) == 0:
        return {"ann_ret": 0.0, "ann_std": 0.0, "sharpe": 0.0, "max_dd": 0.0,
                "n_active_days": 0}
    if active_days is None and df is not None:
        active_days = active_day_set(df, sk_col)
    if active_days:
        idx = sorted(active_days)
        ret = ret.reindex(idx, fill_value=0.0)
    else:
        all_dates = pd.date_range(ret.index.min(), ret.index.max(), freq="D")
        ret = ret.reindex(all_dates.date, fill_value=0.0)
    ann = ret.mean() * ANNUAL_FACTOR
    std = ret.std() * np.sqrt(ANNUAL_FACTOR)
    sharpe = ann / std if std > 0 else 0.0
    cum = ret.cumsum()
    dd = (cum - cum.cummax()).min()
    return {"ann_ret": ann, "ann_std": std, "sharpe": sharpe, "max_dd": dd,
            "n_active_days": len(active_days) if active_days else len(ret)}


def monthly_win_rate(trades: pd.DataFrame) -> float:
    t = trades.copy()
    t["month"] = pd.to_datetime(t["_exit_date"]).dt.to_period("M")
    mret = t.groupby("month")["pnl_net_ccy"].sum()
    return float((mret > 0).mean()) if len(mret) else 0.0


def per_trade_ir(trades: pd.DataFrame) -> float:
    s = trades["pnl_net_bps"].std()
    return float(trades["pnl_net_bps"].mean() / s) if s > 0 else 0.0


def nu_implied(trades: pd.DataFrame) -> tuple[float, float]:
    g = trades["pnl_gross_bps"].values / 10000.0
    mu = g.mean()
    var = g.var()
    nu_frac = mu - var / 2.0
    grp = trades.groupby(["contract", "_exit_date"])["pnl_gross_bps"]
    sizes = grp.size().values.astype(float)
    sums = (grp.sum().values) / 10000.0
    sumsq = (grp.apply(lambda x: (x ** 2).sum()).values) / 10000.0 ** 2
    N = sizes.sum()
    k = len(sizes)
    rng = np.random.default_rng(42)
    nu = np.empty(500)
    for i in range(500):
        sel = rng.integers(0, k, size=k)
        S = sums[sel].sum()
        SS = sumsq[sel].sum()
        mean = S / N
        var_c = SS / N - mean * mean
        nu[i] = mean - var_c / 2.0
    return float(nu_frac * 10000.0), float((nu > 0).mean())


# =====================================================================
# 配对增量检验（§0.1 / §9）—— 候选 vs B0(Cap=1.0)
# =====================================================================
def paired_delta(b0: pd.DataFrame, cap: pd.DataFrame) -> dict:
    def daily_pnl(df):
        t = df.copy()
        t["day"] = t["_exit_date"]
        return t.groupby("day")["pnl_net_ccy"].sum() / EQUITY_INIT
    d0 = daily_pnl(b0)
    d1 = daily_pnl(cap)
    idx = d0.index.union(d1.index)
    d0 = d0.reindex(idx, fill_value=0.0)
    d1 = d1.reindex(idx, fill_value=0.0)
    delta = d1 - d0
    dsharpe = delta.mean() * 252 / (delta.std() * np.sqrt(252)) if delta.std() > 0 else 0.0

    g0 = b0.groupby(["contract", "_exit_date"])["pnl_net_ccy"].sum()
    g1 = cap.groupby(["contract", "_exit_date"])["pnl_net_ccy"].sum()
    gi = g0.index.union(g1.index)
    g0 = g0.reindex(gi, fill_value=0.0)
    g1 = g1.reindex(gi, fill_value=0.0)
    dcl = (g1 - g0) / EQUITY_INIT
    mu = dcl.mean() * 252
    var = dcl.var() * 252
    nu_true = mu - var / 2.0

    arr = dcl.values
    k = len(arr)
    rng = np.random.default_rng(7)
    nus = np.empty(1000)
    for i in range(1000):
        sel = rng.integers(0, k, size=k)
        s = arr[sel].sum()
        ss = (arr[sel] ** 2).sum()
        mean = s / k
        varc = ss / k - mean * mean
        nus[i] = mean * 252 - varc * 252 / 2.0
    p_pos = float((nus > 0).mean())
    return {"dsharpe": dsharpe, "mu_g": mu, "var_g": var, "nu_true": nu_true, "p_nu_pos": p_pos}


# =====================================================================
# 主流程
# =====================================================================
def main() -> None:
    print("=" * 70)
    print("va-composite · Phase 1 · Cap（名义暴露）扫描  [基线=冻结 B0 · 新·可交易日口径=只用 skew 拿到值]")
    print("=" * 70)

    print("[1/4] 加载 timeline + 构建信号（§1.2/§8.1）...")
    tl_full = pd.read_parquet(TIMELINE_PATH)
    ad = active_day_set(tl_full, "signed_skew_rank_roll")
    events = load_events()
    print(f"      A 级去重后事件: {len(events)} | 合约: {events['contract'].nunique()} | "
          f"多:{(events['direction']=='long').sum()} 空:{(events['direction']=='short').sum()}")

    print("[2/4] 逐合约 5m 精确模拟（§3.1-§3.3，仅一次，Cap 无关）...")
    all_rows: list[dict] = []
    for contract, g in events.groupby("contract"):
        all_rows.extend(simulate_contract(contract, g))
    raw = pd.DataFrame(all_rows)
    print(f"      模拟交易数: {len(raw)} | SL:{(raw['exit_reason']=='SL').sum()} "
          f"TIME:{(raw['exit_reason']=='TIME').sum()}")

    print("[3/4] 逐 Cap 压仓 + 指标 + 配对增量...")
    trades_by_cap: dict[float, pd.DataFrame] = {}
    metrics_by_cap: dict[float, dict] = {}
    for cap in CAPS:
        t = compress(raw, cap)
        t = assign_equity(t)
        trades_by_cap[cap] = t
        m = base_metrics(t, active_days=ad)
        m["monthly_win"] = monthly_win_rate(t)
        m["ir"] = per_trade_ir(t)
        m["nu_implied"], m["p_nu_pos"] = nu_implied(t)
        # 压仓诊断
        avg_notional = float(t.groupby("_entry_date")["_notional_frac"].sum().mean())
        compressed_days = int((t.groupby("_entry_date")["scale"].mean() < 1.0).sum())
        m["avg_notional_pre"] = avg_notional
        m["compressed_days"] = compressed_days
        metrics_by_cap[cap] = m
        # 写出明细
        out_cols = ["contract", "symbol", "symbol_type", "entry_bar", "exit_bar", "direction", "tier",
                    "entry_price", "exit_price", "exit_reason", "entry_atr_bps", "qty_raw", "qty_actual",
                    "pnl_gross_bps", "cost_entry_bps", "cost_exit_bps",
                    "pnl_net_bps", "pnl_net_ccy", "equity_before", "equity_after"]
        t[out_cols].to_parquet(OUT_DIR / f"cap{cap}.trades.parquet", index=False)
        print(f"      Cap={cap:>4}: 年化 {m['ann_ret']*100:6.2f}%  夏普 {m['sharpe']:6.2f}  "
              f"MaxDD {m['max_dd']*100:6.2f}%  压仓天数 {compressed_days}  平均名义(前) {avg_notional*100:5.1f}%")

    print("[4/4] 配对增量评估（候选 vs B0） + 写 summary...")
    b0 = trades_by_cap[1.0]
    rows = []
    for cap in CAPS[1:]:
        d = paired_delta(b0, trades_by_cap[cap])
        adopted = (d["dsharpe"] >= 0.2) and (d["p_nu_pos"] >= 0.95)
        rows.append((cap, d, adopted))
        print(f"      Cap={cap:>4}: ΔSharpe={d['dsharpe']:+.2f}  μ_true={d['nu_true']*100:+.3f}%  "
              f"P(μ_true>0)={d['p_nu_pos']:.3f}  => {'采用 ✅' if adopted else '未过门 ❌'}")

    _write_summary(metrics_by_cap, rows)

    # 终判
    best = None
    for cap, d, adopted in rows:
        if adopted and (best is None or metrics_by_cap[cap]["sharpe"] > metrics_by_cap[best]["sharpe"]):
            best = cap
    print()
    if best is not None:
        print(f"Phase 1 结论: 采用 Cap={best}（最高采用档夏普 {metrics_by_cap[best]['sharpe']:.2f}）")
    else:
        print("Phase 1 结论: 无 Cap 候选过门 —— 按 §3 回溯协议，回到 P0.4 复核信号边际，非『Cap 没调对』")


def _write_summary(metrics_by_cap, paired_rows) -> None:
    lines = []
    lines.append("# va-asymmetry-composite · Phase 1 · Cap（名义暴露）配对增量报告")
    lines.append("")
    lines.append("> 基线: 冻结 B0（旧口径 timeline，Cap=1.0）。本 Phase 不重跑上游管线修正（走 A 方案）。")
    lines.append("> 口径: 模拟一次，逐 Cap 复用压仓+指标；配对增量按 §0.1 同一批事件。")
    lines.append("")
    lines.append("## 1. 各 Cap 主指标")
    lines.append("")
    lines.append("| Cap | 年化 | 净夏普 | MaxDD | 月度胜率 | 单笔IR | ν_implied | P(ν>0) | 压仓天数 | 日均名义(前) |")
    lines.append("|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for cap in CAPS:
        m = metrics_by_cap[cap]
        lines.append(f"| {cap} | {m['ann_ret']*100:.2f}% | {m['sharpe']:.2f} | {m['max_dd']*100:.2f}% | "
                     f"{m['monthly_win']*100:.1f}% | {m['ir']:.3f} | {m['nu_implied']:.3f} | "
                     f"{m['p_nu_pos']:.3f} | {m['compressed_days']} | {m['avg_notional_pre']*100:.1f}% |")
    lines.append("")
    lines.append("## 2. 配对增量（候选 vs B0，§0.1）")
    lines.append("")
    lines.append("门限: ΔSharpe ≥ 0.2 **且** P(μ_true>0) ≥ 0.95，二者同时满足方采用。")
    lines.append("")
    lines.append("| Cap | ΔSharpe | μ_g(年化) | σ_g²(年化) | μ_true | P(μ_true>0) | 判定 |")
    lines.append("|:---:|---:|---:|---:|---:|---:|:---:|")
    for cap, d, adopted in paired_rows:
        lines.append(f"| {cap} | {d['dsharpe']:+.2f} | {d['mu_g']*100:+.2f}% | {d['var_g']*100:.2f}% | "
                     f"{d['nu_true']*100:+.3f}% | {d['p_nu_pos']:.3f} | {'采用 ✅' if adopted else '未过门 ❌'} |")
    lines.append("")
    lines.append("## 3. 解读与回溯提示（§3）")
    lines.append("")
    adopt = [cap for cap, d, a in paired_rows if a]
    if adopt:
        best = max(adopt, key=lambda c: metrics_by_cap[c]["sharpe"])
        lines.append(f"- 过门档: {adopt}。建议采用最高夏普档 **Cap={best}**（夏普 {metrics_by_cap[best]['sharpe']:.2f}）。")
        lines.append("- Cap 提升仅放松压缩、放大有效信号暴露，不改变单笔 edge；若夏普随 Cap 单调升，说明瓶颈确在名义上限。")
    else:
        lines.append("- **无候选过门**：呼应 §3「Cap 放大暴露不增夏普 → 信号可能本就边际」，回到 P0.4 复核信号强度，而非继续下游。")
        lines.append("- 若 ΔSharpe 为负或 P(μ_true>0)<0.95，说明放大暴露只是放大噪声/回撤，无真实增量。")
    lines.append("")
    (OUT_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"      写出: {OUT_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
