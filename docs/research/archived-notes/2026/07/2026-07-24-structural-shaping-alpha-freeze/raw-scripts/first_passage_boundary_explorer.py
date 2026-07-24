"""首达定理生效边界探索器 · First-Passage Boundary Explorer.

研究命题：
    固定盈亏比 RR = K_T/K_S 设置止盈止损，止损为 ATR 倍数 K_S。
    首达定理（λ=0）预测 P_win = 1/(1+RR)、E[gross]=0，与 K_S 绝对值无关。
    本实验通过扫描 (K_S, RR) 网格，探索实测偏离理论预测的边界。

设计：
    - 自变量：K_S ∈ 网格（ATR 倍数）、RR ∈ {0.5, 1.0, 1.5, 2.0, 3.0}
    - 因变量：实测 P_win、实测 E[net]、time_exit 概率、ΔP_win vs 理论
    - 入场：DirRandom × uniform_20bar（与 gatekeeper 一致口径）
    - 时间上限 max_bars 可选档位，检验有限 T 的影响
    - 成本：realistic（默认）或 flat 0.05 ATR

用法：
    # 默认扫描（K_S: 0.5-8.0, RR: 0.5-3.0, max_bars: 80）
    python raw-scripts/first_passage_boundary_explorer.py

    # 指定时间上限
    python raw-scripts/first_passage_boundary_explorer.py --max-bars 40,80,160

    # 快速原型（扁平成本）
    python raw-scripts/first_passage_boundary_explorer.py --flat-cost-debug
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from common.contract_specs import CONTRACT_SPECS, ContractSpec
from data.output_paths import market_csv_dir, project_data_root

Side = Literal[1, -1]

# ────────────────────── 品种覆盖 ──────────────────────
SYMBOLS: list[tuple[str, str, str]] = [
    ("black", "rb2601", "SHFE.rb2601"),
    ("black", "rb2605", "SHFE.rb2605"),
    ("black", "i2601", "DCE.i2601"),
    ("black", "i2509", "DCE.i2509"),
    ("metals", "cu2601", "SHFE.cu2601"),
    ("metals", "cu2509", "SHFE.cu2509"),
    ("metals", "al2601", "SHFE.al2601"),
    ("metals", "al2509", "SHFE.al2509"),
    ("energy_chem", "sc2512", "INE.sc2512"),
    ("energy_chem", "sc2509", "INE.sc2509"),
    ("energy_chem", "TA601", "CZCE.TA601"),
    ("energy_chem", "TA509", "CZCE.TA509"),
    ("agri_dce", "m2601", "DCE.m2601"),
    ("agri_dce", "m2605", "DCE.m2605"),
    ("agri_dce", "p2601", "DCE.p2601"),
    ("agri_dce", "p2605", "DCE.p2605"),
    ("agri_czce", "SR601", "CZCE.SR601"),
    ("agri_czce", "SR605", "CZCE.SR605"),
    ("agri_czce", "CF601", "CZCE.CF601"),
    ("agri_czce", "CF509", "CZCE.CF509"),
]

# ────────────────────── 常量 ──────────────────────
COST_PER_TRADE_ATR_FLAT = 0.05  # 扁平成本基准（仅 debug）
ATR_PERIOD = 14
SAMPLING_STRIDE = 20  # uniform_20bar
DIR_RANDOM_SEED = 20260714  # 固定种子
BOOTSTRAP_ITER = 5000

# 每 bar 波动率（ATR 归一化），按 interval 匹配。
# 5m: σ ≈ 1.0/√12 ≈ 0.289；15m: 1.0/√4 = 0.5；1h: 1.0/√1 = 1.0
# 这里用"每小时 σ=1 ATR"作为对齐基准——保证 T*=(K_S,K_T)²/σ² 在物理时间上跨周期可比。
SIGMA_PER_BAR_BY_INTERVAL: dict[str, float] = {
    "5m": 1.0 / math.sqrt(12),  # ≈ 0.2887
    "15m": 1.0 / math.sqrt(4),  # = 0.5
    "1h": 1.0,
}

# ────────────────────── 默认扫描网格 ──────────────────────
DEFAULT_K_S_GRID = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
DEFAULT_RR_GRID = [0.5, 1.0, 1.5, 2.0, 3.0]
DEFAULT_MAX_BARS_GRID = [80]


def realistic_cost_atr_per_side(spec: ContractSpec, entry_price: float, entry_atr_price: float) -> float:
    """按实际合约规格计算单笔单边成本占 entry_atr 的比例。"""
    commission_yuan = spec.total_commission(price=entry_price, lots=1)
    slippage_yuan = spec.slippage(lots=1)
    cost_yuan_per_side = commission_yuan + slippage_yuan
    atr_yuan = entry_atr_price * max(spec.size, 1)
    if atr_yuan <= 0:
        return COST_PER_TRADE_ATR_FLAT
    return cost_yuan_per_side / atr_yuan


# ────────────────────── 数据加载 ──────────────────────

def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    atr = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["atr"] = atr
    df["session_date"] = df["datetime"].dt.date
    return df


# ────────────────────── 事件生成 ──────────────────────

@dataclass(frozen=True)
class Event:
    symbol: str
    sector: str
    entry_idx: int
    side: Side
    entry_price: float
    entry_atr: float
    session_date: object


def make_events(sector: str, symbol: str, df: pd.DataFrame, rng: random.Random) -> list[Event]:
    events: list[Event] = []
    n = len(df)
    first = ATR_PERIOD
    for i in range(first, n - 1, SAMPLING_STRIDE):
        entry_idx = i + 1
        if entry_idx >= n:
            break
        entry_atr = df["atr"].iat[i]
        if not math.isfinite(entry_atr) or entry_atr <= 0:
            continue
        entry_price = df["open"].iat[entry_idx]
        if not math.isfinite(entry_price):
            continue
        side: Side = 1 if rng.random() < 0.5 else -1
        events.append(Event(
            symbol=symbol, sector=sector,
            entry_idx=entry_idx, side=side,
            entry_price=float(entry_price), entry_atr=float(entry_atr),
            session_date=df["session_date"].iat[entry_idx],
        ))
    return events


# ────────────────────── 出场模拟 ──────────────────────

@dataclass
class TradeOutcome:
    exit_reason: str  # stop / take / time_exit / data_end
    exit_bars: int
    net_atr: float
    gross_atr: float


def simulate_trade(event: Event, df: pd.DataFrame,
                   stop_atr: float, take_atr: float, max_bars: int,
                   cost_atr_per_side: float) -> TradeOutcome:
    """极简固定 SL/TP 出场模拟，无 trailing / EOD 等复杂逻辑。"""
    side = event.side
    entry = event.entry_price
    atr = event.entry_atr
    stop_dist = stop_atr * atr
    take_dist = take_atr * atr
    stop_price = entry - side * stop_dist
    take_price = entry + side * take_dist
    two_way_cost = 2 * cost_atr_per_side
    n = len(df)

    for step in range(1, max_bars + 1):
        j = event.entry_idx + step
        if j >= n:
            j = n - 1
            close_j = df["close"].iat[j]
            gross = side * (close_j - entry) / atr
            net = gross - two_way_cost
            return TradeOutcome("data_end", step, float(net), float(gross))

        high_j = df["high"].iat[j]
        low_j = df["low"].iat[j]

        stop_hit = (low_j <= stop_price) if side == 1 else (high_j >= stop_price)
        take_hit = (high_j >= take_price) if side == 1 else (low_j <= take_price)

        if stop_hit:
            gross = side * (stop_price - entry) / atr
            return TradeOutcome("stop", step, float(gross - two_way_cost), float(gross))
        if take_hit:
            gross = side * (take_price - entry) / atr
            return TradeOutcome("take", step, float(gross - two_way_cost), float(gross))

    # 时间上限到期
    j = min(event.entry_idx + max_bars, n - 1)
    exit_price = df["close"].iat[j]
    gross = side * (exit_price - entry) / atr
    net = gross - two_way_cost
    return TradeOutcome("time_exit", max_bars, float(net), float(gross))


# ────────────────────── 首达定理理论预测 ──────────────────────

def first_passage_theory(K_S: float, K_T: float, sigma: float, T: float, mu: float = 0.0, cost: float = 0.05) -> dict:
    """计算首达定理的理论预测值。

    两条理论线：
    1. FPT（λ=0，纯首达定理）：P_win = K_S/(K_S+K_T) = 1/(1+RR)，E[net] = -2c
       → 这是"边界探索"的零假设（null hypothesis）
    2. GBM（μ=0）：含 Itô 凸性修正的 Gerstein-Ito 公式
       → 用于归因：实测偏离 FPT 多少来自 GBM 自身的凸性

    sigma 用于 T_star 和 time_exit Fourier 近似，不影响 P_win_infty（λ=0 分支）。
    """
    # ── FPT 零假设（λ=0）──
    P_win_fpt = K_S / (K_S + K_T)
    E_gross_fpt = 0.0  # 首达定理恒等式
    E_net_fpt = -2 * cost

    # ── GBM μ=0（含 Itô 凸性, λ=-1）──
    nu = mu - sigma**2 / 2
    lam = 2 * nu / sigma**2 if sigma > 0 else 0.0

    tol = 1e-6
    if abs(lam) < tol:
        P_win_gbm = K_S / (K_S + K_T)
    else:
        if abs(lam * K_T) > 50 or abs(lam * K_S) > 50:
            P_win_gbm = 1.0 if lam > 0 else 0.0
        else:
            num = math.exp(lam * K_T) * (1 - math.exp(-lam * K_S))
            den = math.exp(lam * K_T) - math.exp(-lam * K_S)
            P_win_gbm = num / den if abs(den) > tol else K_S / (K_S + K_T)
    P_loss_gbm = 1 - P_win_gbm
    E_gross_gbm = P_win_gbm * K_T - P_loss_gbm * K_S
    E_net_gbm = E_gross_gbm - 2 * cost

    # 短期/长期分界
    T_star = (max(K_S, K_T) ** 2) / (sigma**2) if sigma > 0 else float("inf")

    # 有限 T 的 time_exit 概率（Fourier 级数，λ=0，5 项）
    P_time_exit_approx = _p_time_exit_fourier(K_S, K_T, sigma, T)

    return {
        "P_win_fpt": P_win_fpt,
        "E_net_fpt": E_net_fpt,
        "E_gross_fpt": E_gross_fpt,
        "P_win_gbm": P_win_gbm,
        "E_net_gbm": E_net_gbm,
        "E_gross_gbm": E_gross_gbm,
        "T_star": T_star,
        "P_time_exit_fourier": P_time_exit_approx,
        "lam": lam,
        "nu": nu,
    }


def _p_time_exit_fourier(K_S: float, K_T: float, sigma: float, T: float) -> float:
    """λ=0 时有限 T 的 time_exit 概率（Fourier 级数前 5 项近似）。"""
    if sigma <= 0 or T <= 0 or K_S + K_T <= 0:
        return 0.0
    total = 0.0
    L = K_S + K_T
    for n in range(5):
        k = 2 * n + 1
        term = (1.0 / k) * math.sin(k * math.pi * K_S / L)
        term *= math.exp(-(k**2) * (math.pi**2) * (sigma**2) * T / (2 * L**2))
        total += term
    return 4.0 / math.pi * total


# ────────────────────── 统计 ──────────────────────

@dataclass
class GridResult:
    K_S: float
    K_T: float
    RR: float
    max_bars: int
    n_events: int
    # 实测
    P_win_obs: float
    P_loss_obs: float
    P_time_exit_obs: float
    E_net_obs: float
    E_gross_obs: float
    median_net_obs: float
    mean_exit_bars: float
    # FPT 理论（λ=0 零假设）
    P_win_fpt: float   # 1/(1+RR)
    E_net_fpt: float   # -2c
    # GBM μ=0 理论（含 Itô 凸性）
    P_win_gbm: float
    E_net_gbm: float
    E_gross_gbm: float
    # 偏差（vs FPT 零假设）
    P_win_deviation: float  # obs - fpt
    E_net_deviation: float  # obs - fpt
    # 其他
    T_star: float
    P_time_exit_theory: float
    # 显著性
    bootstrap_ci_lo: float = 0.0
    bootstrap_ci_hi: float = 0.0
    bootstrap_p_gt_0: float = 1.0


def cluster_bootstrap_mean(values_by_contract: dict[str, list[float]], n_iter: int, rng: np.random.Generator):
    contracts = list(values_by_contract.keys())
    if not contracts:
        return 0.0, 0.0, 0.0
    means = []
    n_contracts = len(contracts)
    for _ in range(n_iter):
        sampled = rng.choice(n_contracts, size=n_contracts, replace=True)
        collected: list[float] = []
        for idx in sampled:
            collected.extend(values_by_contract[contracts[idx]])
        means.append(float(np.mean(collected)) if collected else 0.0)
    arr = np.asarray(means)
    return float(arr.mean()), float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def bootstrap_p_gt_0(values_by_contract: dict[str, list[float]], n_iter: int, rng: np.random.Generator) -> float:
    """单侧 H1: mean > 0 的 bootstrap p-value。"""
    contracts = list(values_by_contract.keys())
    if not contracts:
        return 1.0
    n_contracts = len(contracts)
    n_ge0 = 0
    for _ in range(n_iter):
        sampled = rng.choice(n_contracts, size=n_contracts, replace=True)
        collected: list[float] = []
        for idx in sampled:
            collected.extend(values_by_contract[contracts[idx]])
        if collected and float(np.mean(collected)) > 0:
            n_ge0 += 1
    return 1.0 - n_ge0 / n_iter


# ────────────────────── μ_implied 反算（math spec §4.1）──────────────────────

def _p_win_infty_given_lam(lam: float, K_S: float, K_T: float) -> float:
    """§2.3: 首达止盈概率（λ≠0 分支的 Gerstein-Ito 公式）。"""
    tol = 1e-10
    if abs(lam) < tol:
        return K_S / (K_S + K_T)
    arg_s = -lam * K_S
    arg_t = lam * K_T
    if arg_t > 50 or arg_s > 50:
        return 1.0 if lam > 0 else 0.0
    if arg_t < -50 or arg_s < -50:
        return 0.0 if lam > 0 else 1.0
    num = math.exp(arg_t) * (1 - math.exp(arg_s))
    den = math.exp(arg_t) - math.exp(arg_s)
    if abs(den) < tol:
        return K_S / (K_S + K_T)
    return num / den


def _solve_implied_drift(P_win_obs: float, K_S: float, K_T: float,
                         sigma_per_bar: float,
                         lam_range: tuple = (-3.0, 3.0),
                         ) -> tuple[float, float, float]:
    """从实测 P_win 反解隐含 ν 和 μ（math spec §4.1）。

    返回 (ν_implied, μ_implied, λ_implied)。
    若 P_win_obs 超出 [0, 1] 或 brentq 不收敛，返回 (nan, nan, nan).
    """
    import math as _math
    if P_win_obs <= 0 or P_win_obs >= 1:
        return (float("nan"), float("nan"), float("nan"))
    try:
        f = lambda lam: _p_win_infty_given_lam(lam, K_S, K_T) - P_win_obs
        # 尝试两端符号不同
        lo, hi = lam_range
        f_lo, f_hi = f(lo), f(hi)
        # 扩展搜索范围
        for expand_lo, expand_hi in [(-5.0, 5.0), (-10.0, 10.0)]:
            if f_lo * f_hi < 0:
                break
            lo, hi = expand_lo, expand_hi
            f_lo, f_hi = f(lo), f(hi)
        if f_lo * f_hi >= 0:
            return (float("nan"), float("nan"), float("nan"))
        lam = brentq(f, lo, hi, xtol=1e-10)
        nu = lam * sigma_per_bar**2 / 2
        mu = nu + sigma_per_bar**2 / 2
        return (nu, mu, lam)
    except (ValueError, RuntimeError):
        return (float("nan"), float("nan"), float("nan"))


# ────────────────────── 主流程 ──────────────────────

def main() -> None:
    args = _parse_args()
    k_s_grid = [float(x) for x in args.k_s_grid.split(",")]
    rr_grid = [float(x) for x in args.rr_grid.split(",")]
    max_bars_grid = [int(x) for x in args.max_bars.split(",")]
    use_realistic_cost = not args.flat_cost_debug
    interval = args.interval
    if interval not in SIGMA_PER_BAR_BY_INTERVAL:
        raise SystemExit(f"[error] unsupported interval: {interval} (supported: {list(SIGMA_PER_BAR_BY_INTERVAL)})")

    csv_dir = market_csv_dir()
    out_dir = project_data_root() / "research" / "first_passage_boundary"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rng_dir = random.Random(DIR_RANDOM_SEED)
    rng_np = np.random.default_rng(DIR_RANDOM_SEED)

    all_events: list[Event] = []
    trades: list[dict] = []  # 每笔交易记录
    symbol_stats: list[dict] = []

    # 每 bar 波动率（按 interval 查表），单位：ATR / √bar
    # 5m σ ≈ 0.289；15m σ = 0.5；1h σ = 1.0——用"每小时 σ=1 ATR"对齐 T* 物理时间
    SIGMA_PER_BAR = SIGMA_PER_BAR_BY_INTERVAL[interval]

    print(f"周期: {interval} · σ_per_bar = {SIGMA_PER_BAR:.4f}")
    print(f"网格: K_S = {k_s_grid} ({len(k_s_grid)}档)")
    print(f"      RR  = {rr_grid} ({len(rr_grid)}档)")
    print(f"      max_bars = {max_bars_grid} ({len(max_bars_grid)}档)")
    print(f"总 combo: {len(k_s_grid) * len(rr_grid) * len(max_bars_grid)}")
    print(f"成本模型: {'realistic' if use_realistic_cost else 'flat 0.05 ATR'}")
    print()

    for sector, symbol, symbol_prefix in SYMBOLS:
        csv_file = f"{symbol_prefix}.tqsdk.{interval}.csv"
        path = csv_dir / csv_file
        if not path.exists():
            print(f"[skip] missing csv: {path}")
            continue
        df = load_bars(path)
        events = make_events(sector, symbol, df, rng_dir)
        all_events.extend(events)

        symbol_full = symbol_prefix  # "SHFE.rb2601" 等（已是完整格式）
        spec = CONTRACT_SPECS.get_symbol(symbol_full) if use_realistic_cost else None

        cost_stats: list[float] = []
        for max_bars in max_bars_grid:
            for rr in rr_grid:
                for k_s in k_s_grid:
                    k_t = rr * k_s
                    for ev in events:
                        if use_realistic_cost and spec is not None:
                            cost_side = realistic_cost_atr_per_side(spec, ev.entry_price, ev.entry_atr)
                        else:
                            cost_side = COST_PER_TRADE_ATR_FLAT
                        outcome = simulate_trade(ev, df, k_s, k_t, max_bars, cost_side)
                        trades.append({
                            "K_S": k_s, "K_T": k_t, "RR": rr, "max_bars": max_bars,
                            "symbol": symbol, "sector": sector,
                            "entry_idx": ev.entry_idx, "side": int(ev.side),
                            "entry_price": ev.entry_price, "entry_atr": ev.entry_atr,
                            "exit_reason": outcome.exit_reason, "exit_bars": outcome.exit_bars,
                            "net_atr": outcome.net_atr, "gross_atr": outcome.gross_atr,
                            "cost_atr_side": cost_side,
                        })
                    # 只记一次成本统计
                    cost_stats.append(cost_side if not cost_stats else cost_stats[0])

        avg_cost = float(np.mean(cost_stats)) if cost_stats else COST_PER_TRADE_ATR_FLAT
        symbol_stats.append({
            "sector": sector, "symbol": symbol, "bars": len(df), "events": len(events),
            "avg_cost_atr_side": avg_cost,
        })
        print(f"[ok] {sector:12s} {symbol:8s} bars={len(df):5d} events={len(events):4d} avg_cost={avg_cost:.4f}")

    # ── 按 (K_S, RR, max_bars) 汇总 ──
    group_keys = [(k_s, rr, mb) for mb in max_bars_grid for rr in rr_grid for k_s in k_s_grid]
    results: list[GridResult] = []

    # 按 key 索引所有 trades
    trades_by_group: dict[tuple, list[dict]] = {}
    for t in trades:
        key = (t["K_S"], t["RR"], t["max_bars"])
        trades_by_group.setdefault(key, []).append(t)

    avg_cost_side = float(np.mean([s["avg_cost_atr_side"] for s in symbol_stats]))

    for (k_s, rr, mb) in group_keys:
        group_trades = trades_by_group.get((k_s, rr, mb), [])
        if not group_trades:
            continue

        nets = [t["net_atr"] for t in group_trades]
        grosses = [t["gross_atr"] for t in group_trades]
        reasons: dict[str, int] = {}
        for t in group_trades:
            reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
        n_total = len(group_trades)
        n_win = reasons.get("take", 0)
        n_loss = reasons.get("stop", 0)
        n_time = reasons.get("time_exit", 0) + reasons.get("data_end", 0)

        # 理论计算
        theory = first_passage_theory(
            K_S=k_s, K_T=rr * k_s,
            sigma=SIGMA_PER_BAR,
            T=mb,  # bar 数作为时间
            mu=0.0,
            cost=avg_cost_side,
        )

        # bootstrap CI for E[net]
        net_by_contract: dict[str, list[float]] = {}
        for t in group_trades:
            net_by_contract.setdefault(t["symbol"], []).append(t["net_atr"])
        _, ci_lo, ci_hi = cluster_bootstrap_mean(net_by_contract, BOOTSTRAP_ITER, rng_np)
        p_val = bootstrap_p_gt_0(net_by_contract, BOOTSTRAP_ITER, rng_np)

        p_win_obs_val = n_win / n_total if n_total else 0
        e_net_obs_val = float(np.mean(nets)) if nets else 0.0

        # μ_implied 反算（math spec §4.1）: 从实测 P_win 反解 ν
        nu_implied, mu_implied, lam_implied = _solve_implied_drift(
            p_win_obs_val, k_s, rr * k_s, SIGMA_PER_BAR,
        )

        result = GridResult(
            K_S=k_s,
            K_T=rr * k_s,
            RR=rr,
            max_bars=mb,
            n_events=n_total,
            P_win_obs=p_win_obs_val,
            P_loss_obs=n_loss / n_total if n_total else 0,
            P_time_exit_obs=n_time / n_total if n_total else 0,
            E_net_obs=e_net_obs_val,
            E_gross_obs=float(np.mean(grosses)) if grosses else 0.0,
            median_net_obs=float(np.median(nets)) if nets else 0.0,
            mean_exit_bars=float(np.mean([t["exit_bars"] for t in group_trades])) if group_trades else 0.0,
            # FPT 理论（λ=0 零假设）
            P_win_fpt=theory["P_win_fpt"],
            E_net_fpt=theory["E_net_fpt"],
            # GBM μ=0 理论（含 Itô 凸性）
            P_win_gbm=theory["P_win_gbm"],
            E_net_gbm=theory["E_net_gbm"],
            E_gross_gbm=theory["E_gross_gbm"],
            # 偏差 vs FPT 零假设
            P_win_deviation=p_win_obs_val - theory["P_win_fpt"],
            E_net_deviation=e_net_obs_val - theory["E_net_fpt"],
            T_star=theory["T_star"],
            P_time_exit_theory=theory["P_time_exit_fourier"],
            bootstrap_ci_lo=ci_lo,
            bootstrap_ci_hi=ci_hi,
            bootstrap_p_gt_0=p_val,
        )
        results.append(result)

    # ── 输出 ──
    # CSV 明细
    cost_tag = "realcost" if use_realistic_cost else "flat005"
    file_tag = f"{cost_tag}_{interval}"
    csv_path = out_dir / f"boundary_explorer_{file_tag}_{timestamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "K_S", "K_T", "RR", "max_bars", "n_events",
            "P_win_obs", "P_loss_obs", "P_time_exit_obs",
            "E_net_obs", "E_gross_obs", "median_net_obs", "mean_exit_bars",
            "P_win_fpt", "P_win_gbm", "P_win_deviation",
            "E_net_fpt", "E_net_gbm", "E_gross_gbm", "E_net_deviation",
            "T_star", "T_star_ratio", "T_star_regime",
            "P_time_exit_theory",
            "bootstrap_ci_lo", "bootstrap_ci_hi", "bootstrap_p_gt_0",
        ]
        writer.writerow(header)
        for r in results:
            t_star_ratio = r.max_bars / r.T_star if r.T_star > 0 else float("inf")
            # T* 分区（math spec §2.7）
            if t_star_ratio < 0.3:
                regime = "short_term"
            elif t_star_ratio < 3.0:
                regime = "transition"
            else:
                regime = "long_term"
            writer.writerow([
                f"{r.K_S:.2f}", f"{r.K_T:.2f}", f"{r.RR:.2f}", r.max_bars, r.n_events,
                f"{r.P_win_obs:.6f}", f"{r.P_loss_obs:.6f}", f"{r.P_time_exit_obs:.6f}",
                f"{r.E_net_obs:.6f}", f"{r.E_gross_obs:.6f}", f"{r.median_net_obs:.6f}", f"{r.mean_exit_bars:.2f}",
                f"{r.P_win_fpt:.6f}", f"{r.P_win_gbm:.6f}", f"{r.P_win_deviation:.6f}",
                f"{r.E_net_fpt:.6f}", f"{r.E_net_gbm:.6f}", f"{r.E_gross_gbm:.6f}", f"{r.E_net_deviation:.6f}",
                f"{r.T_star:.2f}", f"{t_star_ratio:.4f}", regime,
                f"{r.P_time_exit_theory:.6f}",
                f"{r.bootstrap_ci_lo:.6f}", f"{r.bootstrap_ci_hi:.6f}", f"{r.bootstrap_p_gt_0:.6f}",
            ])

    # 全量成交 CSV
    trades_csv_path = out_dir / f"boundary_explorer_trades_{file_tag}_{timestamp}.csv"
    with trades_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["K_S", "K_T", "RR", "max_bars", "symbol", "sector", "entry_idx", "side",
                          "entry_price", "entry_atr", "exit_reason", "exit_bars", "net_atr", "gross_atr"])
        for t in trades:
            writer.writerow([t["K_S"], t["K_T"], t["RR"], t["max_bars"],
                             t["symbol"], t["sector"], t["entry_idx"], t["side"],
                             f"{t['entry_price']:.4f}", f"{t['entry_atr']:.4f}",
                             t["exit_reason"], t["exit_bars"],
                             f"{t['net_atr']:.6f}", f"{t['gross_atr']:.6f}"])

    # JSON summary
    summary = {
        "timestamp": timestamp,
        "config": {
            "k_s_grid": k_s_grid,
            "rr_grid": rr_grid,
            "max_bars_grid": max_bars_grid,
            "cost_model": cost_tag,
            "interval": interval,
            "avg_cost_atr_side": avg_cost_side,
            "sigma_per_bar": SIGMA_PER_BAR,
            "sampling_stride": SAMPLING_STRIDE,
            "atr_period": ATR_PERIOD,
            "seed": DIR_RANDOM_SEED,
            "bootstrap_iter": BOOTSTRAP_ITER,
        },
        "symbols": symbol_stats,
        "total_events": len(all_events),
        "total_trades": len(trades),
        "n_combos": len(results),
        "results": [
            {
                "K_S": r.K_S, "K_T": r.K_T, "RR": r.RR, "max_bars": r.max_bars,
                "n_events": r.n_events,
                "P_win_obs": r.P_win_obs, "P_loss_obs": r.P_loss_obs, "P_time_exit_obs": r.P_time_exit_obs,
                "E_net_obs": r.E_net_obs, "E_gross_obs": r.E_gross_obs,
                "median_net_obs": r.median_net_obs, "mean_exit_bars": r.mean_exit_bars,
                # 两条理论线
                "P_win_fpt": r.P_win_fpt, "E_net_fpt": r.E_net_fpt,
                "P_win_gbm": r.P_win_gbm, "E_net_gbm": r.E_net_gbm, "E_gross_gbm": r.E_gross_gbm,
                # 偏差 vs FPT
                "P_win_deviation": r.P_win_deviation, "E_net_deviation": r.E_net_deviation,
                "T_star": r.T_star, "T_star_ratio": r.max_bars / r.T_star if r.T_star > 0 else float("inf"),
                "P_time_exit_theory": r.P_time_exit_theory,
                "bootstrap_ci_lo": r.bootstrap_ci_lo, "bootstrap_ci_hi": r.bootstrap_ci_hi,
                "bootstrap_p_gt_0": r.bootstrap_p_gt_0,
            }
            for r in results
        ],
    }
    json_path = out_dir / f"boundary_explorer_{file_tag}_{timestamp}.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"\n{'='*70}")
    print(f"完成: {len(results)} 个 combo 已评估")
    print(f"CSV (汇总): {csv_path}")
    print(f"CSV (明细): {trades_csv_path}")
    print(f"JSON:       {json_path}")

    # ── 快速边界诊断 ──
    _print_boundary_diagnostics(results, k_s_grid, rr_grid, max_bars_grid)


def _print_boundary_diagnostics(results: list[GridResult], k_s_grid, rr_grid, max_bars_grid):
    """打印边界诊断概览（FPT vs GBM μ=0 双重零假设）。"""
    print(f"\n{'='*70}")
    print("边界诊断概览 · FPT (λ=0) vs GBM (μ=0) 双重 null")
    print(f"{'='*70}")

    for mb in max_bars_grid:
        print(f"\n--- max_bars = {mb} ---")
        for rr in rr_grid:
            subset = [r for r in results if abs(r.RR - rr) < 0.001 and r.max_bars == mb]
            subset.sort(key=lambda r: r.K_S)
            if not subset:
                continue
            r0 = subset[0]
            print(f"\n  RR={rr:.1f} | 理论 P_win: FPT(λ=0)={r0.P_win_fpt:.4f}  GBM(μ=0)={r0.P_win_gbm:.4f}  Δ={r0.P_win_gbm - r0.P_win_fpt:+.4f}")
            print(f"  {'K_S':>6s}  {'T_star':>8s}  {'T_star_regime':>14s}  {'P_win_obs':>10s}  {'vs FPT':>8s}  {'vs GBM':>8s}  {'E_net_obs':>10s}  {'E_net_fpt':>10s}  {'E_net_gbm':>10s}  {'P_time':>8s}")
            print(f"  {'-'*6}  {'-'*8}  {'-'*14}  {'-'*10}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*8}")
            for r in subset:
                t_star_ratio = r.max_bars / r.T_star if r.T_star > 0 else float("inf")
                if t_star_ratio < 0.3:
                    regime = "short"
                elif t_star_ratio < 3.0:
                    regime = "transition"
                else:
                    regime = "long"
                vs_fpt = r.P_win_obs - r.P_win_fpt
                vs_gbm = r.P_win_obs - r.P_win_gbm
                # 标记：实测更接近哪条理论线
                if abs(vs_fpt) < abs(vs_gbm):
                    alignment = "FPT"
                else:
                    alignment = "GBM"
                dev_marker = " **" if abs(vs_fpt) > 0.05 else ""
                print(f"  {r.K_S:6.2f}  {r.T_star:8.1f}  {regime:>14s}  {r.P_win_obs:10.4f}  {vs_fpt:+8.4f}{dev_marker}  {vs_gbm:+8.4f}  "
                      f"{r.E_net_obs:10.4f}  {r.E_net_fpt:10.4f}  {r.E_net_gbm:10.4f}  {r.P_time_exit_obs:8.4f}  {alignment}")
        # 打印该 RR 下偏差最小的 K_S 区间
        best_fpt = min(subset, key=lambda r: abs(r.P_win_obs - r.P_win_fpt))
        best_gbm = min(subset, key=lambda r: abs(r.P_win_obs - r.P_win_gbm))
        print(f"  → 最接近 FPT: K_S={best_fpt.K_S:.2f} (Δ={best_fpt.P_win_obs - best_fpt.P_win_fpt:+.4f})")
        print(f"  → 最接近 GBM: K_S={best_gbm.K_S:.2f} (Δ={best_gbm.P_win_obs - best_gbm.P_win_gbm:+.4f})")

    # ── 全局总结：K_S 在哪个区间 FPT/GBM 分别最准 ──
    print(f"\n{'='*70}")
    print("全局总结: 各 RR 下偏差最小的 K_S 区间")
    print(f"{'='*70}")
    for rr in rr_grid:
        subset_all = [r for r in results if abs(r.RR - rr) < 0.001]
        if not subset_all:
            continue
        best_fpt = min(subset_all, key=lambda r: abs(r.P_win_obs - r.P_win_fpt))
        best_gbm = min(subset_all, key=lambda r: abs(r.P_win_obs - r.P_win_gbm))
        print(f"  RR={rr:.1f}: FPT最佳 K_S={best_fpt.K_S:.2f} (Δ={best_fpt.P_win_obs - best_fpt.P_win_fpt:+.4f})  "
              f"GBM最佳 K_S={best_gbm.K_S:.2f} (Δ={best_gbm.P_win_obs - best_gbm.P_win_gbm:+.4f})")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="首达定理生效边界探索器")
    parser.add_argument("--interval", type=str, default="5m",
                        choices=["5m", "15m", "1h"],
                        help="K 线周期（对应 CSV 文件名中的 interval 字段，默认 5m）")
    parser.add_argument("--k-s-grid", type=str, default="0.5,0.75,1.0,1.25,1.5,2.0,2.5,3.0,4.0,5.0,6.0,7.0,8.0",
                        help="K_S 网格（逗号分隔，默认 0.5-8.0）")
    parser.add_argument("--rr-grid", type=str, default="0.5,1.0,1.5,2.0,3.0",
                        help="盈亏比网格（逗号分隔，默认 0.5-3.0）")
    parser.add_argument("--max-bars", type=str, default="80",
                        help="时间上限 bar 数（逗号分隔，默认 80）")
    parser.add_argument("--flat-cost-debug", action="store_true",
                        help="回退到扁平成本模型 0.05 ATR/单边")
    return parser.parse_args()


if __name__ == "__main__":
    main()
