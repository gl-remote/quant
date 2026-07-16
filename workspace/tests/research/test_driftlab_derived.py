"""research.driftlab · research.derived 单元测试

覆盖：
    - dual_channel_drift_test 显著漂移正 / 无漂移 / 通道 B 数值不稳
    - mu_sensitivity 5 档 E[net] 单调性 + μ* 求解
    - k_t_feasible_range 空集 / 窄 / 宽 三种 verdict
    - kelly_position 负期望 → 0、部分凯利上限
    - t_dagger_empirical 经验规则
"""

from __future__ import annotations

import pytest
from research.derived import (
    e_gross_at_mu,
    k_t_feasible_range,
    kelly_position,
    mu_sensitivity,
    t_dagger_empirical,
)
from research.driftlab import dual_channel_drift_test


# ═══════════════════════════════════════════════════════════
# driftlab · 双通道漂移探测器
# ═══════════════════════════════════════════════════════════


class TestDualChannelDrift:
    def test_no_drift_null_case(self):
        """观测比例接近零漂移 Fourier null → verdict='no_drift'。

        K_S=1, K_T=1, sigma=1, T=1 · 实测 p_win_theory ≈ 0.311、p_tau_theory ≈ 0.371。
        构造 n_win=31, n_time_exit=37 让两通道 z 都接近 0。
        """
        result = dual_channel_drift_test(
            n_win=31,
            n_time_exit=37,
            n_total=100,
            k_s=1.0,
            k_t=1.0,
            sigma=1.0,
            t_horizon=1.0,
        )
        assert result.b_channel_valid
        assert result.verdict == "no_drift"
        assert abs(result.z_a) < 2.0
        assert abs(result.z_b) < 2.0

    def test_drift_positive_case(self):
        """观测 P_win 远高于 null + P(τ>T) 远低于 null → drift_positive。

        p_win_theory ≈ 0.311, p_tau_theory ≈ 0.371。构造 n_win=80（远超 31）,
        n_time_exit=5（远低于 37）。
        """
        result = dual_channel_drift_test(
            n_win=80,
            n_time_exit=5,
            n_total=100,
            k_s=1.0,
            k_t=1.0,
            sigma=1.0,
            t_horizon=1.0,
        )
        assert result.b_channel_valid
        assert result.z_a > 2.0
        assert result.z_b < -2.0
        assert result.verdict == "drift_positive"

    def test_b_channel_unstable(self):
        """T 足够大 · p_tau_theory < 1e-3 时通道 B 应标记 invalid。"""
        # K_S=1, K_T=1, sigma=1, T=100 (远大于 T*=1) · p_tau→0
        result = dual_channel_drift_test(
            n_win=55,
            n_time_exit=0,
            n_total=100,
            k_s=1.0,
            k_t=1.0,
            sigma=1.0,
            t_horizon=100.0,
        )
        assert not result.b_channel_valid
        # 只用通道 A · z_A ≈ (0.55 - 0.5) / 0.0497 ≈ 1.0 · 未过 threshold
        assert result.verdict == "no_drift"

    def test_b_channel_only_positive(self):
        """B 不 valid 但 A 显著正 → 'channel_a_only'。"""
        # 构造 n_win 让 z_A 显著（>2），T 大让 B invalid
        result = dual_channel_drift_test(
            n_win=90,
            n_time_exit=0,
            n_total=100,
            k_s=1.0,
            k_t=1.0,
            sigma=1.0,
            t_horizon=100.0,
        )
        assert not result.b_channel_valid
        assert result.z_a > 2.0
        assert result.verdict == "channel_a_only"

    def test_invalid_inputs(self):
        with pytest.raises(ValueError):
            dual_channel_drift_test(n_win=0, n_time_exit=0, n_total=0, k_s=1.0, k_t=1.0, sigma=1.0, t_horizon=1.0)
        with pytest.raises(ValueError, match="Invalid counts"):
            dual_channel_drift_test(n_win=50, n_time_exit=60, n_total=100, k_s=1.0, k_t=1.0, sigma=1.0, t_horizon=1.0)


# ═══════════════════════════════════════════════════════════
# derived · μ 敏感性
# ═══════════════════════════════════════════════════════════


class TestMuSensitivity:
    def test_5_grid_length(self):
        """5 档 μ 格点长度对齐。"""
        result = mu_sensitivity(k_s=3.0, k_t=9.0, sigma=1.0, c_side=0.077)
        assert len(result.mu_grid) == 5
        assert len(result.e_net_grid) == 5

    def test_monotonic_in_mu(self):
        """E[net] 应随 μ 单调递增（R > 1 时 λ↑ → P_win↑ → E_gross↑）。"""
        result = mu_sensitivity(k_s=3.0, k_t=9.0, sigma=1.0, c_side=0.077)
        for i in range(len(result.e_net_grid) - 1):
            assert result.e_net_grid[i] <= result.e_net_grid[i + 1]

    def test_symmetric_barrier_mu_star_positive(self):
        """K_S=K_T 对称下 λ=0 → E[net]=-2c < 0，需要正 μ 补偿。"""
        result = mu_sensitivity(k_s=1.0, k_t=1.0, sigma=1.0, c_side=0.05)
        # μ*应该存在且 > 0（因为 μ=0 下 E[net] = -0.1）
        assert result.mu_star is not None
        assert result.mu_star > 0

    def test_infeasible_high_cost(self):
        """成本极高 → μ* 可能超出 [-2σ, 2σ] 或不存在。"""
        result = mu_sensitivity(k_s=1.0, k_t=1.0, sigma=1.0, c_side=100.0)
        assert result.verdict == "infeasible"


# ═══════════════════════════════════════════════════════════
# derived · K_T 可行区间
# ═══════════════════════════════════════════════════════════


class TestKTFeasibleRange:
    def test_target_p_50_percent(self):
        """P_target=50% → K_T_target = K_S。"""
        r = k_t_feasible_range(k_s=1.5, p_target=0.5, sigma=1.0, t_horizon=1.0)
        assert r.k_t_target == pytest.approx(1.5, abs=1e-9)

    def test_target_p_33_percent(self):
        """P_target=33% → K_T_target = 2 · K_S。"""
        r = k_t_feasible_range(k_s=1.5, p_target=1.0 / 3, sigma=1.0, t_horizon=1.0)
        assert r.k_t_target == pytest.approx(3.0, abs=1e-6)

    def test_k_t_max_scales_sqrt_T(self):
        """K_T_max = k · σ · √T · T=100 → K_T_max=20（k=2, σ=1）。"""
        r = k_t_feasible_range(k_s=1.0, p_target=0.5, sigma=1.0, t_horizon=100.0)
        assert r.k_t_max == pytest.approx(20.0, abs=1e-9)

    def test_wide_verdict(self):
        """K_T_max >> K_T_target → 'wide' 强候选。"""
        r = k_t_feasible_range(k_s=1.0, p_target=0.5, sigma=1.0, t_horizon=100.0)
        assert r.verdict == "wide"

    def test_empty_verdict(self):
        """K_S 极大 → K_T_target > K_T_max → 'empty'。"""
        r = k_t_feasible_range(k_s=100.0, p_target=0.1, sigma=1.0, t_horizon=1.0)
        # K_T_target = 100·0.9/0.1 = 900, K_T_max = 2 · 1 · 1 = 2
        assert r.verdict == "empty"

    def test_invalid_p_target(self):
        with pytest.raises(ValueError):
            k_t_feasible_range(k_s=1.0, p_target=0.0, sigma=1.0, t_horizon=1.0)


# ═══════════════════════════════════════════════════════════
# derived · 凯利仓位
# ═══════════════════════════════════════════════════════════


class TestKellyPosition:
    def test_positive_e_net(self):
        """E[net]=1, K_S=3, K_T=9, α=0.5 → f = 0.5 · 1/27 ≈ 0.0185。"""
        f = kelly_position(e_net=1.0, k_s=3.0, k_t=9.0, alpha=0.5)
        assert f == pytest.approx(0.5 / 27, abs=1e-9)

    def test_negative_e_net_returns_zero(self):
        """E[net]≤0 → f=0。"""
        assert kelly_position(e_net=-0.5, k_s=1.0, k_t=1.0) == 0.0
        assert kelly_position(e_net=0.0, k_s=1.0, k_t=1.0) == 0.0

    def test_f_max_cap(self):
        """f_max 硬上限生效。"""
        # 极高 e_net · 全凯利会很大
        f = kelly_position(e_net=100.0, k_s=1.0, k_t=1.0, alpha=1.0, f_max=0.1)
        assert f == 0.1

    def test_invalid_alpha(self):
        with pytest.raises(ValueError):
            kelly_position(e_net=1.0, k_s=1.0, k_t=1.0, alpha=0.0)


# ═══════════════════════════════════════════════════════════
# derived · T† 经验规则
# ═══════════════════════════════════════════════════════════


class TestTDagger:
    def test_default_half_horizon(self):
        """默认 k_drift=0.5 · T†=T/2。"""
        assert t_dagger_empirical(100.0) == pytest.approx(50.0, abs=1e-9)

    def test_positive_input_required(self):
        with pytest.raises(ValueError):
            t_dagger_empirical(0.0)


# ═══════════════════════════════════════════════════════════
# derived · e_gross_at_mu
# ═══════════════════════════════════════════════════════════


class TestEGrossAtMu:
    def test_zero_drift_after_ito(self):
        """μ=σ²/2 时 ν=0 → λ=0 → 对称 barrier E[gross]=0。"""
        # σ=1, μ=0.5 → ν=0
        eg = e_gross_at_mu(mu=0.5, sigma=1.0, k_s=1.0, k_t=1.0)
        assert eg == pytest.approx(0.0, abs=1e-9)

    def test_positive_drift(self):
        """μ 大 → E[gross] > 0（R>1 塑形）。"""
        eg = e_gross_at_mu(mu=1.0, sigma=1.0, k_s=3.0, k_t=9.0)
        assert eg > 0
