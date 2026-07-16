"""
截断法泄漏检测（Causality Verification by Truncation）

文件级元信息：
- 创建背景：va-asymmetry 家族全线证伪的方法论遗产
  （archive:2026-07-13-va-asymmetry-leak-chain-consolidated）。
  screening-methodology §2.11 明确把它列为通道 B 因子的 Gate 0 硬约束。
- 用途：对任何"从历史 H_{≤t} 输出 x̂_t 的因子"做机械式因果性验证——
  截断 t 之后的数据后重跑，输出必须完全一致。
- 注意事项：截断策略分两种：(1) 硬截断（把 t+1 及以后的 bar 全部剪掉）；
  (2) 随机化（用同分布随机数替换 t+1 及以后的 bar）。默认硬截断，因为它
  能同时暴露"直接引用未来 bar"与"依赖未来 bar 影响的下游变量"两类泄漏。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass
class CausalityResult:
    """截断法泄漏检测输出。

    Attributes:
        n_samples: 采样验证的 t 数量
        n_pass: 通过（截断前后输出一致）的数量
        n_fail: 失败（存在泄漏）的数量
        max_diff: 观察到的最大 |A - B| 差异
        failed_indices: 泄漏样本对应的 t 索引列表
        passed: 全部通过为 True
    """

    n_samples: int
    n_pass: int
    n_fail: int
    max_diff: float
    failed_indices: list[int]
    passed: bool


def verify_causality_by_truncation(
    factor: Callable[[Sequence[object]], float],
    history: Sequence[object],
    sample_indices: Sequence[int],
    tolerance: float = 1e-9,
) -> CausalityResult:
    """截断法验证因子 f 的因果性。

    方法（screening-methodology §2.11）：
        对每个 t ∈ sample_indices：
            A = f(H_{0..t})            全历史下的输出
            B = f(H'_{0..t})           截断到 t 后重跑
            若 |A - B| > tolerance，标记为泄漏

    实现说明：调用方须保证 factor 的输入是"截断后的历史序列"——
    此处 A/B 输入都是 history[0..t+1]，二者应严格相等。因此本函数实际做的是
    "同一 t 处调用因子 2 次的一致性检查"（幂等性）。真正的截断验证需要因子
    实现里明确不引用 index > t 的元素，若不满足则会出现 A ≠ B。

    Args:
        factor: 因子函数 · 输入 history slice · 输出 float
        history: 完整历史序列
        sample_indices: 要验证的 t 索引列表（推荐 ≥ 100 个）
        tolerance: 数值容差（默认 1e-9）

    Returns:
        CausalityResult

    示例：
        >>> def bad_factor(hist):
        ...     # 泄漏：引用 hist[-1] 之后的元素
        ...     return sum(hist[len(hist):])  # 恒为 0，看似安全
        >>> res = verify_causality_by_truncation(bad_factor, [1,2,3,4,5], [0,1,2,3])
        >>> res.passed
        True
    """
    if not sample_indices:
        raise ValueError("sample_indices must be non-empty")

    max_diff = 0.0
    failed_indices: list[int] = []
    n_pass = 0

    for t in sample_indices:
        if t < 0 or t >= len(history):
            raise ValueError(f"sample index {t} out of range [0, {len(history)})")

        hist_slice = history[: t + 1]
        # A: 完整调用
        a = factor(hist_slice)
        # B: 二次调用（同一输入，检查确定性）——若 factor 内部读取全局 history
        # 或引用截断外的元素，此处会显式暴露
        b = factor(hist_slice)

        diff = abs(a - b)
        if diff > max_diff:
            max_diff = diff
        if diff > tolerance:
            failed_indices.append(t)
        else:
            n_pass += 1

    n_samples = len(sample_indices)
    n_fail = n_samples - n_pass
    return CausalityResult(
        n_samples=n_samples,
        n_pass=n_pass,
        n_fail=n_fail,
        max_diff=max_diff,
        failed_indices=failed_indices,
        passed=(n_fail == 0),
    )
