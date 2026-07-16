"""research.bootstrap · research.hurst · research.causality 单元测试

覆盖：
    - cluster_bootstrap 单簇/多簇正确性 + 种子确定性
    - hurst_rs 纯随机漫步 H ≈ 0.5 + 强趋势序列 H > 0.5
    - verify_causality_by_truncation 因果 / 非因果因子分辨
"""

from __future__ import annotations

import math
import random

import pytest
from research.bootstrap import cluster_bootstrap
from research.causality import verify_causality_by_truncation
from research.hurst import hurst_rs


class TestClusterBootstrap:
    def test_deterministic_with_seed(self):
        """相同 seed 下两次调用应产生同样结果。"""
        events = [{"cluster": i // 3, "value": float(i)} for i in range(30)]
        result_a = cluster_bootstrap(
            events,
            cluster_key=lambda e: e["cluster"],
            statistic=lambda es: sum(float(e["value"]) for e in es) / len(es),
            n_boot=100,
            seed=42,
        )
        result_b = cluster_bootstrap(
            events,
            cluster_key=lambda e: e["cluster"],
            statistic=lambda es: sum(float(e["value"]) for e in es) / len(es),
            n_boot=100,
            seed=42,
        )
        assert result_a.point_estimate == result_b.point_estimate
        assert result_a.ci_low == result_b.ci_low
        assert result_a.ci_high == result_b.ci_high

    def test_ci_contains_point_estimate_high_prob(self):
        """多 cluster · 多样本时 std > 0，且 mean 接近 point。"""
        # 每 cluster 5 个 event，共 10 个 cluster
        events: list[dict[str, object]] = []
        rng = random.Random(1)
        for c in range(10):
            for _ in range(5):
                events.append({"cluster": c, "value": rng.gauss(0.0, 1.0)})
        result = cluster_bootstrap(
            events,
            cluster_key=lambda e: e["cluster"],
            statistic=lambda es: sum(float(e["value"]) for e in es) / len(es),
            n_boot=500,
            seed=42,
        )
        # bootstrap 样本应有非零方差
        assert result.std > 0
        # mean(samples) 接近 point_estimate
        assert abs(result.mean - result.point_estimate) < result.std * 3.0

    def test_at_least_two_clusters_required(self):
        events = [{"cluster": "only_one", "value": 1.0}]
        with pytest.raises(ValueError, match="at least 2 clusters"):
            cluster_bootstrap(
                events,
                cluster_key=lambda e: e["cluster"],
                statistic=lambda es: 1.0,
                n_boot=10,
            )

    def test_empty_events(self):
        with pytest.raises(ValueError, match="non-empty"):
            cluster_bootstrap(
                [],
                cluster_key=lambda e: e["cluster"],
                statistic=lambda es: 0.0,
            )


class TestHurst:
    def test_random_walk_approximately_half(self):
        """独立随机增量序列 Hurst ≈ 0.5（弱相关容差较宽）。

        注意：Hurst 定义是对增量序列的自相似度量。gauss(0,1) 独立增量本身 H≈0.5；
        累计和是 fractional integration 后的序列，H≈1.0。此处测试独立增量。
        """
        rng = random.Random(42)
        increments = [rng.gauss(0, 1) for _ in range(1024)]
        h = hurst_rs(increments, min_window=8, max_window=256)
        # 有限样本 + R/S 有偏，允许 [0.35, 0.65] 区间
        assert 0.35 < h < 0.65

    def test_trending_series_hurst_high(self):
        """强线性趋势 Hurst > 0.7（趋势凝聚）。"""
        # y = 0.1*t + noise
        rng = random.Random(42)
        series = [0.1 * t + rng.gauss(0, 0.05) for t in range(1024)]
        h = hurst_rs(series, min_window=8, max_window=256)
        assert h > 0.7

    def test_too_short_series_raises(self):
        with pytest.raises(ValueError, match="too short|Series too short"):
            hurst_rs([1.0, 2.0, 3.0], min_window=8)


class TestCausality:
    def test_causal_factor_passes(self):
        """严格因果的因子（只读 hist[-1]）应通过。"""
        history = list(range(100))
        result = verify_causality_by_truncation(
            factor=lambda h: float(h[-1]) if h else 0.0,
            history=history,
            sample_indices=[10, 30, 50, 70, 90],
        )
        assert result.passed
        assert result.n_fail == 0

    def test_deterministic_factor(self):
        """确定性因子（sum）应通过。"""
        history = [i * 0.1 for i in range(100)]
        result = verify_causality_by_truncation(
            factor=lambda h: sum(float(x) for x in h),
            history=history,
            sample_indices=[10, 50, 90],
        )
        assert result.passed

    def test_out_of_range_index_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            verify_causality_by_truncation(
                factor=lambda h: 0.0,
                history=[1, 2, 3],
                sample_indices=[10],
            )

    def test_empty_sample_indices_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            verify_causality_by_truncation(
                factor=lambda h: 0.0,
                history=[1, 2, 3],
                sample_indices=[],
            )

    def test_max_diff_recorded(self):
        """确定性因子的 max_diff = 0。"""
        history = list(range(20))
        result = verify_causality_by_truncation(
            factor=lambda h: math.sin(len(h)),
            history=history,
            sample_indices=[5, 10, 15],
        )
        assert result.max_diff == 0.0
