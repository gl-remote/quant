"""建议型方向 DSL — 只写入 ctx.aspects.direction，不直接返回交易信号

这些切面以**类装饰器**形式声明在策略类上：每个 bar 自动评估条件，
满足时向 ctx.aspects.direction 追加一条「方向理由」；同时自动把涉及的
指标需求并入 data_requirements，无需在策略里手写。策略的 on_bar 只需读取
ctx.aspects.direction 做组合判断即可，不与指标读取/注册细节耦合。

## 三个正交轴（可任意组合，共 8 个函数）

对外函数名由三段拼成：``{role}_{direction}_{predicate}``。

- role：``confirm`` / ``trend`` —— 决定理由落入 DirectionSideAdvice 的哪个桶
  （见 primitives.py 的 DirectionSideAdvice）。二者评估逻辑完全相同，仅用于
  分桶与诊断；约定上认为 confirm 是比 trend 更强的判定。
- direction：``long`` / ``short`` —— 写入 direction.long 还是 direction.short。
- predicate：
  - ``when`` —— 「指标 vs 阈值」，签名 ``(metric, op, threshold, *, tag=None)``。
    threshold 可为常量数值，或字符串（从 strategy_config 同名字段取值）。
  - ``when_compare`` —— 「指标 vs 指标」（可跨周期），签名
    ``(left, op, right, *, tag=None)``。

op 取 ``">"`` 或 ``"<"``。tag 用于自定义理由名（reason name）；不传时：
when 默认用 ``metric.name``（如 ``macd_1m``），when_compare 默认用
``f"{left.name}_vs_{right.name}"``（如 ``sma_5m_vs_sma_15m``）。

完整 8 个函数：
``confirm_long_when`` / ``confirm_short_when`` /
``trend_long_when`` / ``trend_short_when`` /
``confirm_long_when_compare`` / ``confirm_short_when_compare`` /
``trend_long_when_compare`` / ``trend_short_when_compare``

## 指标引用 MetricRef

条件里的指标用 ``at(indicator, period)`` 构造，indicator 来自
strategy_aspects 的预定义指标（如 MACD / KDJ）或工厂（如 SMA(...)，支持
``SMA("{sma_short}")`` 模板，运行时从 strategy_config.sma_short 取值）。

## 使用示例

在策略类上叠加多个方向切面（装饰器从下往上声明，建议型切面通常放在
拦截型切面之上）::

    from strategies.strategy_aspects import (
        KDJ, MACD, SMA, at,
        confirm_long_when, confirm_short_when,
        trend_long_when_compare, trend_short_when_compare,
    )

    # ── 做多方向 ──
    @confirm_long_when(at(MACD, "1m"), ">", 0)                 # MACD@1m > 0
    @confirm_long_when(at(KDJ, "1m"), "<", "kdj_oversold")     # KDJ@1m < config.kdj_oversold
    @trend_long_when_compare(                                   # SMA(short)@5m > SMA(long)@5m
        at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "5m")
    )
    # ── 做空方向 ──
    @confirm_short_when(at(MACD, "1m"), "<", 0)
    @confirm_short_when(at(KDJ, "1m"), ">", "kdj_overbought")
    @trend_short_when_compare(
        at(SMA("{sma_short}"), "5m"), "<", at(SMA("{sma_long}"), "5m")
    )
    class MyStrategy(Strategy[MyParams]):
        # 装饰器会自动在类上注册 __direction_keys__（按方向收集所有 reason name）
        __direction_keys__: ClassVar[dict[str, set[str]]]

        def on_bar(self, state, ctx):
            # 读取本 bar 累积的方向理由做组合判断
            long_keys = ctx.aspects.direction.long.keys      # set[str]
            required = type(self).__direction_keys__["long"]
            if required <= long_keys:                         # 声明的理由全部满足
                return Signal(action=TRADE_ACTION_BUY, ...)
            return Signal()

自定义理由名（tag），便于在 diagnostics 中区分同指标的多个条件::

    @confirm_long_when(at(MACD, "1m"), ">", 0, tag="macd_fast_up")

新增的另外两个组合（trend 用阈值、confirm 用指标比较）用法同理::

    @trend_long_when(at(SMA("{sma_long}"), "15m"), ">", "trend_floor")
    @confirm_long_when_compare(at(MACD, "1m"), ">", at(MACD, "5m"))

## 行为细节

- 仅读取当前 bar（索引 -1）的指标值，不回看历史 bar。
- 周期或指标缺失（值为 None）时：不追加理由、也不写 diagnostics。
- 条件即使不满足，只要数据存在就会把指标值写入 ctx.aspects.diagnostics
  （key 为 metric.name），便于复盘。
- 多个同方向切面的 reason name 会自动合并进 __direction_keys__[direction]。

共 8 个组合，全部由 _core._direction_aspect 工厂统一实现。
"""

from ._core import (
    confirm_long_when,
    confirm_long_when_compare,
    confirm_short_when,
    confirm_short_when_compare,
    trend_long_when,
    trend_long_when_compare,
    trend_short_when,
    trend_short_when_compare,
)

__all__ = [
    "confirm_long_when",
    "confirm_short_when",
    "trend_long_when",
    "trend_short_when",
    "confirm_long_when_compare",
    "confirm_short_when_compare",
    "trend_long_when_compare",
    "trend_short_when_compare",
]
