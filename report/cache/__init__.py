# -*- coding: utf-8 -*-
"""缓存模块

提供统一的缓存管理能力，包括：
- BuildCache: 增量构建缓存管理器（数据指纹、前端哈希）
- KlineCache: K线数据转换缓存（CSV→JSON）
"""

from .build import BuildCache
from .kline import KlineCache

__all__ = ["BuildCache", "KlineCache"]
