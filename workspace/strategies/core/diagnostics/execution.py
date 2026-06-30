"""Execution 诊断层 — 决策事件中“如何成交与退出”的机器可读快照。

这一层回答 Execution / Backtest Simulation 的问题：结构候选与风险预算如何转化为
可回测的交易生命周期——入场怎么触发、退出来自什么原因、持仓经历了多少不利 / 有利
波动。它消费 alpha 层的结构边界和 risk 层的下单规模，但不拥有最终账务口径
（手续费、滑点、realized PnL 属于清算层）。

完整性约束
----------
任何带 action 的出场/入场信号，execution 层都必须非空（见 core/base.py 的
DecisionPayloadContract.validate）。空层会在 Signal 出站时直接报错。
目的是强制每笔交易都带上结构化执行诊断，让 exit reason 可枚举、可统计，
而不是依赖自然语言拼接。尚未实现真实诊断的策略可用
diagnostics.placeholder_diagnostics 装饰器临时补占位。

通用策略（任意类型）可按需选填
------------------------------
    - exit_reason：退出原因枚举，strict_failure / take_profit / time_exit /
      relaxed_stop / abnormal ...
    - holding_bars：持仓 K 线数
    - actual_volume：实际执行手数（来自 risk 层）

结构型参考价位策略族（structural reference-price）建议填
------------------------------------------------------
    - exit_policy：strict / take_profit / time_exit / relaxed_stop
    - strict_stop_distance / actual_stop_distance：严格 / 实际止损距离
    - stop_relaxation_multiple：止损放宽倍数
    - position_adjustment_multiple：维持风险预算所需仓位调整倍数
    - mae / mfe：最大不利 / 有利波动
    - mae_r / mfe_r：MAE / MFE 相对严格失败距离的 R 化
    - fast_retouch：是否快速再触及严格边界

字段缺失时显式为 null，不要写入展示字符串；格式化留给报告层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionDiagnostics:
    """Execution 诊断层载荷。字段由策略按上文约定自行填充，框架只要求非空。"""

    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.fields)

    def is_empty(self) -> bool:
        return not self.fields
