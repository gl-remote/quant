"""风控切面 — 拦截型切面，触发后直接返回 Signal 提前出场或阻断入场

与建议型方向 DSL（见 direction 模块）相反：方向切面只向 ctx.aspects 填信息、
把决策权交给策略；风控切面则是**拦截型**——条件满足时直接构造并返回 Signal，
短路掉策略原始的 on_bar 逻辑。它们同样以**类装饰器**形式声明在策略类上，按需
自动把所需指标（如 ATR）并入 data_requirements，无需在策略里手写。

## 四个切面一览

| 切面 | 形态 | 触发时机 | 作用 |
|------|------|----------|------|
| ``with_stop_take_profit`` | 裸装饰器 | 有持仓 | 固定比例止盈/止损 |
| ``with_atr_stop_take_profit`` | 装饰器工厂 | 有持仓 | ATR 倍数止盈/止损 |
| ``with_trailing_stop`` | 装饰器工厂 | 有持仓 | 回撤（移动）止盈 |
| ``with_trade_cooldown`` | 装饰器工厂 | 空仓 | 成交后冷却期阻断入场 |

止盈/止损出场触发时返回带 ``reason`` 的平仓 Signal（``reason`` 取
common.constants 的 ``SIGNAL_TAKE_PROFIT`` / ``SIGNAL_STOP_LOSS``）；冷却阻断
返回 ``action=""``、``reason=SIGNAL_TRADE_COOLDOWN`` 的空信号。所有出场切面
都向 ``ctx.aspects.diagnostics`` 写入 ``entry_price`` / ``highest_price`` /
``lowest_price`` / ``current_close``，便于复盘。

## 各切面签名与所需 config

- ``with_stop_take_profit``（裸装饰器，直接 ``@with_stop_take_profit``）
  - 需要 ``config.take_profit_ratio: float``、``config.stop_loss_ratio: float``。
  - 有持仓时按入场价比例检查；**止盈优先级高于止损**。

- ``with_atr_stop_take_profit(period="15m")``
  - 需要 ``config.atr_period: int``、``config.atr_take_profit_multiplier: float``、
    ``config.atr_stop_loss_multiplier: float``。
  - 自动把 ATR 指标注册到 ``period`` 周期的 data_requirements。
  - 多头：``close > entry + atr*tp_mult`` 止盈，``close < entry - atr*sl_mult`` 止损；
    空头方向相反。**止盈优先于止损**。ATR 缺失或 ≤0 时跳过、交后续逻辑。

- ``with_trailing_stop(period="15m")``
  - 需要 ``config.atr_period: int``、``config.trailing_activation_atr: float``（激活倍数）、
    ``config.trailing_drawdown_ratio: float``（回撤比例）。
  - 自动注册 ATR 指标。多头取 ``highest_price`` 为峰值、空头取 ``lowest_price``。
  - 仅当峰值相对入场价超过 ``atr*activation`` 后才激活；激活后从峰值回撤超过
    ``drawdown_ratio`` 即止盈。峰值未初始化（≤0）或 ATR 缺失时跳过。

- ``with_trade_cooldown(minutes: int)``
  - 不依赖额外指标。基于 ``state.fills`` 中最近一笔成交时间计算。
  - **仅在空仓时**阻断新入场（``elapsed < minutes`` 则返回冷却信号），
    不影响已有持仓的止盈止损出场。

## 使用示例

风控切面声明在方向切面**内层**（更靠下）。装饰器自下而上包装，运行时自外向内
执行：方向切面在最外层先把建议写入 ctx.aspects，随后各风控切面依次检查，任一
触发即短路返回 Signal；都未触发才进入策略原始 on_bar::

    from strategies.strategy_aspects import (
        with_stop_take_profit, with_atr_stop_take_profit,
        with_trailing_stop, with_trade_cooldown,
    )

    # ── 方向切面（外层，仅填 ctx.aspects）──
    @confirm_long_when(at(MACD, "1m"), ">", 0)
    # ── 风控切面（内层，触发即提前出场/阻断）──
    @with_trade_cooldown(minutes=10)        # 空仓：成交后 10 分钟内不再入场
    @with_trailing_stop("15m")              # 有持仓：ATR 回撤止盈
    @with_atr_stop_take_profit("15m")       # 有持仓：ATR 止盈止损
    @with_stop_take_profit                  # 有持仓：固定比例止盈止损（最内层）
    class MyStrategy(Strategy[MyParams]):
        def on_bar(self, state, ctx):
            # 走到这里说明本 bar 无风控触发；只需写入场决策
            ...

## 出场优先级

多个出场切面叠加时，**声明顺序决定优先级**：运行时最外层（最靠上）的切面先检查，
先触发者短路。上例中有持仓时的检查顺序为
``trailing_stop -> atr_stop_take -> stop_take``。若希望固定比例止损最先生效，
应把 ``with_stop_take_profit`` 放到最上面。

## 行为细节

- 出场切面只在 ``state.position.direction`` 非空（有持仓）时检查，否则直接交后续逻辑。
- 依赖 ATR 的切面在指标缺失（``None``）或 ≤0 时静默跳过，不会误触发。
- 触发返回的 Signal 已带 ``volume``（等于当前持仓量）与 diagnostics；
  ``reason`` 的 JSON 格式化由框架层 ``_auto_finalize`` 统一完成，切面无需处理。
- 与方向切面不同，风控切面**直接产生交易决策**而非建议，使用者通常无需在
  on_bar 中读取它们的结果。
"""

from ._atr_stop_take import with_atr_stop_take_profit
from ._stop_take import with_stop_take_profit
from ._trade_cooldown import with_trade_cooldown
from ._trailing_stop import with_trailing_stop

__all__ = [
    "with_stop_take_profit",
    "with_atr_stop_take_profit",
    "with_trade_cooldown",
    "with_trailing_stop",
]
