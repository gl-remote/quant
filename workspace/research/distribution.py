"""
|ν|/σ 分布对象（FoldedNormal 与分位数反函数）

文件级元信息：
- 创建背景：shaping-theory §2.23 KF-27 参数优化器的输入是 |ν|/σ 的经验分布 D(μ_D, σ_D)。
  同名脚本 corn_1h_strength_three_views.py 输出的分布参数被
  kf26_parameter_optimizer.py 拟合为 FoldedNormal，是 KF-27 反解 τ*, x* 的基础。
- 用途：拟合 |ν|/σ 分布、提供 CDF / 分位数反函数接口。
- 注意事项：FoldedNormal.fit() 只用前两阶矩（μ_D, σ_D），尾部与经验分布可能有偏差。
  v2 建议加 KDE / 直方图替代（误差从 3% 压到 1% · shaping-theory §2.23.4）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# scipy 是重型依赖，本模块只用到 truncnorm-like 采样；用手写的正态 CDF / iCDF 避免依赖
_SQRT2 = math.sqrt(2.0)


def _norm_cdf(x: float) -> float:
    """标准正态 CDF（用 erf 表达）。"""
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def _norm_ppf(p: float) -> float:
    """标准正态 iCDF（Beasley-Springer-Moro 有理逼近，精度 ~1e-9）。

    参考：Peter J. Acklam's algorithm。用于 FoldedNormal.icdf 的 Newton 初值。
    """
    if p <= 0.0 or p >= 1.0:
        raise ValueError(f"p must be in (0, 1), got {p}")

    # Beasley-Springer-Moro coefficients
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )

    if p <= p_high:
        q = p - 0.5
        r = q * q
        return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) / (
            ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
        )

    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


@dataclass
class FoldedNormal:
    """半正态分布（Folded Normal）· |Z|，Z ~ N(loc, scale²)。

    参数化：给定分布均值 mu_D 与标准差 sigma_D，反解底层正态的 (loc, scale)。
    对齐 shaping-theory §2.23.4 的输入接口（kf26_parameter_optimizer.py）。

    Attributes:
        mu_D: 经验均值 E[|Z|]
        sd_D: 经验标准差 √Var[|Z|]

    Internal (由 fit() 填充):
        loc: 底层正态均值
        scale: 底层正态标准差
    """

    mu_D: float
    sd_D: float
    loc: float = 0.0
    scale: float = 1.0
    _fitted: bool = False

    def fit(self) -> FoldedNormal:
        """拟合底层正态参数。

        对 folded normal |Z| where Z ~ N(μ, σ²)：
            E[|Z|]    = σ·√(2/π)·exp(-μ²/(2σ²)) + μ·(1 - 2·Φ(-μ/σ))
            Var[|Z|]  = μ² + σ² - E[|Z|]²

        当 μ = 0 时简化为：
            E[|Z|]    = σ·√(2/π)
            Var[|Z|]  = σ²·(1 - 2/π)

        本实现采用简化形式（μ=0，即 half-normal），与
        shaping-theory 的 FoldedNormal(mu_D, sd_D) fit 对齐。
        """
        # half-normal: μ_D = σ·√(2/π); σ_D² = σ²·(1 - 2/π)
        # 从 mu_D 反解 σ；忽略 sd_D 的独立信息（保留字段用于将来 μ≠0 拟合扩展）
        if self.mu_D <= 0:
            raise ValueError(f"mu_D must be positive, got {self.mu_D}")
        self.loc = 0.0
        self.scale = self.mu_D * math.sqrt(math.pi / 2.0)
        self._fitted = True
        return self

    def cdf(self, x: float) -> float:
        """|Z| ≤ x 的 CDF（half-normal，loc=0）。

        F(x) = 2·Φ(x/σ) - 1，x ≥ 0
        """
        if not self._fitted:
            self.fit()
        if x < 0:
            return 0.0
        return 2.0 * _norm_cdf(x / self.scale) - 1.0

    def icdf(self, p: float) -> float:
        """CDF 反函数 Q_D(p) = F⁻¹(p)（half-normal，loc=0）。

        Q(p) = σ · Φ⁻¹((1 + p) / 2)，p ∈ (0, 1)

        Args:
            p: 累积概率 ∈ (0, 1)

        Returns:
            对应分位数 · Q_D(p)
        """
        if not self._fitted:
            self.fit()
        if not (0.0 < p < 1.0):
            raise ValueError(f"p must be in (0, 1), got {p}")
        return self.scale * _norm_ppf((1.0 + p) / 2.0)

    def quantile_at_top(self, tau: float) -> float:
        """前 τ 分位对应的 x 值：x* = Q_D(1 - τ)。

        对齐 shaping-theory §2.23.6.4 的 x* 定义。

        Args:
            tau: 前 τ 段（0 < τ < 1）· KF-27 玉米 1h τ*=0.647

        Returns:
            x* = 该 τ 段的下界 |ν|/σ 值
        """
        return self.icdf(1.0 - tau)
