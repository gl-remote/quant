# -*- coding: utf-8 -*-
"""
统计聚合工具 (纯函数)

compute_summary_stats: 数值列表描述性统计
rank_by_key:          对 flat dict 列表按指定键排序

供 backtest (comparison/aggregator) 和 report (sql_reporter) 共用。
"""

from typing import List, Dict, Any, Optional

import numpy as np


def compute_summary_stats(values: List[float]) -> Dict[str, Any]:
    """计算数值列表的描述性统计

    Args:
        values: 数值列表

    Returns:
        {mean, median, std, min, max, count, positive_count, negative_count}
        空列表返回 {}
    """
    if not values:
        return {}
    arr = np.array(values, dtype=float)
    pos = int(np.sum(arr > 0))
    neg = int(np.sum(arr < 0))
    return {
        'mean': float(np.mean(arr)),
        'median': float(np.median(arr)),
        'std': float(np.std(arr)),
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'count': len(values),
        'positive_count': pos,
        'negative_count': neg,
    }


def rank_by_key(
    items: List[Dict],
    key: str,
    reverse: bool = True,
) -> List[Dict]:
    """对 flat dict 列表按指定键排序

    与 backtest/aggregator 中的同名函数不同:
      此版本操作 flat dict (it[key] 直接取值)，不要求 metrics 嵌套结构。

    Args:
        items: 字典列表，每项需包含 key 对应的字段
        key: 排序键名
        reverse: True=降序(越大越好), False=升序(越小越好)

    Returns:
        排序后的字典列表 (原对象引用，非拷贝)
    """
    valid = [it for it in items if it.get(key) is not None]
    return sorted(valid, key=lambda it: it.get(key, 0), reverse=reverse)
