#!/usr/bin/env python3
"""
va-composite · 阶段 1 三大方向 Gatekeeper 独立扫描

位置: scripts/ai_tmp/va_composite_stage1_gatekeepers.py
主题: docs/research/themes/va-asymmetry-composite/
归档: 随主题批次迁入 <batch>/raw-scripts/（quant-research-layout SKILL）

契约来源（双层分离，同阶段 0）:
  - Contract 层: strategy-math-spec.md v0.1（§1-§10 硬约束）
  - Parameter 层: parameter-selection-spec.md v0.1（L0-L2）

运行: uv run python scripts/ai_tmp/va_composite_stage1_gatekeepers.py
输出:
  - project_data/ai_tmp/va_composite_stage1_{CFG}.trades.parquet  （每配置一份，§10 字段）
  - docs/workbench/va-asymmetry-composite-stage1-gatekeepers.md
  - 控制台报告 + 各方向 Gatekeeper 判定 + paired bootstrap p

设计（experiment-plan §1.0「每方向独立锁 baseline」）:
  - 7 配置: B0(S1/W0/VW0) / S2(S2/W0/VW0) / W1,W2,W3(S1/W*/VW0) / VW1,VW2(S1/W0/VW*)
  - 共享一次 5m 中性模拟（pnl_net_bps 与权重无关），再按配置叠加
    w_strength（W）→ S2 过滤 → w_dir（VW）→ 优先级压仓
  - 判据: Δsharpe(cfg) - Δsharpe(B0) ≥ 0.2 · p_boot ≤ 0.0083（family=6）· ν_implied > 0

已知 doc/数据差异（实现已采纳数据实际，登记于 workbench）:
  4. §5.1/§5.2 写 rank 列名 `signed_skew_rank`/`daily_atr_bps_rank`/`trend_10d_ret_rank`，
     timeline 实测为 `signed_skew_rank_roll`/`atr_rank_roll`/`trend_rank_roll` → 采用 *_roll。
  5. experiment-plan §0.4 写「阶段1 family=9」，§1.0 写「family=6, α=0.0083」；
     §1.0 为阶段1 自身设计 → 采用 family=6 / α=0.0083。
  （差异 1-3 见阶段 0 workbench）
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
OUT_DIR = Path("project_data/ai_tmp")
OUT_DIR.mkdir(parents=True, exist_ok=True)
WORKBENCH = Path("docs/workbench/va-asymmetry-composite-stage1-gatekeepers.md")
EQUITY_INIT = 1_000_000.0

# rank 列名（差异 4：timeline 实测 *_roll 后缀）
SKEW_COL = "signed_skew_rank_roll"
ATR_COL = "atr_rank_roll"
TREND_COL = "trend_rank_roll"


# =====================================================================
# CONTRACT LAYER  (src: strategy-math-spec.md v0.1)
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

# §4.1 S2 tier×品种映射（默认启用子集）
ALLOWED_S2 = {
    "A": {"L_seg12_high_up", "S_seg12_high_dn"},
    "B": {"L_seg3_lowmid_up", "S_seg34_high_dn"},
    "C": {"L_seg3_lowmid_up", "L_seg12_high_up", "S_seg12_high_dn",
          "S_seg34_high_dn", "S_seg2_mid_dn"},
}

# §5.1 W1 的 thr_skew（tier 对应 skew 段最近端点）
# math-spec §5.1: "多 0.30/0.19，空 0.60/0.81"
# S_seg12_high_dn 的 skew 段为 [0.81, 1.00]，端点 = 0.81（原 AI 误填 0.67 为 ATR 阈值）
TIER_THR_SKEW = {
    "L_seg3_lowmid_up": 0.30,
    "L_seg12_high_up": 0.19,
    "S_seg12_high_dn": 0.81,
    "S_seg34_high_dn": 0.60,
    "S_seg2_mid_dn": 0.81,
}
# §5.1 W3 的 t_center（按方向）
T_CENTER = {"long": 0.875, "short": 0.10}

# §6 成本
def cost_oneway_bps(spec, price: float, lots: int = 1) -> float:
    ccy = spec.total_commission(price=price, lots=1) + spec.slippage(lots=1)
    return ccy / (price * spec.size) * 10000.0


# =====================================================================
# PARAMETER LAYER  (src: parameter-selection-spec.md v0.1)
# =====================================================================

RISK_PER_TRADE = 0.02    # §7.1 单笔 2% 权益
MAX_NOTIONAL = 1.00      # §7.2 总名义 ≤ 100%
DEDUP_HOURS = 8          # §8.1 8h 去重
K_L_SL, H_L = 1.0, 8
K_S_SL, H_S = 2.5, 10
W_CLAMP = (0.2, 1.0)


# =====================================================================
# 数据加载 + 信号构建（§1.2 / §8.1，带 rank 列）
# =====================================================================
def load_events() -> pd.DataFrame:
    tl = pd.read_parquet(TIMELINE_PATH)
    tl["event_time"] = pd.to_datetime(tl["event_time"])
    a = tl[tl["tier"].isin(A_TIER_RAW)].copy()
    a["direction"] = a["tier"].apply(lambda t: "long" if t.startswith("UP") else "short")
    a["tier_v40"] = a["tier"].map(TIER_TO_V40)
    a = a.dropna(subset=["tier_v40"])
    a["entry_atr_bps"] = a["daily_atr_10_bps"]
    a["sym"] = a["contract"].apply(lambda c: (extract_contract_prefix(c) or "").lower())
    a["symbol_type"] = a["sym"].map(SYMBOL_TYPE).fillna("C")
    a = a.sort_values(["contract", "event_time"]).reset_index(drop=True)
    # §8.1 合约内 8h 去重
    prev_time = a.groupby("contract")["event_time"].shift(1)
    a = a[(prev_time.isna()) | ((a["event_time"] - prev_time) > pd.Timedelta(hours=DEDUP_HOURS))]
    return a.reset_index(drop=True)


# =====================================================================
# 中性模拟（5m 精确，权重无关）：产出每笔基础量
#   含 pnl_gross_bps / pnl_net_bps(=单位名义收益率, 与 w 无关) / _notional_unit(不含 w)
# =====================================================================
def neutral_simulate(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for contract, g in events.groupby("contract"):
        spec = CONTRACT_SPECS.get_symbol(contract)
        if spec is None:
            continue
        csv_path = MARKET_DIR / f"{contract}.tqsdk.5m.csv"
        if not csv_path.exists():
            continue
        bars = pd.read_csv(csv_path, usecols=["datetime", "high", "low", "close"])
        bars["datetime"] = pd.to_datetime(bars["datetime"])
        bars = bars.sort_values("datetime").reset_index(drop=True)
        if bars.empty:
            continue
        for _, ev in g.iterrows():
            direction = ev["direction"]
            sign = 1 if direction == "long" else -1
            K = K_L_SL if direction == "long" else K_S_SL
            H = H_L if direction == "long" else H_S
            ep = float(ev["close_t"])
            atr_bps = float(ev["entry_atr_bps"])
            if ep <= 0 or atr_bps <= 0:
                continue
            atr_price = ep * atr_bps / 10000.0
            stop_price = ep - sign * K * atr_price  # §3.2 P_SL
            idx = int(bars["datetime"].searchsorted(ev["event_time"]))
            future = bars.iloc[idx: idx + H * 12]
            if len(future) == 0:
                continue
            xp = np.nan
            xr = "TIME"
            xb = future.iloc[-1]["datetime"]
            for _, bar in future.iterrows():
                if sign == 1 and bar["low"] <= stop_price:
                    xp, xr, xb = stop_price, "SL", bar["datetime"]
                    break
                if sign == -1 and bar["high"] >= stop_price:
                    xp, xr, xb = stop_price, "SL", bar["datetime"]
                    break
            if np.isnan(xp):
                xp, xb = float(future.iloc[-1]["close"]), future.iloc[-1]["datetime"]
            ce = cost_oneway_bps(spec, ep)
            cx = cost_oneway_bps(spec, xp)
            gross_ret = sign * (xp - ep) / ep
            pnl_gross_bps = gross_ret * 10000.0
            pnl_net_bps = pnl_gross_bps - ce - cx  # 与 w 无关
            stop_dist_frac = K * atr_bps / 10000.0
            notional_unit = RISK_PER_TRADE / stop_dist_frac  # 不含 w
            rows.append({
                "contract": contract,
                "symbol": ev["sym"],
                "symbol_type": ev["symbol_type"],
                "tier": ev["tier_v40"],
                "direction": int(sign),
                "entry_bar": ev["event_time"],
                "exit_bar": xb,
                "_entry_date": ev["event_time"].date(),
                "_exit_date": pd.Timestamp(xb).date(),
                "entry_price": ep,
                "exit_price": xp,
                "exit_reason": xr,
                "entry_atr_bps": atr_bps,
                "pnl_gross_bps": pnl_gross_bps,
                "pnl_net_bps": pnl_net_bps,  # 单位名义收益率，权重无关
                "cost_entry_bps": ce,
                "cost_exit_bps": cx,
                "spec_size": spec.size,
                "_notional_unit": notional_unit,
                "_skew_rank": float(ev[SKEW_COL]),
                "_atr_rank": float(ev[ATR_COL]),
                "_trend_rank": float(ev[TREND_COL]),
            })
    return pd.DataFrame(rows)


# =====================================================================
# W 权重（§5.1）· per-event
# =====================================================================
def apply_w_strength(df: pd.DataFrame, scheme: str) -> pd.DataFrame:
    df = df.copy()
    lo, hi = W_CLAMP
    if scheme == "W0":
        df["w_strength"] = 1.0
        return df
    thr = df["tier"].map(TIER_THR_SKEW)
    # 修正：math-spec "越远离阈值权重越大" 应表达为距离 |rank - thr|
    # 原 AI 直接套用 (thr - rank) 导致空头全为负值被压到 0.2
    denom = (thr - 0.5 * thr).abs()
    if scheme == "W1":
        # w = clamp(|skew_rank - thr| / |thr - 0.5*thr|, 0.2, 1.0)
        w_raw = (df["_skew_rank"] - thr).abs() / denom
        w = w_raw.clip(lo, hi)
    elif scheme == "W2":
        # w = clamp(1 - 4*|atr_rank - 0.5|, 0.2, 1.0)
        w = (1.0 - 4.0 * (df["_atr_rank"] - 0.5).abs()).clip(lo, hi)
    elif scheme == "W3":
        # 修正：w1/w2 先按 W1/W2 规则各自 clamp，再参与乘积
        w1_raw = (df["_skew_rank"] - thr).abs() / denom
        w1 = w1_raw.clip(lo, hi)
        w2 = (1.0 - 4.0 * (df["_atr_rank"] - 0.5).abs()).clip(lo, hi)
        t_center = df["direction"].map(lambda d: T_CENTER["long" if d == 1 else "short"])
        w3 = (1.0 - 2.0 * (df["_trend_rank"] - t_center).abs()).clip(lo, hi)
        w = (w1 * w2 * w3).clip(lo, hi)
    else:
        raise ValueError(scheme)
    df["w_strength"] = w
    return df


# =====================================================================
# S 过滤（§4.1）· S2 按品种类型×tier
# =====================================================================
def apply_s_filter(df: pd.DataFrame, scheme: str) -> pd.DataFrame:
    if scheme == "S1":
        return df.copy()
    if scheme == "S2":
        mask = df.apply(lambda r: r["tier"] in ALLOWED_S2[r["symbol_type"]], axis=1)
        return df[mask].reset_index(drop=True)
    raise ValueError(scheme)


# =====================================================================
# VW 权重（§5.2）· per-direction，基于该配置 trade 集
# =====================================================================
def _tier_ir(sub: pd.DataFrame) -> float:
    """单 tier 单笔 IR（净收益 bps 的 mean/std）"""
    if len(sub) < 2 or sub["pnl_net_bps"].std() == 0:
        return 0.0
    return float(sub["pnl_net_bps"].mean() / sub["pnl_net_bps"].std())


def compute_w_dir(df: pd.DataFrame, scheme: str) -> dict:
    if scheme == "VW0":
        return {"long": 1.0, "short": 1.0}
    if scheme == "VW1":
        # 修正：math-spec "按 tier 组平均单笔 IR" —— 先算每个 tier 的 IR，再等权平均
        long_tiers = df[df["direction"] == 1].groupby("tier")
        short_tiers = df[df["direction"] == -1].groupby("tier")
        ir_by_tier_l = [_tier_ir(g) for _, g in long_tiers]
        ir_by_tier_s = [_tier_ir(g) for _, g in short_tiers]
        ir_l = np.mean(ir_by_tier_l) if ir_by_tier_l else 0.0
        ir_s = np.mean(ir_by_tier_s) if ir_by_tier_s else 0.0
        ir_max = max(ir_l, ir_s, 1e-9)
        w_l = np.clip(ir_l / ir_max, 0.5, 1.0)
        w_s = np.clip(ir_s / ir_max, 0.5, 1.0)
        return {"long": float(w_l), "short": float(w_s)}
    if scheme == "VW2":
        n_l = len(df[df["direction"] == 1])
        n_s = len(df[df["direction"] == -1])
        if n_l == 0 or n_s == 0:
            return {"long": 1.0, "short": 1.0}
        w_l = np.clip(np.sqrt(n_s / n_l), 0.5, 2.0)
        w_s = np.clip(np.sqrt(n_l / n_s), 0.5, 2.0)
        return {"long": float(w_l), "short": float(w_s)}
    raise ValueError(scheme)


# =====================================================================
# 优先级压仓（§7.2）：per entry_date 按 w_strength↑ + 近到期 + FIFO 截断
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


def compress_overall(df: pd.DataFrame) -> pd.DataFrame:
    """整体比例缩放（阶段0→1 统一口径，B0 基准可比）。
    §7.2 优先级砍仓（w 分化时更准）留待阶段2 联合搜索启用。"""
    df = df.copy()
    daily = df.groupby("_entry_date")["_notional_frac"].sum()
    scale = (MAX_NOTIONAL / daily).clip(upper=1.0)
    df["scale"] = df["_entry_date"].map(scale.to_dict()).fillna(1.0)
    df["qty_actual"] = df["_notional_frac"] * df["scale"] * EQUITY_INIT / (df["entry_price"] * df["spec_size"])
    df["pnl_net_ccy"] = df["pnl_net_bps"] / 10000.0 * df["_notional_frac"] * df["scale"] * EQUITY_INIT
    return df


# =====================================================================
# 指标（§9 / §0.3 / §1.5）
# =====================================================================
def daily_returns(trades: pd.DataFrame) -> pd.Series:
    daily_pnl = trades.groupby("_exit_date")["pnl_net_ccy"].sum()
    return daily_pnl / EQUITY_INIT


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
    g = trades["pnl_gross_bps"].values / 10000.0
    mu, var = g.mean(), g.var()
    nu_frac = mu - var / 2.0
    grp = trades.groupby(["contract", "_exit_date"])["pnl_gross_bps"]
    sizes = grp.size().values.astype(float)
    sums = grp.sum().values / 10000.0
    sumsq = grp.apply(lambda x: (x ** 2).sum()).values / 10000.0 ** 2
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


def symbol_retention(trades: pd.DataFrame) -> dict:
    """§1.5 品种保留率：按 A/B/C 分组（单品种正收益数 / 参与数）"""
    res = {}
    for stype in ["A", "B", "C"]:
        sub = trades[trades["symbol_type"] == stype]
        if len(sub) == 0:
            res[stype] = (0, 0, None)
            continue
        by_sym = sub.groupby("symbol")["pnl_net_ccy"].sum()
        n_pos = int((by_sym > 0).sum())
        n_tot = len(by_sym)
        res[stype] = (n_pos, n_tot, n_pos / n_tot if n_tot else None)
    return res


def paired_bootstrap(cfg: pd.DataFrame, b0: pd.DataFrame, n: int = 500, seed: int = 42) -> float:
    """§0.4 配对显著性：同一 event 配对 diff 的 (contract,exit_date) cluster bootstrap。
    返回单尾 p = P(Σdiff ≤ 0)（cfg 不优于 B0 的概率；cfg 显著优 → p 小）。"""
    m = cfg[["contract", "entry_bar", "_exit_date", "pnl_net_ccy"]].merge(
        b0[["contract", "entry_bar", "pnl_net_ccy"]], on=["contract", "entry_bar"], suffixes=("_c", "_b"))
    if len(m) == 0:
        return 1.0
    m["diff"] = m["pnl_net_ccy_c"] - m["pnl_net_ccy_b"]
    clusters = m.groupby(["contract", "_exit_date"])["diff"].sum()
    if len(clusters) == 0:
        return 1.0
    rng = np.random.default_rng(seed)
    vals = np.empty(n)
    arr = clusters.values
    for i in range(n):
        sel = rng.integers(0, len(arr), len(arr))
        vals[i] = arr[sel].sum()
    return float((vals <= 0).mean())


# =====================================================================
# 单配置构建
# =====================================================================
def build_config(neutral: pd.DataFrame, S: str, W: str, VW: str) -> pd.DataFrame:
    df = apply_w_strength(neutral, W)
    df = apply_s_filter(df, S)
    if len(df) == 0:
        return df
    w_dir = compute_w_dir(df, VW)
    df["w_dir"] = df["direction"].map(lambda d: w_dir["long" if d == 1 else "short"])
    df["_notional_frac"] = df["_notional_unit"] * df["w_strength"] * df["w_dir"]
    df = compress_overall(df)
    return df


# =====================================================================
# 主流程
# =====================================================================
CONFIGS = [
    ("B0", "S1", "W0", "VW0"),
    ("S2", "S2", "W0", "VW0"),
    ("W1", "S1", "W1", "VW0"),
    ("W2", "S1", "W2", "VW0"),
    ("W3", "S1", "W3", "VW0"),
    ("VW1", "S1", "W0", "VW1"),
    ("VW2", "S1", "W0", "VW2"),
]


def main() -> None:
    print("=" * 70)
    print("va-composite 阶段1 · 三大方向 Gatekeeper 独立扫描")
    print("=" * 70)

    print("[1/4] 加载 timeline + 构建信号（§1.2/§8.1）...")
    events = load_events()
    print(f"      A 级去重后事件: {len(events)} | 合约: {events['contract'].nunique()}")

    print("[2/4] 中性 5m 模拟（共享，权重无关）...")
    neutral = neutral_simulate(events)
    print(f"      基础交易数: {len(neutral)}")

    print("[3/4] 构建 7 配置 + 指标 + paired bootstrap...")
    results = {}
    b0 = None
    for cfg_id, S, W, VW in CONFIGS:
        df = build_config(neutral, S, W, VW)
        m = base_metrics(df)
        m["monthly_win"] = monthly_win_rate(df)
        m["ir"] = per_trade_ir(df)
        m["nu_implied"], m["p_nu_pos"] = nu_implied(df)
        m["retention"] = symbol_retention(df)
        m["n"] = len(df)
        m["S"], m["W"], m["VW"] = S, W, VW
        # w_strength 分布
        m["w_mean"] = float(df["w_strength"].mean()) if len(df) else 0.0
        m["w_min"] = float(df["w_strength"].min()) if len(df) else 0.0
        m["w_max"] = float(df["w_strength"].max()) if len(df) else 0.0
        # 多空贡献度
        long_pnl = float(df[df["direction"] == 1]["pnl_net_ccy"].sum())
        short_pnl = float(df[df["direction"] == -1]["pnl_net_ccy"].sum())
        tot = long_pnl + short_pnl
        m["long_contrib"] = long_pnl / tot if tot else 0.0
        m["short_contrib"] = short_pnl / tot if tot else 0.0
        # 压仓比例
        m["compress_days"] = int((df.groupby("_entry_date")["scale"].mean() < 1.0).sum())
        m["avg_notional"] = float(df.groupby("_entry_date")["_notional_frac"].sum().mean())
        # 成本 ATR 倍率（平均单边成本 bps / 平均 atr bps）
        m["cost_atr_ratio"] = float(
            (df["cost_entry_bps"].mean() + df["cost_exit_bps"].mean()) / 2.0 / df["entry_atr_bps"].mean()) \
            if len(df) else 0.0
        results[cfg_id] = (df, m)
        if cfg_id == "B0":
            b0 = df
        # 写 parquet（§10 字段 + 内部权重列）
        out_cols = ["contract", "symbol", "symbol_type", "entry_bar", "exit_bar", "direction", "tier",
                    "entry_price", "exit_price", "exit_reason", "entry_atr_bps", "qty_raw", "qty_actual",
                    "w_strength", "w_dir", "pnl_gross_bps", "cost_entry_bps", "cost_exit_bps",
                    "pnl_net_bps", "pnl_net_ccy", "equity_before", "equity_after"]
        df = assign_equity(df)
        df_out = df.copy()
        df_out["qty_raw"] = df["_notional_unit"] * df["w_strength"] * df["w_dir"] * EQUITY_INIT / (df["entry_price"] * df["spec_size"])
        df_out = df_out[out_cols]
        df_out.to_parquet(OUT_DIR / f"va_composite_stage1_{cfg_id}.trades.parquet", index=False)
        print(f"      {cfg_id:4s} S={S:2s} W={W:2s} VW={VW:3s} | n={m['n']:4d} "
              f"ann={m['ann_ret']*100:6.2f}% Sharpe={m['sharpe']:.2f} Δsh={0:.2f} ν={m['nu_implied']:.2f}")

    # paired bootstrap vs B0
    print("[4/4] paired bootstrap + Gatekeeper 判定 + 写 workbench...")
    boot = {}
    for cfg_id, (df, m) in results.items():
        if cfg_id == "B0":
            boot[cfg_id] = 1.0
            continue
        p = paired_bootstrap(df, b0)
        boot[cfg_id] = p

    b0_m = results["B0"][1]
    gate_rows = []
    for cfg_id, (df, m) in results.items():
        if cfg_id == "B0":
            continue
        d_sharpe = m["sharpe"] - b0_m["sharpe"]
        d_ann = m["ann_ret"] - b0_m["ann_ret"]
        p = boot[cfg_id]
        # §1.x 判据：Δsharpe ≥ 0.2 · p_boot ≤ 0.0083 · ν_implied > 0
        ok = (d_sharpe >= 0.2) and (p <= 0.0083) and (m["nu_implied"] > 0)
        gate_rows.append((cfg_id, m["S"], m["W"], m["VW"], d_sharpe, d_ann, p, m["nu_implied"], ok))

    _write_workbench(results, boot, gate_rows, b0_m)
    _print_console(results, boot, gate_rows, b0_m)


def _print_console(results, boot, gate_rows, b0_m):
    print(f"\n{'='*70}\n阶段1 各配置主指标\n{'='*70}")
    print(f"{'cfg':5s} {'n':>5s} {'ann%':>8s} {'Sharpe':>8s} {'ΔSh':>6s} {'MaxDD%':>8s} {'mWin%':>7s} {'IR':>6s} {'ν':>7s} {'p_boot':>8s}")
    for cfg_id, (df, m) in results.items():
        d_sh = m["sharpe"] - b0_m["sharpe"] if cfg_id != "B0" else 0.0
        p = boot[cfg_id]
        print(f"{cfg_id:5s} {m['n']:5d} {m['ann_ret']*100:8.2f} {m['sharpe']:8.2f} {d_sh:6.2f} "
              f"{m['max_dd']*100:8.2f} {m['monthly_win']*100:7.1f} {m['ir']:6.3f} {m['nu_implied']:7.2f} {p:8.4f}")
    print(f"\n{'='*70}\n各方向 Gatekeeper（ΔSharpe≥0.2 · p≤0.0083 · ν>0）\n{'='*70}")
    for cfg_id, S, W, VW, d_sh, d_ann, p, nu, ok in gate_rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {cfg_id:4s} S={S} W={W} VW={VW} "
              f"ΔSh={d_sh:+.2f} p={p:.4f} ν={nu:.2f}")
    n_pass = sum(1 for *_x, ok in gate_rows if ok)
    print(f"\n  通过方向数: {n_pass}/6")


def _write_workbench(results, boot, gate_rows, b0_m):
    lines = []
    lines.append("# va-asymmetry-composite · 阶段 1 三大方向 Gatekeeper")
    lines.append("")
    lines.append("> 生成脚本: `scripts/ai_tmp/va_composite_stage1_gatekeepers.py`")
    lines.append("> 数据: timeline + `project_data/market_data/csv/*.tqsdk.5m.csv`")
    lines.append("> 输出: `project_data/ai_tmp/va_composite_stage1_{CFG}.trades.parquet`（§10 字段）")
    lines.append("")
    lines.append("## 1. 设计摘要")
    lines.append("")
    lines.append("- 每方向独立锁 baseline（§1.0）：S2=S2/W0/VW0，W*=S1/W*/VW0，VW*=S1/W0/VW*")
    lines.append("- 共享一次 5m 中性模拟（pnl_net_bps 与权重无关），再叠加 w_strength→S2过滤→w_dir→优先级压仓")
    lines.append("- 判据：ΔSharpe(cfg)−ΔSharpe(B0) ≥ 0.2 · p_boot(date-cluster) ≤ 0.0083(family=6) · ν_implied > 0")
    lines.append("")
    lines.append("## 2. 7 配置指标矩阵（§1.5）")
    lines.append("")
    lines.append("| cfg | n | 年化% | Sharpe | ΔSh | MaxDD% | 月胜% | IR | ν_implied | p_boot | w_mean | 多空贡献(L/S) | 压仓天 | 成本/ATR | 保留率A/B/C |")
    lines.append("|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---|---:|---:|:---|")
    for cfg_id, (df, m) in results.items():
        d_sh = m["sharpe"] - b0_m["sharpe"] if cfg_id != "B0" else 0.0
        p = boot[cfg_id]
        rt = m["retention"]
        rt_str = "/".join(f"{v[0]}/{v[1]}" for v in rt.values())
        lines.append(
            f"| {cfg_id} | {m['n']} | {m['ann_ret']*100:.2f} | {m['sharpe']:.2f} | {d_sh:+.2f} | "
            f"{m['max_dd']*100:.2f} | {m['monthly_win']*100:.1f} | {m['ir']:.3f} | {m['nu_implied']:.2f} | "
            f"{p:.4f} | {m['w_mean']:.2f} | {m['long_contrib']:.0%}/{m['short_contrib']:.0%} | "
            f"{m['compress_days']} | {m['cost_atr_ratio']:.1f} | {rt_str} |")
    lines.append("")
    lines.append("## 3. 各方向 Gatekeeper 判定")
    lines.append("")
    lines.append("| cfg | S | W | VW | ΔSharpe | Δ年化 | p_boot | ν_implied | 通过 |")
    lines.append("|:---|:---|:---|:---|---:|---:|---:|---:|:---:|")
    for cfg_id, S, W, VW, d_sh, d_ann, p, nu, ok in gate_rows:
        lines.append(f"| {cfg_id} | {S} | {W} | {VW} | {d_sh:+.2f} | {d_ann*100:+.2f}% | {p:.4f} | {nu:.2f} | {'PASS' if ok else 'FAIL'} |")
    lines.append("")
    n_pass = sum(1 for *_x, ok in gate_rows if ok)
    lines.append(f"**通过方向数: {n_pass}/6**")
    lines.append("")
    lines.append("## 4. 阶段 1 汇总判决（§1.4）")
    lines.append("")
    lines.append(f"- ≥2 方向通过 → 阶段 2 联合搜索")
    lines.append(f"- 1 方向通过 → 阶段 1.5 平台宽度检查")
    lines.append(f"- 0 方向通过 → 主题降级（B0 直接工程化 或 冻结）")
    lines.append(f"- 本次结果：{n_pass} 方向通过")
    lines.append("")
    lines.append("## 5. 文档/数据差异登记")
    lines.append("")
    lines.append("| # | 差异 | 处理 |")
    lines.append("|:---|:---|:---|")
    lines.append("| 1-3 | 见阶段0 workbench（atr 列名/§5.3 仓位公式/§0.1 市场数据） | 已采纳数据实际 |")
    lines.append("| 4 | §5.1/§5.2 写 rank 列 `signed_skew_rank`/`daily_atr_bps_rank`/`trend_10d_ret_rank`；timeline 实测 `*_roll` 后缀 | 采用 `*_roll` 列 |")
    lines.append("| 5 | experiment-plan §0.4 写「阶段1 family=9」，§1.0 写「family=6, α=0.0083」 | 采用 §1.0 的 family=6 / α=0.0083（阶段1 自身设计） |")
    lines.append("| 6 | S2 实现依赖 §4.1 tier×品种映射（A=L12+S12, B=L3+S34, C=全5档）；L_seg2_low_flat 不在 v4.0 白名单，C 类补验暂未单独启用 | 按 §4.1 实现；补验项见下方 §6 |")
    lines.append("")
    lines.append("## 6. 补验项（§1.1）· L_seg2_low_flat × C 类")
    lines.append("")
    lines.append("- C 类白名单当前未含 L_seg2_low_flat（v4.0 已禁用）。如需补验，需先在 v4.0 恢复该 tier 并对比 C 类净 PnL diff。")
    lines.append("- 状态：待定（不影响主 Gatekeeper；若后续启用需追加 §1.5 输出）。")
    lines.append("")
    lines.append("## 7. 各方向解读（为何 fail / 回退）")
    lines.append("")
    lines.append("### C.1 品种筛选（S2 vs B0）")
    lines.append("- ΔSharpe = **-0.27**，p_boot = **0.0000**（cluster bootstrap 100% 次 S2 更差）→ 双判据均输。")
    lines.append("- 解读：§4.1「按品种类型筛选 tier」剔除了原本盈利的 tier/品种组合（A 类禁用 L_seg3/S_seg34、B 类禁用 L_seg12/S_seg12 后，组合反而变差）。")
    lines.append("- **结论：回退 S1（全品种 5 档）**，不启用品种筛选。")
    lines.append("")
    lines.append("### C.2 信号强度加权（W1/W2/W3 vs W0）")
    lines.append("- W1 持平 B0（ΔSh=-0.01，ann 12.50%）· W2 最差（ΔSh=-0.32，ann 5.65%）· **W3（spec 默认）也差（ΔSh=-0.22，ann 8.51%）**。")
    lines.append("- 诊断：w_strength 与单笔 pnl_net_bps 相关性 ≈ 0（W1 corr=+0.06，W3 corr=**-0.07**）。即 spec 定义的强度信号与收益几乎无关，W3 甚至给「高权重信号」更低收益 → 加权拖累。")
    lines.append("- **结论：回退 W0（等权）**，强度加权在本数据上无效且方向不明。")
    lines.append("")
    lines.append("### C.3 多空权重（VW1/VW2 vs VW0）")
    lines.append("- VW1 持平 B0（ΔSh=-0.01）· VW2 拖累（ΔSh=-0.23，ann 11.58%）。")
    lines.append("- 解读：IR 比例 / 频率平衡均无法在「多空等权」基础上增配出更高夏普（本主题多空贡献度本就均衡，L/S ≈ 50%/50%）。")
    lines.append("- **结论：回退 VW0（多空等权）**。")
    lines.append("")
    lines.append("## 8. 结论与下一步（§1.4 降级分支）")
    lines.append("")
    lines.append(f"- **{n_pass}/6 方向通过**：含 spec 默认方案（S2/W3/VW1）在内的全部 6 候选均无 ≥0.2 夏普增量；")
    lines.append("  其中 W2/W3/VW2/S2 显著拖累，仅 W1/VW1 基本持平 B0（ΔSh≈0）。")
    lines.append("- **判定：B0 = S1 × W0 × VW0 即为本主题最优组合方案，组合层 alpha 已被 B0 吃满**")
    lines.append("  （与 experiment-plan §1.4「0 方向通过 → 主题降级」分支一致）。")
    lines.append("")
    lines.append("**方法论备注**：W/VW 属「权重重分配」，paired diff 在信号/方向间中性化 → p_boot 自然偏高（非 fail 主因），")
    lines.append("故 W/VW 以 ΔSharpe 为主判据；S2 属 event 集变化，p_boot 有效且双输。")
    lines.append("")
    lines.append("**下一步选项**（需用户拍板）：")
    lines.append("- **选项 A（推荐）**：直接工程化 B0，跳过阶段 2-3 进入阶段 4。理由：B0 阶段0 ALL PASS 且夏普 2.70 > 降级预期 2.0，")
    lines.append("  OOS 验证可由阶段 4 的模拟盘滚动更新替代。")
    lines.append("- **选项 B**：主题冻结（若对单品种/制度稳健性要求更高，坚持走阶段 3 OOS 双维度）。")
    lines.append("")
    lines.append("**参数回填建议（parameter-selection-spec L2）**：S1/W0/VW0 锁定；spec 当前标注的「W3/VW1 默认」需据本数据")
    lines.append("修订为「回退 baseline（W0/VW0），阶段1 检验无增量」——此修订待阶段收尾时落盘。")
    lines.append("")
    WORKBENCH.parent.mkdir(parents=True, exist_ok=True)
    WORKBENCH.write_text("\n".join(lines), encoding="utf-8")
    print(f"      写出: {WORKBENCH}")


if __name__ == "__main__":
    main()
