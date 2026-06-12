"""策略 AOP 装饰器 — 将横切关注点从策略业务逻辑中抽离

设计原则:
  - 每个装饰器只关注一个横切面（止损止盈、日志、风控等）
  - 装饰器在运行时通过 state / ctx 读取配置，不在定义时捕获
  - 与参数搜索 100% 兼容
  - 采用类装饰器模式，便于切面同时干预 on_bar / data_requirements 等多个方法

使用方式:
    from strategies.core.decorators import with_stop_take_profit

    @with_stop_take_profit
    class MyStrategy(Strategy[MyParams]):
        def on_bar(self, state, ctx):
            # 只写入场逻辑，横切面由装饰器自动处理
            ...
"""

from ._atr_stop_take import with_atr_stop_take_profit
from ._stop_take import with_stop_take_profit
from ._trailing_stop import with_trailing_stop

__all__ = [
    "with_stop_take_profit",
    "with_atr_stop_take_profit",
    "with_trailing_stop",
]
