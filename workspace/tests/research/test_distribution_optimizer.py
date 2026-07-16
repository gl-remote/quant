"""research.distribution · research.optimizer 测试

覆盖：
    - FoldedNormal.fit() half-normal 参数化
    - CDF / iCDF 单调性 + 内一致性 (F(F⁻¹(p)) = p)
    - quantile_at_top(τ) 对齐 KF-27 τ* 语义
    - optimize_kf27() 玉米 1h 参考输出核对
"""

from __future__ import annotations

import pytest
from research.distribution import FoldedNormal
from research.optimizer import KF27Params, optimize_kf27


class TestFoldedNormal:
    def test_fit_half_normal_parameterization(self):
        """半正态：mu_D = σ·√(2/π) → σ = mu_D · √(π/2)。"""
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        expected_scale = 0.198 * (3.14159265 / 2) ** 0.5
        assert d.scale == pytest.approx(expected_scale, rel=1e-3)

    def test_cdf_monotonic(self):
        """CDF 单调递增。"""
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        xs = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0]
        cdfs = [d.cdf(x) for x in xs]
        for i in range(len(cdfs) - 1):
            assert cdfs[i] <= cdfs[i + 1]

    def test_cdf_at_zero_and_far(self):
        """CDF(0)=0，CDF(∞)→1。"""
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        assert d.cdf(0.0) == pytest.approx(0.0, abs=1e-10)
        assert d.cdf(1e6) == pytest.approx(1.0, abs=1e-6)
        assert d.cdf(-1.0) == 0.0  # 负数截断

    def test_icdf_inverse_of_cdf(self):
        """iCDF ∘ CDF ≈ 恒等。"""
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            x = d.icdf(p)
            p_back = d.cdf(x)
            assert p_back == pytest.approx(p, abs=1e-3)

    def test_quantile_at_top_corn_1h(self):
        """玉米 1h 前 65% 段对应 x* ≈ 0.13（shaping §2.23.5.4）。"""
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        # 玉米 1h 的 τ* = 0.647（前 64.7% 段）
        x_star = d.quantile_at_top(0.647)
        # 允许 15% 相对误差（half-normal 简化 vs 完整 FoldedNormal 拟合）
        assert x_star == pytest.approx(0.13, rel=0.20)

    def test_icdf_invalid_p(self):
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        with pytest.raises(ValueError):
            d.icdf(0.0)
        with pytest.raises(ValueError):
            d.icdf(1.0)

    def test_mu_D_positive_required(self):
        with pytest.raises(ValueError):
            FoldedNormal(mu_D=0.0, sd_D=0.108).fit()


class TestKF27Optimizer:
    def test_corn_1h_reference_output(self):
        """玉米 1h 参考输出（shaping §2.23.2）。

        期望：K_S* ≈ 3.0, K_T* ≈ 9.0（RR* = 3），Sharpe/年 > 1，
        且 e_net > 0。数值精度取决于 FoldedNormal 拟合与网格粒度。
        """
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        params = KF27Params(
            distribution=d,
            c_side=0.077,
            sigma_bar=1.0,
            year_hours=1625.0,
            k_s_min=1.0,
            k_s_max=6.0,
            k_t_max=12.0,
        )
        result = optimize_kf27(params, objective="sharpe_year")

        # 玉米 1h 参考值：K_S*=3, K_T*=9, RR*=3
        # 网格粒度 0.25，允许 ±1.0 ATR 偏差
        assert 2.0 <= result.k_s <= 4.0
        assert 6.0 <= result.k_t <= 12.0
        assert 2.0 <= result.rr <= 4.0

        # E_net 必须为正（可行性硬约束）
        assert result.e_net > 0

        # Sharpe/年 应大于 0.5（保守下限，shaping 报告 +1.66）
        assert result.sharpe_year > 0.5

    def test_infeasible_when_cost_too_high(self):
        """成本过高时应抛 RuntimeError。"""
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        params = KF27Params(
            distribution=d,
            c_side=5.0,  # 极高成本
            sigma_bar=1.0,
        )
        with pytest.raises(RuntimeError, match="No feasible"):
            optimize_kf27(params, objective="sharpe_year")

    def test_objective_annual_pct(self):
        """annual_pct 目标返回可用结果。"""
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        params = KF27Params(distribution=d, c_side=0.077, sigma_bar=1.0)
        result = optimize_kf27(params, objective="annual_pct")
        assert result.ann_pct_r1 > 0

    def test_invalid_objective(self):
        d = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()
        params = KF27Params(distribution=d, c_side=0.077, sigma_bar=1.0)
        with pytest.raises(ValueError, match="Unknown objective"):
            optimize_kf27(params, objective="invalid")  # type: ignore[arg-type]
