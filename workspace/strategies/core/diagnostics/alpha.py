"""Alpha 诊断层 — 决策事件中“为什么该交易”的机器可读快照。

这一层回答 Alpha / Research 的问题：这笔交易的方向假设是什么、围绕哪个结构或
共识形成、失败与盈利的参照在哪里。它只描述“信号成立的依据”，不描述下多少手
（属于 risk 层），也不描述如何成交与退出（属于 execution 层）。

完整性约束
----------
任何带 action 的出场/入场信号，alpha 层都必须非空（见 core/base.py 的
DecisionPayloadContract.validate）。空层会在 Signal 出站时直接报错。
目的是强制每个开平仓决策都带上可解释的结构依据，而不是把依据散落在
自然语言 reason 或日志里。尚未实现真实诊断的策略可用
diagnostics.placeholder_diagnostics 装饰器临时补占位。

通用策略（任意类型）可按需选填
------------------------------
    - direction_hypothesis：方向假设，long / short
    - entry_reason：进场依据的结构化标签（不是给人看的句子）
    - signal_strength：信号强度 / 置信度
    - reference_price：本次决策依赖的关键参考价位

结构型参考价位策略族（structural reference-price）建议填
------------------------------------------------------
    - consensus_zone_type：previous_day_high_low / opening_range / initial_balance ...
    - structure_source：price_action / auction / wyckoff ...
    - entry_boundary：入场参考边界
    - strict_failure_boundary：严格失败边界
    - expected_profit_boundary：预期盈利上界
    - acceptance_rejection_evidence：接受 / 拒绝证据类型
    - fast_retouch / fast_retouch_bars：严格边界快速再触及情况

字段值应尽量是数字、枚举和布尔，不要塞展示用字符串；格式化留给报告层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AlphaDiagnostics:
    """Alpha 诊断层载荷。字段由策略按上文约定自行填充，框架只要求非空。"""

    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.fields)

    def is_empty(self) -> bool:
        return not self.fields
