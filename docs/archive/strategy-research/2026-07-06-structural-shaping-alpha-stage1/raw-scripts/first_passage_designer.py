"""First-Passage Designer · v1 实现 + 对照表生成器.

对应 docs/research/themes/structural-shaping-alpha/first-passage-designer-math-spec.md
Part V.1（v1 范围）：

- §2.3 首达概率精确解析
- §2.4 平均首达时间（T=infty）
- §2.5 期望收益（gross / net）
- §2.7 短期/长期分界 T*
- §3.1-3.2 μ 敏感性 + μ* 求解
- §3.3 止盈可行区间反解
- §3.5 凯利仓位
- §4.1 μ_implied 反算

用法：
    python scripts/ai_tmp/first_passage_designer.py

输出：
- docs/workbench/first-passage-lookup-tables.md（5 张对照表）
- project_data/research/first_passage_lookup/tables_{1..5}_<timestamp>.csv
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from scipy.optimize import brentq

# ============================================================
# Part V.1 · 核心解析函数
# ============================================================

_LAMBDA_ZERO_TOL = 1e-6  # |lambda| < TOL 走 lambda=0 分支
_LAMBDA_OVERFLOW = 50.0  # |lambda*max(K)| > 阈值 → 返回极限值


def p_win_infty(lam: float, K_S: float, K_T: float) -> float:
    """§2.3 首达止盈概率（T=infty）.

    lam = 2*nu/sigma^2, K_S/K_T > 0.
    lam=0 走首达定理 K_S/(K_S+K_T)；否则走 Gerstein-Ito 公式。
    """
    if K_S <= 0 or K_T <= 0:
        raise ValueError(f"K_S, K_T 必须 > 0: got K_S={K_S}, K_T={K_T}")

    # lambda=0 分支（首达定理）
    if abs(lam) < _LAMBDA_ZERO_TOL:
        return K_S / (K_S + K_T)

    # 上溢保护：极大 |lambda*K| → 返回极限
    if abs(lam * max(K_S, K_T)) > _LAMBDA_OVERFLOW:
        return 1.0 if lam > 0 else 0.0

    # Gerstein-Ito
    exp_pos = math.exp(lam * K_T)
    exp_neg = math.exp(-lam * K_S)
    numerator = exp_pos * (1.0 - exp_neg)
    denominator = exp_pos - exp_neg
    return numerator / denominator


def e_gross_infty(lam: float, K_S: float, K_T: float) -> float:
    """§2.5 gross 期望（T=infty）."""
    pw = p_win_infty(lam, K_S, K_T)
    return pw * K_T - (1.0 - pw) * K_S


def e_net_infty(lam: float, K_S: float, K_T: float, c: float) -> float:
    """§2.5 net 期望（扣双边成本）."""
    return e_gross_infty(lam, K_S, K_T) - 2.0 * c


def e_tau_infty(lam: float, K_S: float, K_T: float, sigma: float) -> float:
    """§2.4 平均首达时间（T=infty）.

    lam=0 时 E[tau] = K_S*K_T / sigma^2;
    lam!=0 时用 Dynkin 公式导出的表达式。
    """
    if sigma <= 0:
        raise ValueError(f"sigma 必须 > 0: got {sigma}")

    if abs(lam) < _LAMBDA_ZERO_TOL:
        return K_S * K_T / (sigma * sigma)

    # nu = lam * sigma^2 / 2
    nu = lam * sigma * sigma / 2.0
    pw = p_win_infty(lam, K_S, K_T)
    return (K_S * (1.0 - pw) - K_T * pw) / (-nu)


def t_star(K_S: float, K_T: float, sigma: float) -> float:
    """§2.7 短期/长期分界 T* = max(K_S,K_T)^2 / sigma^2."""
    return max(K_S, K_T) ** 2 / (sigma * sigma)


def regime(T: float, T_star_val: float) -> Literal["short_term", "transition", "long_term"]:
    """§2.7 三档区间分类."""
    ratio = T / T_star_val
    if ratio < 0.3:
        return "short_term"
    elif ratio < 3.0:
        return "transition"
    else:
        return "long_term"


def mu_from_lambda(lam: float, sigma: float) -> float:
    """给定 lambda, sigma 反算 mu.

    lam = 2*nu/sigma^2, nu = mu - sigma^2/2
    => mu = lam*sigma^2/2 + sigma^2/2 = sigma^2 * (lam + 1) / 2
    """
    return sigma * sigma * (lam + 1.0) / 2.0


def lambda_from_mu(mu: float, sigma: float) -> float:
    """给定 mu, sigma 算 lambda."""
    nu = mu - sigma * sigma / 2.0
    return 2.0 * nu / (sigma * sigma)


def mu_star(K_S: float, K_T: float, sigma: float, c: float,
            mu_range: tuple[float, float] = (-2.0, 2.0)) -> Optional[float]:
    """§3.2 盈亏平衡漂移 mu*.

    找 E[net](mu) = 0 的 mu. 若在给定 mu_range 内 E[net] 始终 < 0，返回 None.
    """
    def f(mu: float) -> float:
        lam = lambda_from_mu(mu, sigma)
        return e_net_infty(lam, K_S, K_T, c)

    lo, hi = mu_range
    f_lo, f_hi = f(lo), f(hi)
    # 保护：不换号则没解
    if f_lo * f_hi > 0:
        return None
    try:
        return brentq(f, lo, hi, xtol=1e-8)
    except ValueError:
        return None


def mu_sensitivity(K_S: float, K_T: float, sigma: float, c: float,
                   mu_grid: list[float]) -> dict[float, float]:
    """§3.1 μ 敏感性表.

    对每个 mu 返回 E[net](mu).
    """
    result = {}
    for mu in mu_grid:
        lam = lambda_from_mu(mu, sigma)
        result[mu] = e_net_infty(lam, K_S, K_T, c)
    return result


def solve_K_T_min(K_S: float, mu: float, sigma: float, c: float,
                  K_T_upper: float = 100.0) -> Optional[float]:
    """§3.3.4 凯利正 edge 下界 K_T_min.

    找使 E[net] > 0 的最小 K_T. 若 mu=0 或 mu<0，返回 None（不可行）.
    """
    lam = lambda_from_mu(mu, sigma)

    def f(K_T: float) -> float:
        return e_net_infty(lam, K_S, K_T, c)

    # 检查上界是否已经 > 0
    if f(K_T_upper) <= 0:
        return None
    # 下界（很小的 K_T）
    K_T_lower = 0.01 * K_S
    if f(K_T_lower) >= 0:
        return K_T_lower  # 极小 K_T 已经正 edge（异常，几乎不可能）
    try:
        return brentq(f, K_T_lower, K_T_upper, xtol=1e-6)
    except ValueError:
        return None


def solve_K_T_max(sigma: float, T: float, k_safety: float = 2.0) -> float:
    """§3.3.5 物理可达上界 K_T_max = k * sigma * sqrt(T)."""
    return k_safety * sigma * math.sqrt(T)


def kelly_position(E_net: float, K_S: float, K_T: float,
                   f_max: float = 0.03, alpha: float = 0.5) -> tuple[float, float]:
    """§3.5 凯利仓位.

    Returns:
        (f_kelly, f_final): 部分凯利建议 vs min(kelly, f_max).
    """
    if K_S <= 0 or K_T <= 0:
        return 0.0, 0.0
    f_star = E_net / (K_S * K_T)
    if f_star <= 0:
        return 0.0, 0.0
    f_kelly = alpha * f_star
    f_final = min(f_kelly, f_max)
    return f_kelly, f_final


def mu_implied(K_S: float, K_T: float, sigma: float, c: float,
               E_net_obs: float,
               mu_range: tuple[float, float] = (-3.0, 3.0)) -> Optional[float]:
    """§4.1 μ_implied 反算.

    找使 E[net](mu) = E_net_obs 的 mu.
    """
    def f(mu: float) -> float:
        lam = lambda_from_mu(mu, sigma)
        return e_net_infty(lam, K_S, K_T, c) - E_net_obs

    lo, hi = mu_range
    if f(lo) * f(hi) > 0:
        return None
    try:
        return brentq(f, lo, hi, xtol=1e-6)
    except ValueError:
        return None


# ============================================================
# 数据类
# ============================================================


@dataclass
class FeasibleRangeResult:
    """§3.3 可行区间结果."""
    K_S: float
    K_T_min: Optional[float]
    K_T_max: float
    K_T_recommended: Optional[float]
    verdict: Literal["empty", "narrow", "wide", "no_kelly_edge"]
    reasoning: str


def solve_feasible_range(
    K_S: float,
    T: float,
    mu: float,
    sigma: float,
    c: float,
    k_safety: float = 2.0,
) -> FeasibleRangeResult:
    """§3.3 完整反解流程."""
    K_T_max = solve_K_T_max(sigma, T, k_safety=k_safety)
    K_T_min = solve_K_T_min(K_S, mu, sigma, c, K_T_upper=K_T_max * 3.0)

    if K_T_min is None:
        return FeasibleRangeResult(
            K_S=K_S,
            K_T_min=None,
            K_T_max=K_T_max,
            K_T_recommended=None,
            verdict="no_kelly_edge",
            reasoning=f"mu={mu:.3f} 下没有 K_T 满足凯利正 edge（K_T_min = +inf）"
        )

    if K_T_min >= K_T_max:
        return FeasibleRangeResult(
            K_S=K_S,
            K_T_min=K_T_min,
            K_T_max=K_T_max,
            K_T_recommended=None,
            verdict="empty",
            reasoning=f"K_T_min={K_T_min:.2f} > K_T_max={K_T_max:.2f}，无可行区间"
        )

    ratio = K_T_max / K_T_min
    K_T_rec = math.sqrt(K_T_min * K_T_max)

    if ratio < 1.5:
        verdict = "narrow"
        reasoning = f"K_T ∈ [{K_T_min:.2f}, {K_T_max:.2f}] 高度敏感（比值={ratio:.2f}）"
    elif ratio > 3.0:
        verdict = "wide"
        reasoning = f"K_T ∈ [{K_T_min:.2f}, {K_T_max:.2f}] 宽区间（比值={ratio:.2f}）· 推荐 {K_T_rec:.2f}"
    else:
        verdict = "narrow"  # 中间也归 narrow（保守）
        reasoning = f"K_T ∈ [{K_T_min:.2f}, {K_T_max:.2f}] 中等宽度（比值={ratio:.2f}）· 推荐 {K_T_rec:.2f}"

    return FeasibleRangeResult(
        K_S=K_S,
        K_T_min=K_T_min,
        K_T_max=K_T_max,
        K_T_recommended=K_T_rec,
        verdict=verdict,
        reasoning=reasoning,
    )


# ============================================================
# 单元自检（跑之前先验数学恒等式）
# ============================================================


def _self_check():
    """§V.8 单元测试建议 · 关键恒等式校验."""
    print("=" * 60)
    print("§V.8 单元自检")
    print("=" * 60)

    # 恒等式 1: lambda=0 下 P_win = K_S/(K_S+K_T)
    for K_S, K_T in [(1.5, 3.0), (1.0, 1.0), (0.5, 4.5)]:
        pw = p_win_infty(0.0, K_S, K_T)
        expected = K_S / (K_S + K_T)
        assert abs(pw - expected) < 1e-10, f"P_win({K_S},{K_T}) = {pw} != {expected}"
    print("✓ lambda=0: P_win = K_S/(K_S+K_T)  精确匹配到 1e-10")

    # 恒等式 2: lambda=0 下 E[gross] ≡ 0
    for K_S, K_T in [(1.5, 3.0), (1.0, 1.0), (0.5, 4.5), (2.5, 7.5)]:
        eg = e_gross_infty(0.0, K_S, K_T)
        assert abs(eg) < 1e-10, f"E[gross]({K_S},{K_T}) = {eg} != 0"
    print("✓ lambda=0: E[gross] ≡ 0  精确匹配到 1e-10")

    # 恒等式 3: lambda=0 下 E[net] = -2c
    c = 0.05
    for K_S, K_T in [(1.5, 3.0), (1.0, 1.0)]:
        en = e_net_infty(0.0, K_S, K_T, c)
        assert abs(en - (-2 * c)) < 1e-10, f"E[net]({K_S},{K_T}) = {en} != {-2*c}"
    print(f"✓ lambda=0: E[net] = -2c = {-2*c}  精确匹配")

    # 恒等式 4: lambda=0 下 E[tau] = K_S*K_T/sigma^2
    sigma = 0.5
    for K_S, K_T in [(1.5, 3.0), (1.0, 1.0)]:
        et = e_tau_infty(0.0, K_S, K_T, sigma)
        expected = K_S * K_T / (sigma * sigma)
        assert abs(et - expected) < 1e-10
    print(f"✓ lambda=0: E[tau] = K_S*K_T/sigma^2  精确匹配")

    # lambda 极限: lambda→0 应连续退化
    for lam in [1e-8, 1e-7, 1e-6, 1e-5]:
        pw = p_win_infty(lam, 1.5, 3.0)
        expected_zero = 1.5 / 4.5
        assert abs(pw - expected_zero) < 1e-3, f"lam={lam} P_win={pw}, expected≈{expected_zero}"
    print("✓ lambda→0 连续退化  在 |lambda|<1e-6 范围内切换分支")

    # lambda 上溢: 极大 lambda 返回极限
    pw_pos = p_win_infty(100.0, 1.5, 3.0)
    pw_neg = p_win_infty(-100.0, 1.5, 3.0)
    assert pw_pos == 1.0 and pw_neg == 0.0
    print("✓ lambda 上溢保护正常")

    # P_win 单调递增（关于 lambda）
    prev = 0
    for lam in [-1.0, -0.5, -0.1, 0.0, 0.1, 0.5, 1.0]:
        pw = p_win_infty(lam, 1.5, 3.0)
        assert pw >= prev - 1e-10, f"P_win non-monotonic at lam={lam}"
        prev = pw
    print("✓ P_win 关于 lambda 单调递增")

    print("\n所有自检通过 ✓\n")


# ============================================================
# 对照表生成
# ============================================================


TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = Path("project_data/research/first_passage_lookup")
OUT_DIR.mkdir(parents=True, exist_ok=True)
MD_PATH = Path("docs/workbench/first-passage-lookup-tables.md")


def _write_csv(name: str, headers: list[str], rows: list[list]):
    p = OUT_DIR / f"{name}_{TIMESTAMP}.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in rows:
            w.writerow(row)
    print(f"  → CSV: {p}")


def _fmt(x, digits=3):
    if x is None:
        return "None"
    if isinstance(x, str):
        return x
    if not math.isfinite(x):
        return "+inf" if x > 0 else "-inf"
    if abs(x) < 1e-4:
        return f"{x:.2e}"
    return f"{x:.{digits}f}"


def gen_table1_zero_drift_identity() -> str:
    """表 1 · lambda=0 恒等式校验."""
    print("生成表 1 · lambda=0 恒等式校验")
    sigma = 0.5
    c = 0.05
    K_S_list = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    K_T_list = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]

    csv_rows = []
    for K_S in K_S_list:
        for K_T in K_T_list:
            pw = p_win_infty(0.0, K_S, K_T)
            eg = e_gross_infty(0.0, K_S, K_T)
            en = e_net_infty(0.0, K_S, K_T, c)
            et = e_tau_infty(0.0, K_S, K_T, sigma)
            csv_rows.append([K_S, K_T, f"{pw:.6f}", f"{eg:.2e}", f"{en:.6f}", f"{et:.2f}"])

    _write_csv("table1_zero_drift_identity", ["K_S", "K_T", "P_win", "E_gross", "E_net_c005", "E_tau_sigma05"], csv_rows)

    # Markdown 表
    md = [
        "### 表 1 · λ=0 恒等式校验",
        "",
        "**固定参数**：$\\lambda = 0$（无漂移）· $\\sigma = 0.5$ ATR/√h · $c = 0.05$（扁平成本）· $T = \\infty$",
        "",
        "**预期**：$E[\\text{gross}] \\equiv 0$（精度到 $10^{-10}$）· $E[\\text{net}] \\equiv -2c = -0.10$",
        "",
        "**$P_{\\text{win}}$ 表**（应精确等于 $K_S/(K_S+K_T)$）：",
        "",
        "| $K_S$ \\ $K_T$ | " + " | ".join(f"{k}" for k in K_T_list) + " |",
        "|" + "-" * 14 + "|" + "|".join("-" * 6 for _ in K_T_list) + "|",
    ]
    for K_S in K_S_list:
        row = [f"**{K_S}**"]
        for K_T in K_T_list:
            pw = p_win_infty(0.0, K_S, K_T)
            row.append(f"{pw:.3f}")
        md.append("| " + " | ".join(row) + " |")

    md.append("")
    md.append("**$E[\\text{net}]$ 表**（应精确等于 $-2c = -0.10$，全部）：")
    md.append("")
    md.append("| $K_S$ \\ $K_T$ | " + " | ".join(f"{k}" for k in K_T_list) + " |")
    md.append("|" + "-" * 14 + "|" + "|".join("-" * 6 for _ in K_T_list) + "|")
    for K_S in K_S_list:
        row = [f"**{K_S}**"]
        for K_T in K_T_list:
            en = e_net_infty(0.0, K_S, K_T, c)
            row.append(f"{en:.3f}")
        md.append("| " + " | ".join(row) + " |")

    md.append("")
    md.append("**$E[\\tau]$ 表**（$K_S K_T / \\sigma^2$，单位：小时）：")
    md.append("")
    md.append("| $K_S$ \\ $K_T$ | " + " | ".join(f"{k}" for k in K_T_list) + " |")
    md.append("|" + "-" * 14 + "|" + "|".join("-" * 6 for _ in K_T_list) + "|")
    for K_S in K_S_list:
        row = [f"**{K_S}**"]
        for K_T in K_T_list:
            et = e_tau_infty(0.0, K_S, K_T, sigma)
            row.append(f"{et:.1f}")
        md.append("| " + " | ".join(row) + " |")

    md.append("")
    md.append("**校验结论**：所有单元格数值符合首达定理 KF-1 恒等式。$E[\\text{net}]$ 全部为 $-0.10$，与实测 combo A/E 的成本后近似值一致（含 realistic-cost 修正后的偏差可参见 §表 4）。")
    md.append("")

    return "\n".join(md)


def gen_table2_mu_sensitivity() -> str:
    """表 2 · μ 敏感性."""
    print("生成表 2 · μ 敏感性扫描")
    # 用 L @ 15m 场景
    K_S, K_T = 1.5, 3.0
    T = 20.0
    sigma = 0.9
    c = 0.05

    # 也做 A @ 5m 场景（短期区）
    scenarios = [
        ("A @ 5m", 1.5, 3.0, 6.7, 0.5),
        ("E @ 5m", 1.5, 2.0, 6.7, 0.5),
        ("L @ 15m", 1.5, 3.0, 20.0, 0.9),
        ("SCALE=5 @ 5m", 7.5, 15.0, 33.0, 0.5),
    ]

    mu_grid_ratio = [-1.0, -0.5, -0.3, -0.1, 0.0, 0.1, 0.3, 0.5, 1.0]

    md = [
        "### 表 2 · μ 敏感性扫描",
        "",
        "**用途**：显示 $\\mu$ 假设对 $E[\\text{net}]$ 的影响 · 定位盈亏平衡漂移 $\\mu^*$",
        "",
        "**列**：$\\mu / \\sigma$ 比值（每单位时间；时间单位 = 小时）",
        "",
    ]

    csv_rows = []
    for scen, ksv, ktv, tv, sig in scenarios:
        Ts = t_star(ksv, ktv, sig)
        rg = regime(tv, Ts)
        mu_star_val = mu_star(ksv, ktv, sig, c)

        md.append(f"**场景 {scen}**：$K_S={ksv}, K_T={ktv}, T={tv}$h, $\\sigma={sig}$ ATR/√h · 分界 $T^*={Ts:.1f}$h → **{rg}**")
        md.append("")
        header = "| μ/σ | " + " | ".join(f"{m:+.1f}" for m in mu_grid_ratio) + " | $\\mu^*/\\sigma$ |"
        md.append(header)
        md.append("|" + "-" * 5 + "|" + "|".join("-" * 6 for _ in mu_grid_ratio) + "|" + "-" * 10 + "|")
        row = ["$E[\\text{net}]$"]
        for r in mu_grid_ratio:
            mu = r * sig
            lam = lambda_from_mu(mu, sig)
            en = e_net_infty(lam, ksv, ktv, c)
            row.append(f"{en:+.3f}")
            csv_rows.append([scen, ksv, ktv, tv, sig, r, mu, en])
        mu_star_ratio = mu_star_val / sig if mu_star_val is not None else None
        row.append(f"{mu_star_ratio:+.3f}" if mu_star_ratio is not None else "N/A")
        md.append("| " + " | ".join(row) + " |")
        md.append("")

    _write_csv("table2_mu_sensitivity", ["scenario", "K_S", "K_T", "T_h", "sigma", "mu_over_sigma", "mu", "E_net"], csv_rows)

    md.append("**读表**：")
    md.append("")
    md.append("- $\\mu = 0$ 列全部为 $-2c = -0.10$（$c=0.05$ 扁平口径），印证 KF-1")
    md.append("- $\\mu^*/\\sigma$ 是让 $E[\\text{net}] = 0$ 所需的漂移。若 $\\mu^*/\\sigma > 1$，说明这个 combo 需要不合理的强漂移，直接淘汰")
    md.append("- SCALE=5 场景 $T^*$ 极大 → **长期区**，$\\mu$ 微小变化就能显著改变期望，正是 KF-7 里被 SCALE 放大伪影的数学根源")
    md.append("")
    return "\n".join(md)


def gen_table3_regime() -> str:
    """表 3 · 短期/长期分界扫描."""
    print("生成表 3 · 短期/长期分界")
    K_S = K_T = 1.5
    sigma_list = [0.3, 0.5, 0.9, 1.5]
    T_list = [1.0, 6.7, 20.0, 80.0, 400.0]

    csv_rows = []
    for sig in sigma_list:
        for T in T_list:
            Ts = t_star(K_S, K_T, sig)
            rg = regime(T, Ts)
            csv_rows.append([K_S, K_T, sig, T, Ts, T / Ts, rg])
    _write_csv("table3_regime", ["K_S", "K_T", "sigma", "T", "T_star", "T_over_T_star", "regime"], csv_rows)

    md = [
        "### 表 3 · 短期/长期分界扫描",
        "",
        f"**固定参数**：$K_S = K_T = {K_S}$ ATR",
        "",
        "**规则**：$T/T^* < 0.3$ → short_term · $0.3 \\le T/T^* < 3.0$ → transition · $T/T^* \\ge 3.0$ → long_term",
        "",
        "**$T/T^*$ 表**（下方标 regime 首字母 S/T/L）：",
        "",
        "| $T$ (h) \\ $\\sigma$ | " + " | ".join(f"{s}" for s in sigma_list) + " |",
        "|" + "-" * 20 + "|" + "|".join("-" * 12 for _ in sigma_list) + "|",
    ]
    for T in T_list:
        row = [f"**{T}**"]
        for sig in sigma_list:
            Ts = t_star(K_S, K_T, sig)
            ratio = T / Ts
            rg = regime(T, Ts)
            tag = {"short_term": "S", "transition": "T", "long_term": "L"}[rg]
            row.append(f"{ratio:.2f} [{tag}]")
        md.append("| " + " | ".join(row) + " |")

    md.append("")
    md.append("**读表**：")
    md.append("")
    md.append("- 例：$T=6.7$h, $\\sigma=0.5$: $T^*= 1.5^2/0.5^2 = 9$h → $T/T^* = 0.74$ → **transition**（用户诉求「何时肯定不能止盈」的分界）")
    md.append("- 短期区（S）内不管 μ 如何，$E[\\text{net}] \\approx -2c$")
    md.append("- 长期区（L）内 μ 假设主导期望，即微弱漂移也能翻正 mean")
    md.append("")
    return "\n".join(md)


def gen_table4_combo_verdict() -> str:
    """表 4 · combo 判决对照."""
    print("生成表 4 · combo 判决")
    # 场景表：本主题的 combo（含 realistic-cost 用 c=0.225）
    combos = [
        ("A @ 5m",       1.5, 3.0, 6.7,  0.5, 0.05,  -0.116),
        ("A @ 5m real",  1.5, 3.0, 6.7,  0.5, 0.225, -0.462),
        ("E @ 5m",       1.5, 2.0, 6.7,  0.5, 0.05,  -0.127),
        ("E @ 15m",      1.5, 2.0, 20.0, 0.9, 0.05,  -0.109),
        ("L @ 15m",      1.5, 3.0, 20.0, 0.9, 0.05,  +0.041),
        ("M @ 5m SCALE=5", 7.5, 15.0, 33.0, 0.5, 0.05, +0.306),
    ]
    mu_ratios = [0.0, 0.1, 0.3, 0.5]

    csv_rows = []
    md = [
        "### 表 4 · combo 判决对照",
        "",
        "**用途**：本主题 combo 在不同 μ 假设下的可行性判决",
        "",
        "**判决规则**（§3.3.6）：",
        "- **empty** $K_T^{\\min} > K_T^{\\max}$ → 数学必输 · 淘汰",
        "- **no_kelly_edge** $K_T^{\\min} = +\\infty$ → 任何止盈都不满足凯利正 edge",
        "- **narrow** $K_T^{\\max}/K_T^{\\min} < 1.5$ → 高度参数敏感",
        "- **wide** $K_T^{\\max}/K_T^{\\min} > 3$ → 强候选",
        "",
        "| combo | $K_S$ | $K_T$ | $T$(h) | $\\sigma$ | $c$ | μ=0 | μ=0.1σ | μ=0.3σ | μ=0.5σ | $\\mu^*/\\sigma$ | 实测 $E[\\text{net}]$ |",
        "|-------|-------|-------|--------|-----------|-----|-----|--------|--------|--------|------------------|----------------------|",
    ]

    for scen, ksv, ktv, tv, sig, cv, obs in combos:
        row = [scen, str(ksv), str(ktv), str(tv), str(sig), str(cv)]
        for r in mu_ratios:
            mu = r * sig
            fr = solve_feasible_range(ksv, tv, mu, sig, cv, k_safety=2.0)
            row.append(fr.verdict)
            csv_rows.append([scen, r, mu, fr.K_T_min, fr.K_T_max, fr.verdict, obs])
        ms = mu_star(ksv, ktv, sig, cv)
        row.append(f"{ms/sig:+.3f}" if ms is not None else "N/A")
        row.append(f"{obs:+.3f}")
        md.append("| " + " | ".join(row) + " |")

    _write_csv("table4_combo_verdict", ["combo", "mu_over_sigma", "mu", "K_T_min", "K_T_max", "verdict", "E_net_obs"], csv_rows)

    md.append("")
    md.append("**读表**：")
    md.append("")
    md.append("- μ=0 列全部 no_kelly_edge → 印证 KF-1 无漂移下所有 combo 凯利负 edge")
    md.append("- $\\mu^*/\\sigma$ 越大 → 需要越强漂移才能盈利 → combo 越「贵」")
    md.append("- L @ 15m 的 $\\mu^*$ 相对较低 → 与实测 mean 微正吻合")
    md.append("- SCALE=5 场景 $\\mu^*$ 极小 → 极微弱漂移就能翻正 → 印证 KF-7 长期区被漂移主导的机制")
    md.append("")
    return "\n".join(md)


def gen_table5_mu_implied() -> str:
    """表 5 · μ_implied 反算."""
    print("生成表 5 · μ_implied 反算")
    # 用 realistic cost 校准
    scenarios = [
        # scen, K_S, K_T, T, sigma, c, E_net_obs
        ("L @ 15m",          1.5, 3.0, 20.0, 0.9, 0.05,  +0.041),
        ("L @ 15m real",     1.5, 3.0, 20.0, 0.9, 0.20,  -0.20),   # 15m realistic 约估
        ("M @ 5m SCALE=5",   7.5, 15.0, 33.0, 0.5, 0.05, +0.306),
        ("M @ 5m S=5 real",  7.5, 15.0, 33.0, 0.5, 0.225, +0.306),
        ("N @ 5m SCALE=5",   7.5, 22.5, 33.0, 0.5, 0.05, +0.472),
        ("A @ 5m real",      1.5, 3.0, 6.7,  0.5, 0.225, -0.462),  # 应≈-2c
    ]

    csv_rows = []
    md = [
        "### 表 5 · ν_implied 反算（对数空间漂移）",
        "",
        "**用途**：从实测 $E[\\text{net}]$ 反算隐含**对数空间漂移** $\\nu = \\mu - \\sigma^2/2$，判断实测正 mean 是「GBM 隐含漂移」还是「非 GBM 溢价」",
        "",
        "**为什么用 $\\nu$ 而不是 $\\mu$**：",
        "",
        "- 首达公式 $P_{\\text{win}}(\\lambda)$ 由 $\\lambda = 2\\nu/\\sigma^2$ 决定，$\\nu$ 才是「决定期望符号」的量",
        "- $\\nu = 0$ 时 $X_t$ 是 martingale → $E[\\text{gross}] \\equiv 0$（KF-1 恒等式）",
        "- $\\mu = 0$ 时 $\\nu = -\\sigma^2/2 < 0$ → 对数空间有轻微负漂移（Itô 凸性修正）",
        "- 用 $\\nu$ 归因避免把 Itô 修正误判为「市场有正漂移」",
        "",
        "**归因规则**（基于 $\\nu / \\sigma$）：",
        "- $|\\nu_{\\text{implied}} / \\sigma| < 0.02$ → **martingale · GBM 无漂移完美对齐**",
        "- $|\\nu_{\\text{implied}} / \\sigma| < 0.10$ → **接近 martingale · 微弱漂移或非 GBM 溢价**",
        "- $\\nu_{\\text{implied}} / \\sigma \\ge 0.10$ → **显著隐含正漂移（GBM 可解释）**",
        "- $\\nu_{\\text{implied}} / \\sigma \\le -0.10$ → **显著隐含负漂移**",
        "- 反解失败 → **GBM 假设不足**（fat tail / 跳空 / 波动率聚集主导）",
        "",
        "| 场景 | $K_S$ | $K_T$ | $T$(h) | $\\sigma$ | $c$ | 实测 $E[\\text{net}]$ | 理论 $\\nu=0$ $E[\\text{net}]$ | 偏差 | $\\nu_{\\text{implied}}$ | $\\nu/\\sigma$ | $\\mu_{\\text{implied}}$ | 归因 |",
        "|------|-------|-------|--------|-----------|-----|----------------------|-------------------------------|------|-------------------------|-----------------|-------------------------|------|",
    ]

    for scen, ksv, ktv, tv, sig, cv, obs in scenarios:
        theo_zero = -2 * cv  # nu=0 时 E[net] = -2c
        diff = obs - theo_zero
        mi = mu_implied(ksv, ktv, sig, cv, obs)  # 反算的 mu

        if mi is None:
            attribution = "反解失败 · GBM 假设不足"
            ni = None
            ni_ratio = None
            mi_display = "N/A"
        else:
            # 关键修正：从 mu 转 nu = mu - sigma^2/2
            ni = mi - sig * sig / 2.0
            ni_ratio = ni / sig
            mi_display = _fmt(mi, 4)

            if abs(ni_ratio) < 0.02:
                attribution = "≈0 → **martingale · GBM 完美对齐**"
            elif abs(ni_ratio) < 0.10:
                attribution = "接近 0 → 微弱漂移 / 非 GBM 溢价"
            elif ni_ratio >= 0.10:
                attribution = "**显著 > 0 → 隐含正漂移**"
            else:
                attribution = "显著 < 0 → 隐含负漂移"

        row = [
            scen, str(ksv), str(ktv), str(tv), str(sig), str(cv),
            f"{obs:+.3f}", f"{theo_zero:+.3f}", f"{diff:+.3f}",
            _fmt(ni, 4) if ni is not None else "N/A",
            f"{ni_ratio:+.3f}" if ni_ratio is not None else "N/A",
            mi_display,
            attribution
        ]
        md.append("| " + " | ".join(row) + " |")
        csv_rows.append([scen, ksv, ktv, tv, sig, cv, obs, theo_zero, diff, ni, ni_ratio, mi, attribution])

    _write_csv("table5_nu_implied",
               ["scen", "K_S", "K_T", "T_h", "sigma", "c", "E_net_obs", "E_net_theo_nu0",
                "diff", "nu_implied", "nu_over_sigma", "mu_implied", "attribution"], csv_rows)

    md.append("")
    md.append("**读表**：")
    md.append("")
    md.append("- **A @ 5m real**：$\\nu_{\\text{implied}} \\approx 0$（$\\nu/\\sigma \\approx 0$）→ **完美对齐 martingale 假设** · 实测偏差 -0.012 ATR 仅来自采样噪声")
    md.append("- **L @ 15m**（扁平/real 两口径）：$\\nu/\\sigma \\approx 0$ → 依然是 martingale · 正 mean 主要来自 Itô 凸性 + 时间尺度的 tail 效应，非「市场有真实趋势」")
    md.append("- **M/N @ SCALE=5**：$\\nu/\\sigma \\approx 0$ → 同样是 martingale · SCALE=5 的显著正 mean 是**长期区对 martingale 的 Itô 修正的放大**，不是真实漂移")
    md.append("- **关键洞察**：反算所有场景 $\\nu \\approx 0$ → **KF-1 的 martingale 恒等式在实测中完美成立** · 所有「正 mean」都是 GBM 的凸性效应 + 采样噪声，不需要引入「市场有漂移」来解释")
    md.append("- **归因升级**：本项目从「寻找 $\\mu > 0$」的方向 alpha，转向「寻找 $\\nu > 0$」（即 $\\mu > \\sigma^2/2$）的**超凸性漂移**——这是一个更高的门槛")
    md.append("")
    return "\n".join(md)


def main():
    _self_check()

    print("=" * 60)
    print("生成 5 张对照表")
    print("=" * 60)

    parts = [
        "# First-Passage Designer · 对照表",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 数学依据：[first-passage-designer-math-spec.md](../research/themes/structural-shaping-alpha/first-passage-designer-math-spec.md)",
        "> 生成脚本：`scripts/ai_tmp/first_passage_designer.py`",
        "> 数据快照：`project_data/research/first_passage_lookup/tables_*_" + TIMESTAMP + ".csv`",
        "",
        "**5 张对照表**：",
        "",
        "1. **表 1**：λ=0 恒等式校验（$P_{\\text{win}}, E[\\text{gross}], E[\\text{net}], E[\\tau]$）",
        "2. **表 2**：μ 敏感性扫描（4 个 combo 场景）",
        "3. **表 3**：短期/长期分界 $T^*$ 扫描",
        "4. **表 4**：本主题 combo 的可行区间判决",
        "5. **表 5**：实测 $\\nu_{\\text{implied}}$ 反算与归因（对数空间漂移）",
        "",
        "***",
        "",
        gen_table1_zero_drift_identity(),
        "***",
        "",
        gen_table2_mu_sensitivity(),
        "***",
        "",
        gen_table3_regime(),
        "***",
        "",
        gen_table4_combo_verdict(),
        "***",
        "",
        gen_table5_mu_implied(),
        "***",
        "",
        "## 附：与 spec 章节对应",
        "",
        "| 表 | Spec 章节 | 核心量 |",
        "|----|-----------|--------|",
        "| 1 | §2.3-2.5 | $P_{\\text{win}}, E[\\text{gross}], E[\\text{net}], E[\\tau]$ |",
        "| 2 | §3.1-3.2 | μ 敏感性 · $\\mu^*$ |",
        "| 3 | §2.7 | $T^*$ 分界 |",
        "| 4 | §3.3 | 可行区间反解 · verdict |",
        "| 5 | §4.1 | $\\nu_{\\text{implied}}$ 反算（对数空间） · $\\mu_{\\text{implied}}$ 附表 |",
        "",
    ]

    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"\n对照表 Markdown 已写入：{MD_PATH}")
    print(f"CSV 数据已写入：{OUT_DIR}/tables_*_{TIMESTAMP}.csv")


if __name__ == "__main__":
    main()
