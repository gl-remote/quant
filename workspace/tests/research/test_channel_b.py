"""research.fpt / research.fourier / research.channel_b 单元测试

覆盖：
    - FPT λ=0 恒等式（P_win = 1/(1+R), E[gross] = 0）
    - FPT λ≠0 精确解与极限性质
    - Fourier T → ∞ 收敛到无限时间解
    - Fourier martingale 参照（K_S=K_T 对称双 barrier）
    - 通道 B 混合期望正性 + Doob 保守律
    - x_min 玉米 1h 数值核对
"""

from __future__ import annotations

import math

import pytest
from research.channel_b import e_gross_mix, e_gross_mix_smallx, x_min_smallx
from research.fourier import p_tau_gt_T_fourier, p_win_finiteT_fourier
from research.fpt import e_gross_infty, e_net_infty, e_tau_infty, p_win_infty, t_star

# ═══════════════════════════════════════════════════════════
# FPT · shaping-theory §1.3.1 / §1.4 / §1.5
# ═══════════════════════════════════════════════════════════


class TestPWinInfty:
    def test_lambda_zero_identity(self):
        """λ=0 恒等式 P_win = 1/(1+R)（shaping §2.3 表）。"""
        assert p_win_infty(0.0, 1.5, 3.0) == pytest.approx(1.0 / 3.0, abs=1e-10)
        assert p_win_infty(0.0, 1.0, 1.0) == pytest.approx(0.5, abs=1e-10)
        assert p_win_infty(0.0, 1.0, 2.0) == pytest.approx(1.0 / 3.0, abs=1e-10)

    def test_lambda_zero_dispatched_by_tol(self):
        """|λ| < 1e-6 走 λ=0 分支避免除零。"""
        assert p_win_infty(1e-8, 1.0, 1.0) == pytest.approx(0.5, abs=1e-10)
        assert p_win_infty(-1e-8, 1.0, 1.0) == pytest.approx(0.5, abs=1e-10)

    def test_lambda_positive_bias(self):
        """λ > 0（正漂移）时 P_win 高于 λ=0 基准。"""
        p_zero = p_win_infty(0.0, 1.5, 3.0)
        p_pos = p_win_infty(0.5, 1.5, 3.0)
        assert p_pos > p_zero

    def test_lambda_saturation_upper(self):
        """|λ·max(K)| > 50 返回极限值。"""
        assert p_win_infty(100.0, 1.0, 1.0) == 1.0
        assert p_win_infty(-100.0, 1.0, 1.0) == 0.0

    def test_barrier_limits(self):
        """K_T → 0 时 P_win → 1；K_T → ∞ + λ≤0 时 → 0。"""
        assert p_win_infty(0.0, 1.0, 1e-6) == pytest.approx(1.0, abs=1e-3)
        # λ=0 且 K_T 极大 → K_S/(K_S+K_T) → 0
        assert p_win_infty(0.0, 1.0, 1e6) == pytest.approx(0.0, abs=1e-3)

    def test_invalid_barriers(self):
        with pytest.raises(ValueError):
            p_win_infty(0.0, 0.0, 1.0)
        with pytest.raises(ValueError):
            p_win_infty(0.0, 1.0, -1.0)


class TestEGrossInfty:
    def test_doob_identity(self):
        """λ=0 时 E[gross] ≡ 0（Doob 停时定理，任意 K_S/K_T）。"""
        assert e_gross_infty(0.0, 1.5, 3.0) == pytest.approx(0.0, abs=1e-10)
        assert e_gross_infty(0.0, 1.0, 5.0) == pytest.approx(0.0, abs=1e-10)
        assert e_gross_infty(0.0, 2.0, 2.0) == pytest.approx(0.0, abs=1e-10)

    def test_net_with_cost(self):
        """λ=0 时 E[net] = -2c。"""
        assert e_net_infty(0.0, 1.0, 1.0, 0.05) == pytest.approx(-0.10, abs=1e-10)


class TestETauInfty:
    def test_lambda_zero(self):
        """λ=0 平均首达时间 = K_S · K_T / σ²（shaping §1.5）。"""
        assert e_tau_infty(0.0, 1.0, 1.0, 0.5) == pytest.approx(4.0, abs=1e-10)
        assert e_tau_infty(0.0, 2.0, 3.0, 1.0) == pytest.approx(6.0, abs=1e-10)

    def test_lambda_nonzero_requires_nu(self):
        with pytest.raises(ValueError):
            e_tau_infty(1.0, 1.0, 1.0, 0.5)


class TestTStar:
    def test_definition(self):
        """T* = max(K_S, K_T)² / σ²。"""
        assert t_star(1.0, 2.0, 0.5) == pytest.approx(16.0, abs=1e-10)
        assert t_star(3.0, 1.5, 1.0) == pytest.approx(9.0, abs=1e-10)


# ═══════════════════════════════════════════════════════════
# Fourier · shaping-theory §2.13.2 · KF-17
# ═══════════════════════════════════════════════════════════


class TestFourier:
    def test_convergence_to_infty(self):
        """T → ∞ 时 P_win_finiteT → K_S/(K_S+K_T)。"""
        k_s, k_t = 1.0, 2.0
        p_infty_theory = k_s / (k_s + k_t)  # = 1/3
        p_finite = p_win_finiteT_fourier(k_s, k_t, sigma=1.0, t_horizon=10000.0)
        assert p_finite == pytest.approx(p_infty_theory, abs=5e-3)

    def test_martingale_symmetric(self):
        """K_S = K_T 对称 barrier 下 P_win_finiteT ≈ 0.5（martingale）。"""
        p = p_win_finiteT_fourier(1.0, 1.0, sigma=1.0, t_horizon=100.0)
        assert p == pytest.approx(0.5, abs=5e-3)

    def test_p_tau_gt_T_decays(self):
        """T 越大 P(τ > T) 越小。"""
        p1 = p_tau_gt_T_fourier(1.0, 1.0, sigma=1.0, t_horizon=0.5)
        p2 = p_tau_gt_T_fourier(1.0, 1.0, sigma=1.0, t_horizon=5.0)
        p3 = p_tau_gt_T_fourier(1.0, 1.0, sigma=1.0, t_horizon=50.0)
        assert p1 > p2 > p3

    def test_p_tau_gt_T_short_horizon_near_one(self):
        """T → 0 时 P(τ > T) → 1。"""
        p = p_tau_gt_T_fourier(1.0, 1.0, sigma=0.01, t_horizon=1.0)
        assert p == pytest.approx(1.0, abs=5e-3)


# ═══════════════════════════════════════════════════════════
# 通道 B · shaping-theory §2.22.2 · §2.23.6.2 · KF-26
# ═══════════════════════════════════════════════════════════


class TestChannelBMix:
    def test_doob_conservative_R_equals_1(self):
        """R = 1 (对称) 下 E_gross_mix ≡ 0，任意 x（Doob 保守律）。"""
        assert e_gross_mix(0.5, 1.0, 1.0) == pytest.approx(0.0, abs=1e-9)
        assert e_gross_mix(0.13, 3.0, 3.0) == pytest.approx(0.0, abs=1e-9)

    def test_asymmetric_positive(self):
        """R > 1 且 x > 0 下 E_gross_mix > 0（KF-26 核心结论）。"""
        assert e_gross_mix(0.13, 3.0, 9.0) > 0
        assert e_gross_mix(0.2, 2.0, 6.0) > 0

    def test_asymmetric_negative_R_lt_1(self):
        """R < 1 下 E_gross_mix < 0（反通道 B）。"""
        assert e_gross_mix(0.13, 3.0, 1.5) < 0

    def test_zero_x_zero_expectation(self):
        """x = 0 时 λ = 0，退化到 Doob 恒等式 E_gross = 0。"""
        assert e_gross_mix(0.0, 3.0, 9.0) == pytest.approx(0.0, abs=1e-9)

    def test_smallx_approx_matches_exact(self):
        """小 x 二阶展开在 x < 0.10 精度 < 10%（shaping §2.23.6.2 验证表）。

        x=0.10 时相对误差约 15%（表内实测 K_S=3/R=3 误差 3%，
        但那是 x_min 值代入，而非任意 x）。这里取 x=0.05 以更严格测试展开。
        """
        x = 0.05
        k_s, r_ratio = 3.0, 3.0
        k_t = k_s * r_ratio
        exact = e_gross_mix(x, k_s, k_t)
        approx = e_gross_mix_smallx(x, k_s, k_t)
        rel_err = abs(exact - approx) / max(abs(exact), 1e-9)
        assert rel_err < 0.10


class TestXMin:
    def test_corn_1h_numerical_alignment(self):
        """玉米 1h 数值核对（shaping §2.23.5.2 · x_min ≈ 0.053）。"""
        x_min = x_min_smallx(c_side=0.077, k_s=3.0, k_t=9.0)
        assert x_min == pytest.approx(0.053, abs=0.005)

    def test_R_equals_1_undefined(self):
        """R = 1 时 x_min 应引发 ValueError（Doob 极限 x_min → ∞）。"""
        with pytest.raises(ValueError, match="R"):
            x_min_smallx(0.077, 3.0, 3.0)

    def test_R_lt_1_undefined(self):
        """R < 1 时 x_min 无实数解。"""
        with pytest.raises(ValueError):
            x_min_smallx(0.077, 3.0, 1.5)

    def test_cost_square_root_law(self):
        """成本减半 → x_min 减 30%（平方根律）。"""
        base = x_min_smallx(0.077, 3.0, 9.0)
        halved = x_min_smallx(0.077 / 2, 3.0, 9.0)
        ratio = halved / base
        assert ratio == pytest.approx(1.0 / math.sqrt(2), abs=1e-6)

    def test_R_up_x_min_down(self):
        """R 越大 x_min 越低。"""
        xm_r2 = x_min_smallx(0.077, 3.0, 6.0)
        xm_r3 = x_min_smallx(0.077, 3.0, 9.0)
        xm_r4 = x_min_smallx(0.077, 3.0, 12.0)
        assert xm_r2 > xm_r3 > xm_r4
