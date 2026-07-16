"""
Cluster Bootstrap（事件非独立性处理）

文件级元信息：
- 创建背景：shaping-theory §2.6.3 / §2.19.1 / KF-22 沉淀的方法论——
  barrier 触达事件按 (symbol, contract) 内部强相关（同合约相邻 bar 触达路径共享噪声），
  不能用普通 IID bootstrap 估 CI。本模块给出通用的 cluster bootstrap 接口。
- 用途：任何需要给统计量估 CI 但样本内部有 cluster 结构的场景。
- 注意事项：cluster 单位（symbol, contract）由调用方给出；
  抽样单位是"整个 cluster"而非"单 bar"，保留 cluster 内部相关结构。
"""

from __future__ import annotations

import random
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass


@dataclass
class BootstrapResult:
    """Cluster bootstrap 输出。

    Attributes:
        point_estimate: 原样本上的点估计
        samples: n_boot 次重抽样的统计量列表
        ci_low: 95% CI 下界（percentile 2.5）
        ci_high: 95% CI 上界（percentile 97.5）
        mean: 样本均值
        std: 样本标准差
    """

    point_estimate: float
    samples: list[float]
    ci_low: float
    ci_high: float
    mean: float
    std: float


def cluster_bootstrap(
    events: Iterable[dict[str, object]],
    cluster_key: Callable[[dict[str, object]], Hashable],
    statistic: Callable[[list[dict[str, object]]], float],
    n_boot: int = 5000,
    ci: tuple[float, float] = (2.5, 97.5),
    seed: int | None = None,
) -> BootstrapResult:
    """Cluster bootstrap 估计任意统计量的 CI。

    方法（shaping-theory §2.6.3）：
        1. 按 cluster_key 把 events 分成若干 cluster
        2. 每次 bootstrap 以有放回方式抽 |clusters| 个 cluster
        3. 合并抽到的所有 cluster 内 events，重算 statistic
        4. 重复 n_boot 次，取 percentile CI

    Args:
        events: 事件列表（每个是 dict）
        cluster_key: 提取 cluster 键的函数，如 lambda e: (e["symbol"], e["contract"])
        statistic: 在事件列表上算统计量的函数（如 mean(gross)）
        n_boot: bootstrap 次数（默认 5000）
        ci: CI 分位（默认 (2.5, 97.5) = 95% CI）
        seed: 随机种子（复现用）

    Returns:
        BootstrapResult
    """
    event_list = list(events)
    if not event_list:
        raise ValueError("events must be non-empty")

    # 分组
    clusters: dict[Hashable, list[dict[str, object]]] = {}
    for e in event_list:
        key = cluster_key(e)
        clusters.setdefault(key, []).append(e)
    cluster_keys = list(clusters.keys())
    n_clusters = len(cluster_keys)

    if n_clusters < 2:
        raise ValueError(f"Need at least 2 clusters for bootstrap, got {n_clusters}")

    # 原样本点估计
    point = statistic(event_list)

    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(n_boot):
        # 有放回抽 n_clusters 个 cluster
        sampled_keys = [rng.choice(cluster_keys) for _ in range(n_clusters)]
        sampled_events: list[dict[str, object]] = []
        for k in sampled_keys:
            sampled_events.extend(clusters[k])
        samples.append(statistic(sampled_events))

    samples_sorted = sorted(samples)
    lo_idx = int(ci[0] / 100.0 * n_boot)
    hi_idx = int(ci[1] / 100.0 * n_boot)
    lo_idx = max(0, min(n_boot - 1, lo_idx))
    hi_idx = max(0, min(n_boot - 1, hi_idx))

    mean_val = sum(samples) / n_boot
    var_val = sum((s - mean_val) ** 2 for s in samples) / n_boot
    std_val = var_val**0.5

    return BootstrapResult(
        point_estimate=point,
        samples=samples,
        ci_low=samples_sorted[lo_idx],
        ci_high=samples_sorted[hi_idx],
        mean=mean_val,
        std=std_val,
    )
