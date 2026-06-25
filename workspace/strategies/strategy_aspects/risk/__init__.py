"""风控切面 — 建议型切面，触发时将 RiskReason 写入 ctx.aspects.risk

与 direction 模块一致：切面只向 ctx.aspects 填信息，把决策权交给策略。
它们同样以**类装饰器**形式声明在策略类上，按需自动把所需指标（如 ATR）
并入 data_requirements，无需在策略里手写。

## 切面一览

| 切面 | 形态 | 触发时机 | 写入位置 |
|------|------|----------|----------|
| ``with_take_profit`` | 装饰器工厂 | 有持仓 | ``risk.take_profit.exit`` |
| ``with_stop_loss`` | 装饰器工厂 | 有持仓 | ``risk.stop_loss.exit`` |
| ``with_take_profit_atr`` | 装饰器工厂 | 有持仓 | ``risk.take_profit.exit`` |
| ``with_stop_loss_atr`` | 装饰器工厂 | 有持仓 | ``risk.stop_loss.exit`` |
| ``with_trailing_take_profit`` | 装饰器工厂 | 有持仓 | ``risk.take_profit.exit`` |
| ``with_cooldown_after_take_profit`` | 装饰器工厂 | 空仓 | ``risk.take_profit.entry_block`` |
| ``with_cooldown_after_stop_loss`` | 装饰器工厂 | 空仓 | ``risk.stop_loss.entry_block`` |

## 使用示例

风控切面与方向切面一样，以装饰器声明在策略类上。运行时所有切面先把建议
写入 ``ctx.aspects``，随后策略原始 ``on_bar`` 执行，在内部自行消费这些建议：

    from strategies.strategy_aspects import (
        with_take_profit, with_stop_loss,
        with_take_profit_atr, with_stop_loss_atr,
        with_trailing_take_profit,
        with_cooldown_after_take_profit,
        with_cooldown_after_stop_loss,
    )

    # ── 方向切面（外层）──
    @confirm_long_when(at(MACD, "1m"), ">", 0)
    # ── 风控切面（内层）──
    @with_cooldown_after_take_profit(minutes=10)
    @with_cooldown_after_stop_loss(minutes=30)
    @with_trailing_take_profit("15m")
    @with_take_profit_atr("15m")
    @with_stop_loss_atr("15m")
    @with_take_profit()
    @with_stop_loss()
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

from ._cooldown_after_stop_loss import with_cooldown_after_stop_loss
from ._cooldown_after_take_profit import with_cooldown_after_take_profit
from ._stop_loss import with_stop_loss
from ._stop_loss_atr import with_stop_loss_atr
from ._take_profit import with_take_profit
from ._take_profit_atr import with_take_profit_atr
from ._trailing_take_profit import with_trailing_take_profit

__all__ = [
    "with_take_profit",
    "with_stop_loss",
    "with_take_profit_atr",
    "with_stop_loss_atr",
    "with_trailing_take_profit",
    "with_cooldown_after_take_profit",
    "with_cooldown_after_stop_loss",
]
