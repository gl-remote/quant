"""
双通道漂移探测器 · z_A / z_B 与融合判据

文件级元信息：
- 创建背景：shaping-theory §2.13.6 / §2.16 / KF-17 / KF-18 沉淀的"双通道漂移探测器"。
  给定一个 barrier 停时事件集，可以从两个独立通道验证"该样本是否真的带漂移"：
    - 通道 A（P_win 通道）：观测胜率 vs Fourier 零漂移 null 的 z 分数
    - 通道 B（time-exit 通道）：观测 P(τ > T) vs Fourier 零漂移 null 的 z 分数
  两个通道方向一致（z_A > 2 且 z_B < -2）时才算真实漂移证据。
- 用途：strength-factor-screening 主题里 Gate 1-3 通过后的第 4 层事后审计，
  避免"评估集抽样偏差"导致虚假 accept。
- 注意事项：P(τ > T)_theory < 1e-3 时 z_B 会数值爆炸（观察到 +2367），
  下游必须过滤该阈值下的格点；本模块通过 `valid` 字段显式标注。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from research.fourier import p_tau_gt_T_fourier, p_win_finiteT_fourier

# P(τ > T) 理论值低于此阈值时通道 B 数值不稳，标记 valid=False
_P_TAU_STABLE_TOL = 1e-3


@dataclass
class DriftDetection:
    """双通道漂移探测结果。

    Attributes:
        z_a: 通道 A（P_win）的 z 分数
        z_b: 通道 B（time-exit）的 z 分数
        p_win_obs / p_win_theory: 观测与 Fourier 零漂移 null
        p_tau_gt_T_obs / p_tau_gt_T_theory: 观测与理论 P(τ > T)
        b_channel_valid: P(τ > T)_theory ≥ 1e-3，通道 B 数值可靠
        verdict: "drift_positive"（z_A > 2 ∧ z_B < -2）· "drift_negative"（相反）·
                 "no_drift"（两通道都不显著）· "channel_a_only"（B 不 valid，仅 A）·
                 "inconsistent"（两通道方向冲突，可能是 barrier 结构问题）
    """

    z_a: float
    z_b: float
    p_win_obs: float
    p_win_theory: float
    p_tau_gt_T_obs: float
    p_tau_gt_T_theory: float
    b_channel_valid: bool
    verdict: str


def _binomial_se(p: float, n: int) -> float:
    """二项比例的标准误 sqrt(p(1-p)/n)。"""
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    return math.sqrt(max(p * (1.0 - p), 0.0) / n)


def dual_channel_drift_test(
    n_win: int,
    n_time_exit: int,
    n_total: int,
    k_s: float,
    k_t: float,
    sigma: float,
    t_horizon: float,
    z_threshold: float = 2.0,
) -> DriftDetection:
    """双通道漂移探测（shaping-theory §2.13.6 · §2.16）。

    Args:
        n_win: 事件集中止盈胜利的样本数
        n_time_exit: 事件集中 time-exit（τ > T）的样本数
        n_total: 事件集总样本数
        k_s, k_t: barrier 距离
        sigma: 每单位时间波动率
        t_horizon: 有限时间上限
        z_threshold: 双通道显著性阈值，默认 2.0（约 95% 单侧）

    Returns:
        DriftDetection

    数值稳定性：
        P(τ > T)_theory < 1e-3 时通道 B 的 z_b 会爆炸；此时 valid=False，
        verdict 只根据通道 A 判定（"channel_a_only"）。
    """
    if n_total <= 0:
        raise ValueError(f"n_total must be positive, got {n_total}")
    if n_win < 0 or n_time_exit < 0 or n_win + n_time_exit > n_total:
        raise ValueError(f"Invalid counts: n_win={n_win}, n_time_exit={n_time_exit}, n_total={n_total}")

    # Fourier null
    p_win_theory = p_win_finiteT_fourier(k_s, k_t, sigma, t_horizon)
    p_tau_theory = p_tau_gt_T_fourier(k_s, k_t, sigma, t_horizon)

    # 观测比例
    p_win_obs = n_win / n_total
    p_tau_obs = n_time_exit / n_total

    # z_A: P_win 通道
    se_win = _binomial_se(p_win_obs, n_total)
    z_a = (p_win_obs - p_win_theory) / se_win if se_win > 0 else 0.0

    # z_B: time-exit 通道 · 数值稳定性检查
    b_valid = p_tau_theory >= _P_TAU_STABLE_TOL
    if b_valid:
        se_tau = _binomial_se(p_tau_obs, n_total)
        z_b = (p_tau_obs - p_tau_theory) / se_tau if se_tau > 0 else 0.0
    else:
        z_b = 0.0  # 占位，valid=False 时不使用

    # 判决
    if not b_valid:
        # 只用通道 A
        verdict = "channel_a_only" if z_a > z_threshold else "no_drift"
    else:
        if z_a > z_threshold and z_b < -z_threshold:
            verdict = "drift_positive"
        elif z_a < -z_threshold and z_b > z_threshold:
            verdict = "drift_negative"
        elif abs(z_a) < z_threshold and abs(z_b) < z_threshold:
            verdict = "no_drift"
        else:
            verdict = "inconsistent"

    return DriftDetection(
        z_a=z_a,
        z_b=z_b,
        p_win_obs=p_win_obs,
        p_win_theory=p_win_theory,
        p_tau_gt_T_obs=p_tau_obs,
        p_tau_gt_T_theory=p_tau_theory,
        b_channel_valid=b_valid,
        verdict=verdict,
    )
