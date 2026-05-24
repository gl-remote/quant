# -*- coding: utf-8 -*-
"""
绩效指标计算工具 — re-export from lib.metrics

纯函数已移至 lib/metrics.py，此处保留向后兼容的导入路径。
新代码请直接 from lib.metrics import ...。
"""

from lib.metrics import calc_max_drawdown, calc_sharpe_ratio

__all__ = ['calc_max_drawdown', 'calc_sharpe_ratio']
