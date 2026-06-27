"""策略切面能力库 — 将横切关注点从策略业务逻辑中抽离。

AI/开发者实现新策略或审查策略代码时，先检查这里是否已有可复用切面，
避免在策略类中重复实现方向、确认、止盈止损、冷却等通用逻辑。

核心语义：
- 切面 DSL 以类装饰器声明，运行时先评估表达式并写入 ``ctx.aspects``。
- 切面只给建议，不直接下单；交易决策仍由策略 ``on_bar()`` 消费建议完成。
- 表达式涉及的指标需求会自动合并到 ``data_requirements()``，策略只补充特有需求。
- direction 切面写入 ``ctx.aspects.direction``，risk 切面写入 ``ctx.aspects.risk``。

常用入口：
- ``trend_long`` / ``trend_short``：趋势方向
- ``confirm_long`` / ``confirm_short``：确认条件
- ``exit_for_take_profit`` / ``exit_for_stop_loss``：出场风控建议
- ``entry_block_after_take_profit`` / ``entry_block_after_stop_loss``：入场阻断建议

表达式速览：
- 指标引用：``macd@1m``、``sma({sma_short})@15m``、``atr@15m``
- 配置引用：``{field}``，从策略参数读取
- 内置函数：``cooldown()``、``profit_pct()``、``loss_pct()``、``profit_abs()``、``loss_abs()``、
  ``peak_profit()``、``drawdown_pct()``
- 比较与组合：``> < >= <= == !=``、``&& || and or``，支持括号

使用方式:
    from strategies.strategy_aspects import (
        confirm_long, confirm_short,
        trend_long, trend_short,
        exit_for_take_profit, exit_for_stop_loss,
    )

    @trend_long("sma({sma_short})@15m > sma({sma_long})@15m")
    @confirm_long("macd@1m > 0")
    @exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
    @exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
    class MyStrategy(Strategy[MyParams]):
        ...

继续阅读：
- ``indicators.py``：DSL 可用指标与 ``build_indicator()``
- ``builtins.py``：DSL 内置函数
- ``_parser.py``：表达式语法与求值
- ``predicate.py``：direction/risk 共享的切面谓词协议
- ``requirements.py``：DSL 指标需求自动合并
- ``templates.py``：配置模板值解析
- ``direction/``：方向建议写入与消费语义
- ``risk/``：风控建议写入与消费语义
"""

from ..core.indicators import IndicatorSpec
from .direction import confirm_long, confirm_short, trend_long, trend_short
from .primitives import (
    DirectionAdvice,
    DirectionReason,
    DirectionSideAdvice,
    RiskAdvice,
    RiskReason,
    StrategyAspects,
)

# 风控切面
from .risk import (
    entry_block_after_stop_loss,
    entry_block_after_take_profit,
    exit_for_stop_loss,
    exit_for_take_profit,
)

__all__ = [
    # 协议层
    "DirectionReason",
    "DirectionSideAdvice",
    "DirectionAdvice",
    "RiskReason",
    "RiskAdvice",
    "StrategyAspects",
    "IndicatorSpec",
    # 建议型方向 DSL
    "confirm_long",
    "confirm_short",
    "trend_long",
    "trend_short",
    # 风控切面
    "exit_for_take_profit",
    "exit_for_stop_loss",
    "entry_block_after_take_profit",
    "entry_block_after_stop_loss",
]
