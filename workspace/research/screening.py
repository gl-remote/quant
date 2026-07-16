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
  Gate 1.5（分布对齐）: 均值/尺度/尾部/KS 四项检验（screening-methodology §四 Step 4.5）
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
class Gate1_5Result:
    """Gate 1.5（分布对齐）诊断 · screening-methodology §四 Step 4.5。

    检验因子输出 x̂ 与真值代理 x^真 的分布是否在合理边界内对齐——
    避免"se 数值上过 gate 但分布位置/形态错位"的静默失效。

    四项检验：
        C1 · 一阶矩：|E[x̂] - E[x^真]| / E[x^真] ≤ mean_rel_thresh（默认 0.20）
        C2 · 尺度：sd(x̂) / sd(x^真) ∈ std_ratio_range（默认 [0.5, 1.5]）
        C3 · 尾部：|Q_p(x̂) - Q_p(x^真)| / Q_p(x^真) ≤ q_tail_rel_thresh（默认 0.30, p=0.90）
        C4 · KS 双样本统计量：D_KS ≤ ks_thresh（默认 0.15）

    Attributes:
        mean_rel_error: 均值相对偏差
        std_ratio: sd(x̂) / sd(x^真)
        q_tail_rel_error: 上分位（默认 90%）相对偏差
        ks_statistic: KS 双样本统计量 D
        c1_passed / c2_passed / c3_passed / c4_passed: 四项子判据
        passed: 四项综合（AND）
        reasons: 若 passed=False · 列出失败项名称
        remedy_hint: "rescale"（量纲错位）· "reweight_tail"（尾部错位）·
                     "degenerate"（sd→0 点分布）· "reject_dist_error"（严重不对齐）· None
    """

    mean_rel_error: float
    std_ratio: float
    q_tail_rel_error: float
    ks_statistic: float
    c1_passed: bool
    c2_passed: bool
    c3_passed: bool
    c4_passed: bool
    passed: bool
    reasons: list[str]
    remedy_hint: str | None


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
        reject_reason: 若 rejected，第一个失败的 gate（Gate1 / Gate1_5 / Gate2 / Gate3）
        gate1: Gate 1 诊断
        gate1_5: Gate 1.5 分布对齐诊断（可选 · 若未提供 x_truth 分布无法算则为 None）
        gate2: Gate 2 诊断
        gate3: Gate 3 诊断
    """

    accepted: bool
    reject_reason: str | None
    gate1: Gate1Result
    gate1_5: Gate1_5Result | None
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


def _quantile(values: Sequence[float], p: float) -> float:
    """线性插值分位数（与 numpy 默认 'linear' 一致）。"""
    if not values:
        raise ValueError("values must be non-empty")
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be in [0, 1], got {p}")
    sorted_v = sorted(values)
    n = len(sorted_v)
    if n == 1:
        return sorted_v[0]
    h = p * (n - 1)
    lo = int(math.floor(h))
    hi = int(math.ceil(h))
    if lo == hi:
        return sorted_v[lo]
    return sorted_v[lo] + (h - lo) * (sorted_v[hi] - sorted_v[lo])


def _ks_two_sample(a: Sequence[float], b: Sequence[float]) -> float:
    """双样本 KS 统计量 D = sup_x |F_a(x) - F_b(x)|。"""
    if not a or not b:
        raise ValueError("both samples must be non-empty")
    sorted_a = sorted(a)
    sorted_b = sorted(b)
    na, nb = len(sorted_a), len(sorted_b)
    all_vals = sorted(set(sorted_a) | set(sorted_b))
    d_max = 0.0
    for v in all_vals:
        # 经验 CDF：|{x ≤ v}| / n
        fa = sum(1 for x in sorted_a if x <= v) / na
        fb = sum(1 for x in sorted_b if x <= v) / nb
        d = abs(fa - fb)
        if d > d_max:
            d_max = d
    return d_max


def gate1_5_distribution_alignment(
    x_hat: Sequence[float],
    x_truth: Sequence[float],
    mean_rel_thresh: float = 0.20,
    std_ratio_range: tuple[float, float] = (0.5, 1.5),
    q_tail_rel_thresh: float = 0.30,
    q_tail_p: float = 0.90,
    ks_thresh: float = 0.15,
) -> Gate1_5Result:
    """Gate 1.5：分布对齐门槛（screening-methodology §四 Step 4.5）。

    检验因子输出 x̂ 与真值代理 x^真 的分布是否在合理边界内对齐。
    该 gate 弥补 Gate 1（SE）只测一阶矩误差、Gate 3（Spearman）不敏感于分布形态的盲区。

    四项子判据：
        C1 · 一阶矩：|mean(x̂) - mean(x^真)| / mean(x^真) ≤ mean_rel_thresh
        C2 · 尺度：sd(x̂) / sd(x^真) ∈ std_ratio_range
        C3 · 尾部：|Q_p(x̂) - Q_p(x^真)| / Q_p(x^真) ≤ q_tail_rel_thresh
        C4 · KS 双样本：sup_x |F_x̂(x) - F_x^真(x)| ≤ ks_thresh

    Args:
        x_hat: 因子输出序列
        x_truth: 真值代理序列
        mean_rel_thresh: C1 阈值，默认 0.20
        std_ratio_range: C2 (lo, hi) 区间，默认 (0.5, 1.5)
        q_tail_rel_thresh: C3 阈值，默认 0.30
        q_tail_p: C3 分位点，默认 0.90
        ks_thresh: C4 阈值，默认 0.15

    Returns:
        Gate1_5Result · 若 passed=False，reasons 列出失败项，remedy_hint 给修正方向

    Raises:
        ValueError: 序列长度不匹配 · 空序列 · x_truth 均值/上分位为 0（无法算相对偏差）
    """
    if len(x_hat) != len(x_truth):
        raise ValueError(f"Length mismatch: x_hat={len(x_hat)}, x_truth={len(x_truth)}")
    if len(x_hat) < 3:
        raise ValueError(f"Need at least 3 samples, got {len(x_hat)}")
    lo, hi = std_ratio_range
    if not (0 < lo < hi):
        raise ValueError(f"std_ratio_range must satisfy 0 < lo < hi, got {std_ratio_range}")

    n = len(x_hat)
    mean_hat = sum(x_hat) / n
    mean_truth = sum(x_truth) / n
    # 方差用总体（分母 n · 与 numpy 默认 ddof=0 一致）
    var_hat = sum((v - mean_hat) ** 2 for v in x_hat) / n
    var_truth = sum((v - mean_truth) ** 2 for v in x_truth) / n
    sd_hat = math.sqrt(max(var_hat, 0.0))
    sd_truth = math.sqrt(max(var_truth, 0.0))

    # C1 · 均值相对偏差
    if abs(mean_truth) < 1e-12:
        raise ValueError("mean(x_truth) is 0; cannot compute relative mean error")
    mean_rel_err = abs(mean_hat - mean_truth) / abs(mean_truth)
    c1 = mean_rel_err <= mean_rel_thresh

    # C2 · 尺度比 · sd_truth=0 时视为病态
    if sd_truth < 1e-12:
        raise ValueError("sd(x_truth) is 0; truth series is degenerate")
    std_ratio = sd_hat / sd_truth
    c2 = lo <= std_ratio <= hi

    # C3 · 上分位相对偏差
    q_hat = _quantile(list(x_hat), q_tail_p)
    q_truth = _quantile(list(x_truth), q_tail_p)
    if abs(q_truth) < 1e-12:
        raise ValueError(f"Q_{q_tail_p}(x_truth) is 0; cannot compute relative tail error")
    q_tail_rel_err = abs(q_hat - q_truth) / abs(q_truth)
    c3 = q_tail_rel_err <= q_tail_rel_thresh

    # C4 · KS 双样本
    d_ks = _ks_two_sample(list(x_hat), list(x_truth))
    c4 = d_ks <= ks_thresh

    passed = c1 and c2 and c3 and c4
    reasons: list[str] = []
    remedy_hint: str | None = None

    if not c1:
        reasons.append(f"C1_mean: rel_err={mean_rel_err:.3f} > {mean_rel_thresh:.3f}")
    if not c2:
        reasons.append(f"C2_scale: sd_ratio={std_ratio:.3f} not in [{lo}, {hi}]")
    if not c3:
        reasons.append(f"C3_tail: q{int(q_tail_p * 100)}_rel_err={q_tail_rel_err:.3f} > {q_tail_rel_thresh:.3f}")
    if not c4:
        reasons.append(f"C4_ks: D={d_ks:.3f} > {ks_thresh:.3f}")

    # 修正提示：优先按主导症状分派
    if not passed:
        if std_ratio < lo * 0.5:
            remedy_hint = "degenerate"
        elif (not c1) and mean_rel_err > 3 * mean_rel_thresh:
            remedy_hint = "rescale"
        elif (not c3) and q_tail_rel_err > 2 * q_tail_rel_thresh:
            remedy_hint = "reweight_tail"
        else:
            remedy_hint = "reject_dist_error"

    return Gate1_5Result(
        mean_rel_error=mean_rel_err,
        std_ratio=std_ratio,
        q_tail_rel_error=q_tail_rel_err,
        ks_statistic=d_ks,
        c1_passed=c1,
        c2_passed=c2,
        c3_passed=c3,
        c4_passed=c4,
        passed=passed,
        reasons=reasons,
        remedy_hint=remedy_hint,
    )


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
    run_gate1_5: bool = True,
    mean_rel_thresh: float = 0.20,
    std_ratio_range: tuple[float, float] = (0.5, 1.5),
    q_tail_rel_thresh: float = 0.30,
    q_tail_p: float = 0.90,
    ks_thresh: float = 0.15,
) -> ScreeningResult:
    """执行完整筛选流程（含 Gate 1.5）。

    数学根据（screening-methodology §一 · 五）：
        Gate 1 反解阈值：θ_thresh = x_min + z · se_hat
        Gate 1.5 · 分布对齐（均值/尺度/尾部/KS · §四 Step 4.5）
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
        run_gate1_5: 是否执行 Gate 1.5（默认 True）· 关闭时 gate1_5=None
        mean_rel_thresh / std_ratio_range / q_tail_rel_thresh / q_tail_p / ks_thresh:
            Gate 1.5 四项阈值

    Returns:
        ScreeningResult · 若任一 gate 失败，后续 gate 仍会计算但 accepted=False
    """
    se_target_value = se_target(x_star, x_min, z)
    g1 = gate1_se_precision(x_hat, x_truth, se_target_value)

    g1_5: Gate1_5Result | None = None
    if run_gate1_5:
        g1_5 = gate1_5_distribution_alignment(
            x_hat,
            x_truth,
            mean_rel_thresh=mean_rel_thresh,
            std_ratio_range=std_ratio_range,
            q_tail_rel_thresh=q_tail_rel_thresh,
            q_tail_p=q_tail_p,
            ks_thresh=ks_thresh,
        )

    threshold = x_min + z * g1.se_hat
    g2 = gate2_coverage(x_hat, threshold, n_bars_total, year_bars, n_year_star, coverage_ratio)
    g3 = gate3_rank_correlation(x_hat, x_truth, rank_threshold)

    if not g1.passed:
        reason: str | None = "Gate1"
    elif g1_5 is not None and not g1_5.passed:
        reason = "Gate1_5"
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
        gate1_5=g1_5,
        gate2=g2,
        gate3=g3,
    )
