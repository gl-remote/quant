"""策略决策诊断层 — alpha / risk / execution 三层契约。

三层契约（各自的目的、完整性约束、通用可选字段与策略族建议字段）分别定义在：
    - alpha.py      —— AlphaDiagnostics：为什么该交易
    - risk.py       —— RiskDiagnostics：能不能交易、下多少
    - execution.py  —— ExecutionDiagnostics：如何成交与退出

本入口只暴露三层契约本身，保持对 core.types 的零依赖（避免导入环）。
临时占位工具见同包的 placeholder.py。
"""

from .alpha import AlphaDiagnostics
from .execution import ExecutionDiagnostics
from .risk import RiskDiagnostics

__all__ = [
    "AlphaDiagnostics",
    "RiskDiagnostics",
    "ExecutionDiagnostics",
]
