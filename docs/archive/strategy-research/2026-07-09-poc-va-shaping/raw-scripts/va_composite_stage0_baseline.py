#!/usr/bin/env python3
"""
va-composite · 阶段 0 基线 B0 回测脚本

位置: scripts/ai_tmp/va_composite_stage0_baseline.py
主题: docs/research/themes/va-asymmetry-composite/
归档: 随主题批次迁入 <batch>/raw-scripts/（quant-research-layout SKILL）

契约来源（双层分离）:
  - Contract 层: strategy-math-spec.md v0.1（§1-§10 硬约束）
  - Parameter 层: parameter-selection-spec.md v0.1（L0-L2 基线 / B0）

运行: uv run python scripts/ai_tmp/va_composite_stage0_baseline.py
输出:
  - project_data/ai_tmp/va_composite_stage0_baseline.trades.parquet  （§10 字段）
  - docs/workbench/va-asymmetry-composite-stage0-baseline.md
  - 控制台报告 + Gatekeeper 判定

设计要点（与 math-spec 对齐）:
  - 入场价 = timeline 的 close_t（§3.1 理论价）
  - 退出 = 读 5m CSV 逐 bar 扫描：
        SL 穿越：多头 low<=P_SL / 空头 high>=P_SL → exit_price=P_SL, reason=SL
        时间退出：到达 H_L/H_S 小时 bar close → reason=TIME（§3.3，SL 优先）
  - 仓位（§5.3 含 ATR 修正版）：notional_frac = 0.02 / (K_SL * entry_atr_bps/10000)
        满足 §7.1「单笔失败亏 2% 权益」（math-spec §5.3 字面公式漏 ATR，已修正）
  - 风控（§7.2）：按入场日聚合名义，超额比例压仓至 ≤100%
  - 成本（§6）：realistic-cost，单边 commission+slippage，entry/exit 分别计 bps

已知 doc/数据差异（实现已采纳数据实际，登记于 workbench）:
  1. §2 写 entry_atr_bps = "rolling20d"；timeline 实测仅 daily_atr_10_bps（10日）。
     实现采用 daily_atr_10_bps 作为 entry_atr_bps。
  2. §5.3 仓位公式 = 0.02/K_SL（漏 ATR），与 §3.2/§7.1「单笔亏 2%」矛盾。
     实现采用含 ATR 经济正确版（见上）。
  3. experiment-plan §0.1「阶段0不需要市场数据」与 math-spec §3.3/§10 矛盾；
     math-spec 为唯一定义源 → 阶段0 必须读 5m（退出需连续价格序列）。
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
OUT_PARQUET = Path("project_data/ai_tmp/va_composite_stage0_baseline.trades.parquet")
OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
WORKBENCH = Path("docs/workbench/va-asymmetry-composite-stage0-baseline.md")
EQUITY_INIT = 1_000_000.0  # 简化权益模型（§10 阶段0-2 允许）


# =====================================================================
# CONTRACT LAYER  (src: strategy-math-spec.md v0.1)
#   硬约束：tier 定义(§1.2) / ATR 归一化(§2) / SL(§3.2) / 时间退出(§3.3)
#          / 成本(§6) / 风控(§7) / 去重(§8.1) / 输出字段(§10)
# =====================================================================

# §1.2 tier 映射：raw（archive 命名）→ v4.0 六类（L_seg2_low_flat 已禁用，不在白名单）
# src: math-spec §1.2 + archive poc_va_risk_managed_v2.py A_TIER_RAW / TIER_TO_V40
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

# §4.1 品种类型 A/B/C（src: math-spec §4.1，前缀统一小写）
SYMBOL_TYPE: dict[str, str] = {}
for p in ["if", "ih", "ic", "im", "t", "tf", "ts", "au", "ag"]:
    SYMBOL_TYPE[p] = "A"
for p in ["rb", "hc", "i", "j", "jm", "ta", "ma", "pp", "l", "v", "eb", "eg", "sc", "fu", "bu"]:
    SYMBOL_TYPE[p] = "B"
for p in ["cu", "al", "zn", "ni", "sn", "pb", "m", "y", "p", "c", "cs", "cf", "sr", "oi", "rm", "fg"]:
    SYMBOL_TYPE[p] = "C"


# §6 成本（src: math-spec §6.1 / §6.3）。单边成本，bps of notional（与手数无关）。
# 注意：成本占名义的比例与持仓手数无关，故按 1 手计成本后除以单合约名义(price*size)。
def cost_oneway_bps(spec, price: float, lots: int = 1) -> float:
    ccy = spec.total_commission(price=price, lots=1) + spec.slippage(lots=1)
    return ccy / (price * spec.size) * 10000.0


# =====================================================================
# PARAMETER LAYER  (src: parameter-selection-spec.md v0.1)
#   L0 硬约束（锁定）/ L1 塑形基线 / L2 选择基线（B0）
# =====================================================================

# L0 硬约束（src: parameter-selection-spec L0.3-L0.6）
RISK_PER_TRADE = 0.02    # §7.1 单笔止损 2% 权益
MAX_NOTIONAL = 1.00      # §7.2 总名义 ≤ 100% 权益
DEDUP_HOURS = 8          # §8.1 合约内 8h 去重
COST_MODE = "realistic"  # §6 realistic-cost

# L1 塑形基线（src: parameter-selection-spec L1.1-L1.6 · B0）
K_L_SL, H_L = 1.0, 8      # L1.1/L1.2 多头 SL 1.0 · 8h
K_S_SL, H_S = 2.5, 10     # L1.3/L1.4 空头 SL 2.5 · 10h
USE_TRAILING = False      # L1.5 关闭
USE_TP = False            # L1.6 关闭

# L2 选择基线 = B0（src: parameter-selection-spec L2.1/L2.3/L2.5 初值; experiment-plan §0.2）
#   S1 全品种5档 / W0 等权 / VW0 多空等权 / clamp[0.2,1.0]（W0 不启用）
SCHEME = "S1"             # 全品种 5 档
W_STRENGTH = 1.0          # W0 等权
W_DIR_LONG = 1.0          # VW0
W_DIR_SHORT = 1.0         # VW0
W_CLAMP = (0.2, 1.0)      # L2.4 clamp 初值（W0 不启用）


# =====================================================================
# 数据加载 + 信号构建（§1.2 / §8.1）
# =====================================================================
def load_events() -> pd.DataFrame:
    tl = pd.read_parquet(TIMELINE_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    a = tl[tl["tier"].isin(A_TIER_RAW)].copy()
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["tier_v40"] = a["tier"].map(TIER_TO_V40)
    a = a.dropna(subset=["tier_v40"])
    # §2 entry_atr_bps：timeline 实测 daily_atr_10_bps（非 §2 所述 20d，取数据实际列）
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a = a.sort_values("event_time")

    # §8.1 合约内 8h 去重：每合约 8h 内只留首个信号（向量化，避免分组列丢失）
    a = a.sort_values(["contract", "event_time"]).reset_index(drop=True)
    prev_time = a.groupby("contract")["event_time"].shift(1)
    a = a[(prev_time.isna()) | ((a["event_time"] - prev_time) > pd.Timedelta(hours=DEDUP_HOURS))]
    return a.reset_index(drop=True)


# =====================================================================
# 逐合约 5m 精确模拟（§3.1-§3.3 / §5.3 / §6）
# =====================================================================
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
        stop_price = entry_price - sign * K * atr_price  # §3.2 P_SL

        # §5.3 仓位（含 ATR 修正版，满足 §7.1 单笔亏 2%）
        #   notional_frac = RiskPerTrade / (K_SL * atr_bps/10000)
        stop_dist_frac = K * atr_bps / 10000.0
        notional_frac = RISK_PER_TRADE / stop_dist_frac
        w_dir = W_DIR_LONG if direction == "long" else W_DIR_SHORT
        notional_frac *= w_dir * W_STRENGTH  # B0 均为 1
        qty_raw = notional_frac * EQUITY_INIT / (entry_price * spec.size)

        # 定位入场 bar，扫描未来 H*12 根 5m bar（1h = 12 根 5m）
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

        # §6 成本（单边，entry + exit）
        cost_entry_bps = cost_oneway_bps(spec, entry_price, qty_raw)
        cost_exit_bps = cost_oneway_bps(spec, exit_price, qty_raw)
        # §6.3 净收益
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
            "tier": ev["tier_v40"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "entry_atr_bps": atr_bps,
            "qty_raw": qty_raw,
            "qty_actual": qty_raw,  # 压仓后填充
            "w_strength": float(W_STRENGTH),
            "w_dir": float(w_dir),
            "pnl_gross_bps": pnl_gross_bps,
            "cost_entry_bps": cost_entry_bps,
            "cost_exit_bps": cost_exit_bps,
            "pnl_net_bps": pnl_net_bps,
            "pnl_net_ccy": pnl_net_ccy,
            "equity_before": np.nan,
            "equity_after": np.nan,
            # 内部字段（输出前删除）
            "_notional_frac": notional_frac,
            "_entry_date": ev["event_time"].date(),
            "_exit_date": pd.Timestamp(exit_bar).date(),
        })
    return rows


# =====================================================================
# 风控压仓（§7.2）：按入场日聚合名义，超额比例压仓至 ≤ MAX_NOTIONAL
#   注：B0 下 w_strength 全部相等，比例压仓等价于「先砍低权重」的 FIFO 近似
# =====================================================================
def compress(trades: pd.DataFrame) -> pd.DataFrame:
    daily = trades.groupby("_entry_date")["_notional_frac"].sum()
    scale = (MAX_NOTIONAL / daily).clip(upper=1.0)
    scale_map = scale.to_dict()
    trades = trades.copy()
    trades["scale"] = trades["_entry_date"].map(scale_map).fillna(1.0)
    trades["qty_actual"] = trades["qty_raw"] * trades["scale"]
    # 净收益随 qty 线性缩放；pnl_net_bps 为每单位名义，不受影响
    trades["pnl_net_ccy"] = trades["pnl_net_ccy"] * trades["scale"]
    return trades


# =====================================================================
# 简化权益曲线（§10 阶段0-2 允许 initial_equity + 累计 pnl）
#   PnL 在 exit_bar 实现（按出场顺序结算，简化）
# =====================================================================
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
# 指标（§9 归因 + experiment-plan §0.3）
# =====================================================================
def daily_returns(trades: pd.DataFrame) -> pd.Series:
    t = trades.copy()
    t["day"] = t["_exit_date"]
    daily_pnl = t.groupby("day")["pnl_net_ccy"].sum()
    ret = daily_pnl / EQUITY_INIT  # 简化：以初始权益为分母
    return ret


def base_metrics(trades: pd.DataFrame) -> dict:
    ret = daily_returns(trades)
    if len(ret) == 0:
        return {"ann_ret": 0.0, "ann_std": 0.0, "sharpe": 0.0, "max_dd": 0.0}
    all_dates = pd.date_range(ret.index.min(), ret.index.max(), freq="D")
    ret = ret.reindex(all_dates.date, fill_value=0.0)
    ann = ret.mean() * 252
    std = ret.std() * np.sqrt(252)
    sharpe = ann / std if std > 0 else 0.0
    cum = ret.cumsum()
    dd = (cum - cum.cummax()).min()
    return {"ann_ret": ann, "ann_std": std, "sharpe": sharpe, "max_dd": dd}


def monthly_win_rate(trades: pd.DataFrame) -> float:
    t = trades.copy()
    t["month"] = pd.to_datetime(t["_exit_date"]).dt.to_period("M")
    mret = t.groupby("month")["pnl_net_ccy"].sum()
    return float((mret > 0).mean()) if len(mret) else 0.0


def per_trade_ir(trades: pd.DataFrame) -> float:
    s = trades["pnl_net_bps"].std()
    return float(trades["pnl_net_bps"].mean() / s) if s > 0 else 0.0


def nu_implied(trades: pd.DataFrame) -> tuple[float, float]:
    """§9: ν = μ − σ²/2（收益率小数单位）。pnl_gross_bps 需先 /10000 转小数。"""
    g = trades["pnl_gross_bps"].values / 10000.0  # 转收益率小数
    mu = g.mean()
    var = g.var()
    nu_frac = mu - var / 2.0

    # cluster bootstrap p(ν>0)，以 (contract, date) 为簇（§9）
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


def sub_metrics(trades: pd.DataFrame) -> dict:
    m = base_metrics(trades)
    m["n"] = len(trades)
    m["monthly_win"] = monthly_win_rate(trades)
    m["ir"] = per_trade_ir(trades)
    return m


# =====================================================================
# Gatekeeper（experiment-plan §0.3）
# =====================================================================
GATE = [
    ("年化净收益 ≥ 12%", lambda m: m["ann_ret"] >= 0.12, "archive 15.45%"),
    ("净夏普 ≥ 1.8", lambda m: m["sharpe"] >= 1.8, "archive 2.23"),
    ("MaxDD ≤ 10%", lambda m: m["max_dd"] >= -0.10, "archive -7.51%"),
    ("月度胜率 ≥ 70%", lambda m: m["monthly_win"] >= 0.70, "archive 83%"),
    ("单笔 IR ≥ 0.25", lambda m: m["ir"] >= 0.25, "archive 0.30"),
    ("ν_implied > 0", lambda m: m["nu_implied"] > 0, "唯一定义源 §9"),
]


# =====================================================================
# 主流程
# =====================================================================
def main() -> None:
    print("=" * 70)
    print("va-composite 阶段0 · B0 基线回测")
    print("=" * 70)

    print("[1/5] 加载 timeline + 构建信号（§1.2/§8.1）...")
    events = load_events()
    print(f"      A 级去重后事件: {len(events)} | 合约: {events['contract'].nunique()} | "
          f"多:{(events['direction']=='long').sum()} 空:{(events['direction']=='short').sum()}")

    print("[2/5] 逐合约 5m 精确模拟（§3.1-§3.3）...")
    all_rows: list[dict] = []
    for contract, g in events.groupby("contract"):
        all_rows.extend(simulate_contract(contract, g))
    trades = pd.DataFrame(all_rows)
    print(f"      模拟交易数: {len(trades)} | SL:{(trades['exit_reason']=='SL').sum()} "
          f"TIME:{(trades['exit_reason']=='TIME').sum()}")

    print("[3/5] 风控压仓（§7.2）+ 权益曲线（§10）...")
    trades = compress(trades)
    trades = assign_equity(trades)

    # 输出 §10 字段
    out_cols = ["contract", "symbol", "symbol_type", "entry_bar", "exit_bar", "direction", "tier",
                "entry_price", "exit_price", "exit_reason", "entry_atr_bps", "qty_raw", "qty_actual",
                "w_strength", "w_dir", "pnl_gross_bps", "cost_entry_bps", "cost_exit_bps",
                "pnl_net_bps", "pnl_net_ccy", "equity_before", "equity_after"]
    out = trades[out_cols].copy()
    out.to_parquet(OUT_PARQUET, index=False)
    print(f"      写出: {OUT_PARQUET}")

    print("[4/5] 计算指标（§9 / §0.3）...")
    m = base_metrics(trades)
    m["monthly_win"] = monthly_win_rate(trades)
    m["ir"] = per_trade_ir(trades)
    m["nu_implied"], m["p_nu_pos"] = nu_implied(trades)
    long_m = sub_metrics(trades[trades["direction"] == 1])
    short_m = sub_metrics(trades[trades["direction"] == -1])

    # 逐 tier
    tier_rows = []
    for tier in sorted(trades["tier"].unique()):
        sub = trades[trades["tier"] == tier]
        sm = sub_metrics(sub)
        tier_rows.append((tier, sm["n"], sm["ann_ret"], sm["sharpe"], sm["max_dd"]))

    # 压仓诊断
    daily_notional = trades.groupby("_entry_date")["_notional_frac"].sum() * trades.groupby("_entry_date")["scale"].mean()
    compressed_days = int((trades.groupby("_entry_date")["scale"].mean() < 1.0).sum())
    avg_notional = float(trades.groupby("_entry_date")["_notional_frac"].sum().mean())

    print("[5/5] Gatekeeper 判定 + 写 workbench...")
    gate_rows = []
    all_pass = True
    for name, fn, ref in GATE:
        ok = fn(m)
        all_pass &= ok
        gate_rows.append((name, ok, ref))

    _write_workbench(m, long_m, short_m, tier_rows, gate_rows, all_pass,
                     len(trades), compressed_days, avg_notional,
                     events["contract"].nunique())
    _print_console(m, long_m, short_m, tier_rows, gate_rows, all_pass)

    print(f"\n阶段0 B0 Gatekeeper: {'ALL PASS ✅' if all_pass else 'FAIL ❌'}")


def _print_console(m, long_m, short_m, tier_rows, gate_rows, all_pass):
    print(f"\n{'='*70}\n主指标\n{'='*70}")
    print(f"  年化净收益 : {m['ann_ret']*100:7.2f}%   (archive 15.45%)")
    print(f"  净夏普     : {m['sharpe']:7.2f}     (archive 2.23)")
    print(f"  MaxDD      : {m['max_dd']*100:7.2f}%   (archive -7.51%)")
    print(f"  月度胜率   : {m['monthly_win']*100:7.1f}%   (archive 83%)")
    print(f"  单笔 IR    : {m['ir']:7.3f}     (archive 0.30)")
    print(f"  ν_implied  : {m['nu_implied']:.3f}   p(ν>0)={m['p_nu_pos']:.3f}")
    print(f"\n  多头: 年化 {long_m['ann_ret']*100:6.2f}%  Sharpe {long_m['sharpe']:.2f}  n={long_m['n']}")
    print(f"  空头: 年化 {short_m['ann_ret']*100:6.2f}%  Sharpe {short_m['sharpe']:.2f}  n={short_m['n']}")
    print(f"\n{'='*70}\nGatekeeper\n{'='*70}")
    for name, ok, ref in gate_rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:18s}  ref={ref}")
    print(f"\n  结论: {'ALL PASS ✅' if all_pass else 'FAIL ❌'}")


def _write_workbench(m, long_m, short_m, tier_rows, gate_rows, all_pass,
                     n_trades, compressed_days, avg_notional, n_contracts):
    lines = []
    lines.append("# va-asymmetry-composite · 阶段 0 基线 B0 回测")
    lines.append("")
    lines.append(f"> 生成脚本: `scripts/ai_tmp/va_composite_stage0_baseline.py`")
    lines.append(f"> 数据: `project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet` + `project_data/market_data/csv/*.tqsdk.5m.csv`")
    lines.append(f"> 输出: `project_data/ai_tmp/va_composite_stage0_baseline.trades.parquet`（§10 字段）")
    lines.append("")
    lines.append("## 1. 配置摘要（B0）")
    lines.append("")
    lines.append("| 层 | 参数 | 值 | 来源 |")
    lines.append("|:---|:---|:---|:---|")
    lines.append("| L0 | 成本口径 | realistic-cost | parameter-selection-spec L0.3 / §6 |")
    lines.append("| L0 | 单笔止损 | 2% 权益 | L0.4 / §7.1 |")
    lines.append("| L0 | 总名义上限 | 100% 权益 | L0.5 / §7.2 |")
    lines.append("| L0 | 合约内去重 | 8h | L0.6 / §8.1 |")
    lines.append("| L1 | 多头 SL × 持仓 | 1.0 × 8h | L1.1/L1.2 |")
    lines.append("| L1 | 空头 SL × 持仓 | 2.5 × 10h | L1.3/L1.4 |")
    lines.append("| L1 | Trailing / TP | 关闭 / 关闭 | L1.5/L1.6 |")
    lines.append("| L2 | 品种筛选 | S1 全品种5档 | L2.1 / §4.2 |")
    lines.append("| L2 | 强度加权 | W0 等权 | L2.3 / §5.1 |")
    lines.append("| L2 | 多空权重 | VW0 等权 | L2.5 / §5.2 |")
    lines.append("")
    lines.append("## 2. 文档/数据差异登记（实现已采纳数据实际）")
    lines.append("")
    lines.append("| # | 差异 | 处理 |")
    lines.append("|:---|:---|:---|")
    lines.append("| 1 | §2 写 entry_atr_bps=rolling20d，timeline 实测仅 `daily_atr_10_bps`（10日） | 采用 `daily_atr_10_bps` |")
    lines.append("| 2 | §5.3 仓位公式 `0.02/K_SL` 漏 ATR，与 §3.2/§7.1「单笔亏2%」矛盾 | 采用含 ATR 版 `0.02/(K_SL·entry_atr_bps/10000)`，与 archive 一致 |")
    lines.append("| 3 | experiment-plan §0.1「阶段0不需市场数据」与 §3.3/§10 矛盾 | 以 math-spec 为准，读 5m 做退出 |")
    lines.append("")
    lines.append("## 3. 主指标 vs archive")
    lines.append("")
    lines.append("| 指标 | B0 本主题 | archive 参考 | 阈值(§0.3) |")
    lines.append("|:---|---:|---:|---:|")
    lines.append(f"| 年化净收益 | {m['ann_ret']*100:.2f}% | 15.45% | ≥12% |")
    lines.append(f"| 净夏普 | {m['sharpe']:.2f} | 2.23 | ≥1.8 |")
    lines.append(f"| MaxDD | {m['max_dd']*100:.2f}% | -7.51% | ≤10% |")
    lines.append(f"| 月度胜率 | {m['monthly_win']*100:.1f}% | 83% | ≥70% |")
    lines.append(f"| 单笔 IR | {m['ir']:.3f} | 0.30 | ≥0.25 |")
    lines.append(f"| ν_implied | {m['nu_implied']:.3f} | - | >0 |")
    lines.append(f"| p(ν>0) bootstrap | {m['p_nu_pos']:.3f} | - | ≥0.95(目标) |")
    lines.append("")
    lines.append("## 4. 多空 / 逐 tier")
    lines.append("")
    lines.append(f"- 多头: 年化 {long_m['ann_ret']*100:.2f}% · Sharpe {long_m['sharpe']:.2f} · MaxDD {long_m['max_dd']*100:.2f}% · n={long_m['n']}")
    lines.append(f"- 空头: 年化 {short_m['ann_ret']*100:.2f}% · Sharpe {short_m['sharpe']:.2f} · MaxDD {short_m['max_dd']*100:.2f}% · n={short_m['n']}")
    lines.append("")
    lines.append("| tier | n | 年化 | Sharpe | MaxDD |")
    lines.append("|:---|---:|---:|---:|---:|")
    for tier, n, ann, sh, dd in tier_rows:
        lines.append(f"| {tier} | {n} | {ann*100:.2f}% | {sh:.2f} | {dd*100:.2f}% |")
    lines.append("")
    lines.append("## 5. 风控诊断")
    lines.append("")
    lines.append(f"- 交易数: {n_trades} | 合约数: {n_contracts}")
    lines.append(f"- 日均名义暴露(压仓前): {avg_notional*100:.1f}%")
    lines.append(f"- 触发压仓的天数: {compressed_days}")
    lines.append("")
    lines.append("## 6. Gatekeeper（§0.3）")
    lines.append("")
    lines.append("| 判据 | 结果 | 参考 |")
    lines.append("|:---|:---:|:---|")
    for name, ok, ref in gate_rows:
        lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {ref} |")
    lines.append("")
    lines.append(f"**结论: {'ALL PASS ✅' if all_pass else 'FAIL ❌'}**")
    lines.append("")
    WORKBENCH.parent.mkdir(parents=True, exist_ok=True)
    WORKBENCH.write_text("\n".join(lines), encoding="utf-8")
    print(f"      写出: {WORKBENCH}")


if __name__ == "__main__":
    main()
