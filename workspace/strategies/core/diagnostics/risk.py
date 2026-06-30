"""Risk 诊断层 — 决策事件中“能不能交易、下多少”的机器可读快照。

这一层回答 Pre-trade Risk / Position Sizing 的问题：在给定入场价、失败边界、
账户权益和合约约束下，这笔交易是否满足风险预算、最终下多少手、若被拒绝原因是
什么。它消费 alpha 层的方向与边界，产出可执行的下单规模，但不负责结构是否成立
（alpha 层），也不负责成交与退出过程（execution 层）。

完整性约束
----------
任何带 action 的出场/入场信号，risk 层都必须非空（见 core/base.py 的
DecisionPayloadContract.validate）。空层会在 Signal 出站时直接报错。
目的是强制每个决策都显式记录风险预算与 sizing 依据，避免把不可交易结构误判为
策略失败，或把风险口径藏在隐式逻辑里。尚未实现真实诊断的策略可用
diagnostics.placeholder_diagnostics 装饰器临时补占位。

通用策略（任意类型）可按需选填
------------------------------
    - account_equity：决策时账户权益
    - target_risk_ratio：目标单次风险比例，例如 0.02 / 0.03
    - actual_volume：实际下单手数
    - account_risk_amount / account_risk_ratio：实际风险金额 / 比例
    - risk_budget_passed：风险预算是否通过
    - risk_budget_reject_reason：未通过原因（枚举，不用自由文本）

结构型参考价位策略族（structural reference-price）建议填
------------------------------------------------------
    - strict_failure_distance：严格失败距离
    - expected_profit_distance：盈利上界距离
    - raw_price_r_multiple：价格原始盈亏比
    - target_risk_amount：目标账户风险金额
    - loss_per_min_volume：最小手数失败损失
    - theoretical_volume：理论手数
    - raw_account_r_multiple：账户原始盈亏比

字段值应尽量是数字、枚举和布尔，不要塞展示用字符串；格式化留给报告层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RiskDiagnostics:
    """Risk 诊断层载荷。字段由策略按上文约定自行填充，框架只要求非空。"""

    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.fields)

    def is_empty(self) -> bool:
        return not self.fields
