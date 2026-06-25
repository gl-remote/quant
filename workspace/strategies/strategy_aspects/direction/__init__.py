"""建议型方向 DSL — 字符串表达式版本

这些切面以**类装饰器**形式声明在策略类上：每个 bar 自动评估表达式，
满足时向 ctx.aspects.direction 追加一条「方向理由」；同时自动把涉及的
指标需求并入 data_requirements，无需在策略里手写。

## 用法

::

    from strategies.strategy_aspects import (
        confirm_long, confirm_short, trend_long, trend_short,
    )

    # ── 做多方向 ──
    @confirm_long("macd@1m > 0")
    @confirm_long("kdj@1m < {kdj_oversold}")
    @trend_long("sma({sma_short})@5m > sma({sma_long})@5m")
    # ── 做空方向 ──
    @confirm_short("macd@1m < 0")
    @confirm_short("kdj@1m > {kdj_overbought}")
    @trend_short("sma({sma_short})@5m < sma({sma_long})@5m")
    class MyStrategy(Strategy[MyParams]):
        ...

## 表达式语法

- 指标引用：``indicator@period``，如 ``macd@1m``、``sma({param})@5m``
- 配置引用：``{field}``，从 strategy_config 读取字段
- 内置函数：``cooldown()``、``profit_abs()`` 等（风控场景）
- 比较：``> < >= <= == !=``
- 布尔组合：``&& || and or``，支持括号分组
- 自定义理由名：``@confirm_long("macd@1m > 0", tag="macd_fast_up")``

详见 ``_parser.py`` 及 ``docs/roadmap/decorator-string-dsl.md``。
"""

from ._core import confirm_long, confirm_short, trend_long, trend_short

__all__ = [
    "confirm_long",
    "confirm_short",
    "trend_long",
    "trend_short",
]
