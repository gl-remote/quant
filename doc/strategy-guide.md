# 策略开发指南

> 版本: 0.2.0 | 更新日期: 2026-05-24

---

## 一、架构概览

本项目的策略系统采用 **核心-桥接器 (Core-Bridge)** 模式：

```
      MaStrategyCore              ← 纯业务逻辑，零框架依赖
       /        \
VnpyStrategyBridge  TqsdkStrategyBridge   ← 框架适配 + 数据转换
   (vn.py 回测)       (天勤 实盘/模拟)
```

**核心原则**：策略只做交易决策，桥接器只做翻译。回测和实盘共用同一个策略实例，确保行为一致。

---

## 二、如何新增一个策略

### 2.1 最小实现示例

```python
# strategies/core/my_strategy.py

from dataclasses import dataclass
from typing import List, Optional
from .core.base import Strategy
from .core.types import Bar, Signal, Fill, StrategyPosition, Performance


@dataclass
class MyConfig:
    """策略配置 — 全部可调参数"""
    param_a: int = 10
    param_b: float = 0.5


class MyStrategy(Strategy):
    """自定义策略核心"""

    name: str = "my_strategy"

    def __init__(self, config: Optional[MyConfig] = None):
        self._config = config or MyConfig()
        self._position = StrategyPosition()
        self._fills: List[Fill] = []

    # ---- Strategy 接口 ----

    @property
    def config(self) -> MyConfig:
        return self._config

    @config.setter
    def config(self, value: MyConfig):
        self._config = value

    @property
    def position(self) -> StrategyPosition:
        return self._position

    @property
    def performance(self) -> Performance:
        # 实现绩效计算
        return self._calc_performance()

    @property
    def fills(self) -> List[Fill]:
        return list(self._fills)

    def reset(self) -> None:
        self._position = StrategyPosition()
        self._fills.clear()

    def on_bar(self, bar: Bar) -> Signal:
        # 实现核心信号逻辑
        signal = Signal()
        # ... 计算 ...
        return signal

    def on_fill(self, fill: Fill) -> None:
        if fill.action == 'buy':
            self._position = StrategyPosition(
                direction='long',
                entry_price=fill.price,
                volume=fill.volume,
            )
        elif fill.action == 'sell':
            self._position = StrategyPosition()
        self._fills.append(fill)
```

### 2.2 必须实现的方法

| 方法 | 说明 |
|------|------|
| `on_bar(bar: Bar) -> Signal` | 策略决策中枢，接收 K 线，返回交易信号 |
| `on_fill(fill: Fill) -> None` | 成交回调，更新持仓和交易记录 |
| `performance` | 累计绩效，一般在卖出时计算 |
| `position` | 当前持仓状态 |
| `config` | 策略配置读写 |
| `reset()` | 状态重置，用于新一轮回测 |

### 2.3 Signal 字段说明

```python
@dataclass
class Signal:
    action: str = ""       # 'buy' / 'sell' / '' (空字符串表示不交易)
    reason: str = ""       # 信号原因，如 'golden_cross' / 'stop_loss'
    volume: int = 0        # 预计算手数（买入时必填）
```

- `action=''` 表示本根 K 线不产生任何交易信号
- `reason` 用于回测报告和调试，建议用英文常量
- `volume` 由策略在信号生成时预计算，Bridge 直接使用

---

## 三、注册到回测引擎

### 3.1 编程方式

构造 `TradingContext`，将策略实例直接注入回测引擎：

```python
from strategies.core.context import TradingContext
from strategies.core.my_strategy import MyStrategy, MyConfig
from backtest import VnpyBacktestEngine

context = TradingContext(strategy=MyStrategy(MyConfig(param_a=15)))
engine = VnpyBacktestEngine(config, context=context)
result = engine.run_full_pipeline(symbol='DCE.m2509')
```

适合脚本或 Notebook 中手动调用。

### 3.2 CLI 动态加载

在 `main.py` 中 `load_strategy()` 已支持按名称加载：

```bash
python main.py backtest --symbol DCE.m2509 --strategy my_strategy
```

策略名会自动映射到 `strategies/ma_strategy.py` 中的类。如需加载自定义策略文件，修改 `load_strategy()` 的 `name` 映射逻辑。

---

## 四、策略开发流程

```
1. 编写策略核心 → 2. 离线测试 → 3. 回测验证 → 4. Walk-Forward → 5. 参数优化
```

### 4.1 离线测试

```bash
python main.py test --strategy ma
```

跑预设的模拟场景，验证信号逻辑是否正确。

### 4.2 单品种回测

```bash
python main.py backtest --symbol DCE.m2509
```

查看控制台输出的 statistics、comparison 和过拟合评分。

### 4.3 Walk-Forward 验证

```bash
python main.py backtest --symbol DCE.m2509 --walk-forward
```

滚动窗口验证，检测 IS-OOS（样本内/样本外）一致性。过拟合评分 < 15 为优秀。

### 4.4 批量品种测试

```bash
python main.py backtest --pattern "DCE\..*" --parallel 4
```

跨品种验证策略普适性，生成合并对比报告。

---

## 五、止损/止盈与信号优先级

### 5.1 信号优先级规则

持仓状态下，多个信号可能同时触发。**代码中 `if/elif` 的顺序决定实际优先级**：

```
止损 (stop_loss) > 止盈 (take_profit) > 死叉 (death_cross)
```

即：即使同时满足止损和止盈条件，也只执行止损。

空仓状态下仅检测金叉买入信号。

### 5.2 自定义优先级

如果你开发的策略有多个出场条件，请明确文档化优先级，并在代码中使用清晰的 `if/elif/else` 结构：

```python
def on_bar(self, bar: Bar) -> Signal:
    if self._has_position:
        # 优先级 1: 止损 (最高)
        if self._check_stop_loss(bar.close):
            return Signal(action='sell', reason='stop_loss', volume=self._pos.volume)
        # 优先级 2: 止盈
        elif self._check_take_profit(bar.close):
            return Signal(action='sell', reason='take_profit', volume=self._pos.volume)
        # 优先级 3: 趋势反转
        elif self._check_trend_reverse():
            return Signal(action='sell', reason='trend_reverse', volume=self._pos.volume)
    else:
        if self._check_entry():
            vol = self._calc_size(bar.close)
            return Signal(action='buy', reason='entry_signal', volume=vol)
    return Signal()
```

---

## 六、参数调优

### 6.1 可调参数清单

以均线策略为例：

| 参数 | 含义 | 建议范围 | 默认值 |
|------|------|---------|--------|
| `sma_short` | 短均线周期 | 3-15 | 5 |
| `sma_long` | 长均线周期 | 10-60 | 20 |
| `stop_loss_ratio` | 止损比例 | 0.01-0.05 | 0.03 |
| `take_profit_ratio` | 止盈比例 | 0.03-0.10 | 0.05 |
| `position_ratio` | 仓位比例 | 0.05-0.30 | 0.10 |

### 6.2 调参原则

1. **先粗后细**：先大步长搜索大致区域，再小步长精调
2. **单变量变化**：一次只改一个参数，观察效果
3. **跨品种验证**：参数在一个品种上好不代表普适
4. **关注 IS-OOS**：训练集好、测试集差 = 过拟合
5. **不要追逐最高分**：稍微宽松的参数通常更稳健

### 6.3 网格搜索（计划中）

S1 阶段将提供内置的参数优化器：

```python
from optimizer import GridSearch

search = GridSearch(engine, param_grid={
    'sma_short': [3, 5, 7, 10],
    'sma_long': [15, 20, 30, 40],
})
results = search.run(symbol='DCE.m2509')
print(results.best_params)
```

---

## 七、常见问题

### 策略信号不触发？

- 检查 `close_history` 是否积累足够数据（至少 `sma_long` 根 K 线）
- 检查 `on_fill` 是否正确更新了 `_position`

### 回测收益为 0？

- 确认手续费和滑点参数是否正确
- 检查 `_calc_performance` 是否正确匹配买卖对

### Walk-Forward 过拟合评分高？

- 缩短训练窗口，增加测试期
- 减少参数数量
- 增加止损/止盈等风控约束

---

## 八、参考实现

完整可运行示例：

- [MaStrategyCore](../strategies/ma_strategy.py) — 均线交叉策略（约 200 行）
- [Strategy ABC](../strategies/core/base.py) — 策略基类接口定义
- [VnpyStrategyBridge](../strategies/bridges/vnpy_bridge.py) — vn.py 桥接器（约 120 行）
- [TqsdkStrategyBridge](../strategies/bridges/tqsdk_bridge.py) — 天勤桥接器（约 220 行）
