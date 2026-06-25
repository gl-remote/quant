"""风控切面 — 建议型切面，触发时将 RiskReason 写入 ctx.aspects.risk

与 direction 模块一致：切面只向 ctx.aspects 填信息，把决策权交给策略。
它们同样以**类装饰器**形式声明在策略类上，AST 节点按需自动把所需指标（如 ATR）
并入 data_requirements，无需在策略里手写。

## 使用示例

风控切面与方向切面一样，以装饰器声明在策略类上。运行时所有切面先把建议
写入 ``ctx.aspects``，随后策略原始 ``on_bar`` 执行，在内部自行消费这些建议：

    from strategies.strategy_aspects import (
        exit_take_profit, exit_stop_loss,
        entry_block_take_profit, entry_block_stop_loss,
        FixedRatioNode, AtrNode, TrailingNode, CooldownNode,
    )

    # ── 方向切面（外层）──
    @confirm_long_when(at(MACD, "1m"), ">", 0)
    # ── 风控切面（内层）──
    @entry_block_take_profit(CooldownNode("take_profit", minutes=10))
    @entry_block_stop_loss(CooldownNode("stop_loss", minutes=10))
    @exit_take_profit(TrailingNode("15m"))
    @exit_take_profit(AtrNode("take_profit", "15m"))
    @exit_stop_loss(AtrNode("stop_loss", "15m"))
    @exit_take_profit(FixedRatioNode("take_profit"))
    @exit_stop_loss(FixedRatioNode("stop_loss"))
    class MyStrategy(Strategy[MyParams]):
        def on_bar(self, state, ctx):
            # 策略自行消费方向建议与风控建议
            exit_reasons = ctx.aspects.risk.take_profit.exit + ctx.aspects.risk.stop_loss.exit
            if exit_reasons:
                # 出场（策略可自定义优先级）
                return self._exit(state, ctx)
            # 无风控 exit → 正常入场决策
            ...

## 消费语义

与 direction 的 AND/子集不同，risk 的消费语义由**策略自己定义**：

- 框架不内置优先级、不自动聚合、不短路
- 策略可遍历 ``ctx.aspects.risk.all_reasons``，按名称过滤、排序或组合决策
- 建议调用 ``ctx.aspects.flush_diagnostics()`` 将 risk 信息展平到
  ``diagnostics``，便于复盘与日志输出

## 行为细节

- 出场切面只在 ``state.position.direction`` 非空（有持仓）时检查；
  cooldown 只在空仓时检查。
- 依赖 ATR 的切面在指标缺失（``None``）或 ≤0 时静默跳过，不会误触发。
- 切面不再构造或返回 Signal，所有交易决策由策略 ``on_bar`` 完成。
"""

from ._ast import AtrNode, CooldownNode, FixedRatioNode, TrailingNode
from ._core import (
    entry_block_stop_loss,
    entry_block_take_profit,
    exit_stop_loss,
    exit_take_profit,
)

__all__ = [
    "exit_take_profit",
    "exit_stop_loss",
    "entry_block_take_profit",
    "entry_block_stop_loss",
    "FixedRatioNode",
    "AtrNode",
    "TrailingNode",
    "CooldownNode",
]
