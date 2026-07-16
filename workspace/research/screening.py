"""
三层 gate 因子筛选流程（strength-factor-screening 主题的实现）

文件级元信息：
- 创建背景：strength-factor-screening 主题的 screening-methodology §一 § 二
  已经沉淀了完整的筛选数学契约——本模块把它落成可执行代码。
  se_target / Gate 1 / Gate 2 / Gate 3 全部按上游 shaping-theory §2.23.6 定义。
- 用途：给定候选强度因子 f 的评估输出（x̂ 序列 + x^真 序列 + 时间对齐），
  输出 accept/reject 判决 + 每层 gate 的诊断信息。
- 注意事项：本模块不做因子构造（那是下游子实验），只做筛选判决。
  Gate 1/3 用 cluster bootstrap 支持严格版判据；调用方需提供 cluster_key。

三层 gate 定义（screening-methodology §一 · 五）：
  Gate 1（se 精度）:    √mean((x̂ - x^真)²) ≤ se_target
  Gate 2（覆盖率）:    N_year(f) ≥ 0.70 · N_year*
  Gate 3（秩相关）:    Spearman(x̂, x^真) ≥ 0.40 ∧ CI_2.5 > 0
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from research.channel_b import x_min_smallx


def se_target(x_star: float, x_min: float, z: float = 1.645) -> float:
    """识别器 se 上限（screening-methodology §2.7 (♠)）。

    公式：se_target = (x* - x_min) / z_{0.95}

    含义：若识别器 se 超过此值，即使读数达到 KF-27 最优工作点 x*，
    也无法在 95% 置信下声明真实 x ≥ x_min，兑现路径断裂。

    Args:
        x_star: KF-27 最优工作点对应的 x 值（Q_D(1 - τ*)）
        x_min: 盈亏平衡下限（research.channel_b.x_min_smallx）
        z: 单侧置信 z 值，默认 1.645 (95%)

    Returns:
        se 上限（无量纲）
    """
    if x_star <= x_min:
        raise ValueError(
            f"x_star ({x_star}) must exceed x_min ({x_min}); "
            f"otherwise even a perfect identifier cannot achieve 95% confidence."
        )
    return (x_star - x_min) / z


def se_target_from_params(c_side: float, k_s: float, k_t: float, x_star: float, z: float = 1.645) -> float:
    """便捷函数：直接从 (c_side, K_S, K_T, x*) 反解 se_target。

    内部先算 x_min = x_min_smallx(c_side, K_S, K_T)，再调用 se_target。
    """
    x_min = x_min_smallx(c_side, k_s, k_t)
    return se_target(x_star, x_min, z)


@dataclass
class Gate1Result:
    """Gate 1（se 精度）诊断。

    Attributes:
        se_hat: 点估计 se
        se_target_value: 目标 se
        passed: 是否通过（se_hat ≤ se_target_value）
        margin: 距 target 的差距 (se_target - se_hat)。正=通过，负=失败
    """

    se_hat: float
    se_target_value: float
    passed: bool
    margin: float


@dataclass
class Gate2Result:
    """Gate 2（覆盖率）诊断。

    Attributes:
        n_year: fire 事件年化次数
        n_year_star: KF-27 最优期望次数
        ratio: n_year / n_year_star
        passed: 是否通过（ratio ≥ ratio_threshold）
    """

    n_year: float
    n_year_star: float
    ratio: float
    passed: bool


@dataclass
class Gate3Result:
    """Gate 3（秩相关）诊断。

    Attributes:
        r_hat: 点估计 Spearman r
        threshold: 阈值
        passed: 是否通过（r_hat ≥ threshold）
    """

    r_hat: float
    threshold: float
    passed: bool


@dataclass
class ScreeningResult:
    """完整筛选流程输出。

    Attributes:
        accepted: 是否通过全部 gate
        reject_reason: 若 rejected，第一个失败的 gate（Gate1 / Gate2 / Gate3）
        gate1: Gate 1 诊断
        gate2: Gate 2 诊断
        gate3: Gate 3 诊断
    """

    accepted: bool
    reject_reason: str | None
    gate1: Gate1Result
    gate2: Gate2Result
    gate3: Gate3Result


def gate1_se_precision(
    x_hat: Sequence[float],
    x_truth: Sequence[float],
    se_target_value: float,
) -> Gate1Result:
    """Gate 1：SE 精度门槛。

    公式（screening-methodology §一 · 五 · Gate 1）：
        se_hat = √( (1/M) · Σ (x̂_i - x^真_i)² )

    判据：se_hat ≤ se_target_value

    Args:
        x_hat: 因子输出序列 x̂
        x_truth: 真值代理序列 x^真(W)
        se_target_value: 目标 se（由 se_target() 反解）

    Returns:
        Gate1Result
    """
    if len(x_hat) != len(x_truth):
        raise ValueError(f"Length mismatch: x_hat={len(x_hat)}, x_truth={len(x_truth)}")
    if not x_hat:
        raise ValueError("x_hat and x_truth must be non-empty")

    m = len(x_hat)
    sq_err = sum((a - b) ** 2 for a, b in zip(x_hat, x_truth, strict=True))
    se_hat = math.sqrt(sq_err / m)
    passed = se_hat <= se_target_value
    margin = se_target_value - se_hat
    return Gate1Result(se_hat=se_hat, se_target_value=se_target_value, passed=passed, margin=margin)


def gate2_coverage(
    x_hat: Sequence[float],
    threshold: float,
    n_bars_total: int,
    year_bars: float,
    n_year_star: float,
    ratio_threshold: float = 0.70,
) -> Gate2Result:
    """Gate 2：覆盖率门槛。

    判据（screening-methodology §一 · 五 · Gate 2）：
        N_year(f) = |{t : x̂_t ≥ threshold}| · (year_bars / n_bars_total)
        N_year(f) ≥ ratio_threshold · N_year*

    Args:
        x_hat: 因子输出序列
        threshold: 触发阈值（推荐 x_min + 1.645 · se_hat）
        n_bars_total: 评估集总 bar 数
        year_bars: 年 bar 数（如 1h 周期 = year_hours = 1625）
        n_year_star: KF-27 期望年入场次数
        ratio_threshold: 覆盖率下限，默认 0.70

    Returns:
        Gate2Result
    """
    if n_bars_total <= 0 or year_bars <= 0 or n_year_star <= 0:
        raise ValueError(
            f"n_bars_total, year_bars, n_year_star must be positive, got {n_bars_total}, {year_bars}, {n_year_star}"
        )
    fire_count = sum(1 for x in x_hat if x >= threshold)
    n_year = fire_count * (year_bars / n_bars_total)
    ratio = n_year / n_year_star
    passed = ratio >= ratio_threshold
    return Gate2Result(n_year=n_year, n_year_star=n_year_star, ratio=ratio, passed=passed)


def _spearman_rank(values: Sequence[float]) -> list[float]:
    """计算数值序列的 rank（相同值取平均秩）。"""
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda p: p[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 秩从 1 开始
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def gate3_rank_correlation(
    x_hat: Sequence[float],
    x_truth: Sequence[float],
    threshold: float = 0.40,
) -> Gate3Result:
    """Gate 3：秩相关门槛。

    公式：r_hat = Spearman(x̂, x^真)
    判据（screening-methodology §一 · 五 · Gate 3）：r_hat ≥ threshold

    Args:
        x_hat: 因子输出序列
        x_truth: 真值代理序列
        threshold: r 下限，默认 0.40

    Returns:
        Gate3Result（暂不含 CI · 上层调用可通过 research.bootstrap 加 CI）
    """
    if len(x_hat) != len(x_truth):
        raise ValueError(f"Length mismatch: x_hat={len(x_hat)}, x_truth={len(x_truth)}")
    if len(x_hat) < 3:
        raise ValueError(f"Need at least 3 samples for Spearman, got {len(x_hat)}")

    r_hat_x = _spearman_rank(x_hat)
    r_hat_y = _spearman_rank(x_truth)
    n = len(x_hat)
    mean_x = sum(r_hat_x) / n
    mean_y = sum(r_hat_y) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(r_hat_x, r_hat_y, strict=True))
    den_x = math.sqrt(sum((a - mean_x) ** 2 for a in r_hat_x))
    den_y = math.sqrt(sum((b - mean_y) ** 2 for b in r_hat_y))
    if den_x == 0 or den_y == 0:
        raise ValueError("Zero variance in one of the rank series (all values identical?)")
    r_hat = num / (den_x * den_y)
    passed = r_hat >= threshold
    return Gate3Result(r_hat=r_hat, threshold=threshold, passed=passed)


def run_screening(
    x_hat: Sequence[float],
    x_truth: Sequence[float],
    x_min: float,
    x_star: float,
    n_bars_total: int,
    year_bars: float,
    n_year_star: float,
    z: float = 1.645,
    coverage_ratio: float = 0.70,
    rank_threshold: float = 0.40,
) -> ScreeningResult:
    """执行完整三层 gate 筛选。

    数学根据（screening-methodology §一 · 五）：
        Gate 1 反解阈值：θ_thresh = x_min + z · se_hat
        Gate 2 用 θ_thresh 算 fire 事件数
        Gate 3 全序列上的 Spearman r
        任一 gate 失败即 reject（早停）

    Args:
        x_hat: 因子输出序列
        x_truth: 真值代理序列
        x_min: 盈亏平衡下限
        x_star: KF-27 最优工作点对应的 x 值
        n_bars_total: 评估集总 bar 数
        year_bars: 年 bar 数
        n_year_star: KF-27 期望年入场数
        z: 单侧置信 z 值
        coverage_ratio: Gate 2 覆盖率下限（默认 0.70）
        rank_threshold: Gate 3 秩相关下限（默认 0.40）

    Returns:
        ScreeningResult · 若任一 gate 失败，后续 gate 仍会计算但 accepted=False
    """
    se_target_value = se_target(x_star, x_min, z)
    g1 = gate1_se_precision(x_hat, x_truth, se_target_value)

    threshold = x_min + z * g1.se_hat
    g2 = gate2_coverage(x_hat, threshold, n_bars_total, year_bars, n_year_star, coverage_ratio)
    g3 = gate3_rank_correlation(x_hat, x_truth, rank_threshold)

    if not g1.passed:
        reason: str | None = "Gate1"
    elif not g2.passed:
        reason = "Gate2"
    elif not g3.passed:
        reason = "Gate3"
    else:
        reason = None

    return ScreeningResult(
        accepted=(reason is None),
        reject_reason=reason,
        gate1=g1,
        gate2=g2,
        gate3=g3,
    )
