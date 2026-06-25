# 风控切面建议化重构（risk aspects → advisory）

> 类型：Design / 已实现设计记录
> 状态：已实现
> 完成日期：2026-06-25
> 关联代码：[strategy_aspects/risk](file:///Users/gaolei/Documents/src/quant/workspace/strategies/strategy_aspects/risk)、[strategy_aspects/direction](file:///Users/gaolei/Documents/src/quant/workspace/strategies/strategy_aspects/direction)、[primitives.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/strategy_aspects/primitives.py)
> 关联缺陷：DEF-S05（信号优先级由 if/elif 顺序隐式定义）

---

## 0. 交接摘要

- 当前 `risk` 模块是**拦截型切面**：条件满足时直接 `return Signal`，短路策略原始 `on_bar`。
- 出场优先级由**装饰器声明顺序隐式决定**，策略无法干预、组合或复用出场信息——这是本次重构的核心动机（策略灵活度）。
- 目标：把风控切面改造为**建议型**（信息填充），统一到 `ctx.aspects` 模型，**决策权交还策略**，与 `direction` DSL 的哲学对齐。
- 消费语义与 `direction` 不同：`direction` 是 AND/子集（`required <= keys`），risk 是**策略完全自治**（框架不内置聚合语义）。

---

## 1. 背景与动机

### 1.1 现状（重构前）

`risk` 模块四个切面：

| 切面 | 行为 | 触发 |
|------|------|------|
| `with_stop_take_profit` | 直接返回平仓 Signal | 有持仓 |
| `with_atr_stop_take_profit` | 直接返回平仓 Signal | 有持仓 |
| `with_trailing_stop` | 直接返回平仓 Signal | 有持仓 |
| `with_trade_cooldown` | 直接返回空 Signal 阻断入场 | 空仓 |

它们各自包装 `on_bar`，满足条件即短路返回，链式叠加时**最外层（声明最靠上）先触发者胜出**。

### 1.2 痛点

1. **优先级隐式**：出场优先级 = 装饰器堆叠顺序，不在策略可见处（DEF-S05）。调整优先级要改装饰器顺序，易错且不直观。
2. **策略无干预能力**：策略拿不到「本 bar 有哪些出场理由触发」，无法做组合决策。例如：
   - 「ATR 止损触发，但方向建议依然强烈 → 想用更宽的止损容忍一次」；
   - 「止盈与移动止盈同时满足 → 想按自定义规则择一」；
   - 「想把出场理由纳入策略级统计/过滤」。
3. **信息不可复用**：出场理由只体现在最终 Signal 的 reason 里，无法像方向理由那样进入 `ctx.aspects` 供策略与诊断统一消费。
4. **模型割裂**：`direction` 已是「填信息 → 策略决策」，`risk` 还是「切面直接决策」，两套心智模型。

### 1.3 重构收益

策略在 `on_bar` 里同时看到方向建议与风控建议，**对入场/出场冲突、出场优先级拥有完全控制权**，而不再被装饰器顺序隐式绑定。

---

## 2. 设计原则（与 direction 的异同）

| 维度 | direction（参照） | risk（本设计） |
|------|------------------|----------------|
| 切面产物 | 方向理由写入 `ctx.aspects.direction` | 风控理由写入 `ctx.aspects.risk` |
| 决策归属 | 策略 | 策略 |
| 消费语义 | AND / 子集（`required <= keys`） | **策略完全自治** |
| reason 载荷 | `name + detail`（诊断用） | `name + detail`（诊断用） |
| 抽象形态 | 单工厂 × 正交三轴（8 全满） | **AST 节点 + 统一工厂** |
| 安全级别 | 策略全责 | 策略全责 |

**关键简化**：reason 载荷不引入 `severity`、`action`、`volume` 等决策权重字段——切面只提供**纯信息**，消费语义（包括优先级、聚合规则）**完全由策略自定义**。

---

## 3. 目标数据结构

挂载到现有 [StrategyAspects](file:///Users/gaolei/Documents/src/quant/workspace/strategies/strategy_aspects/primitives.py)，新增 `risk`（与 `direction` 平级），采用**多层分桶结构**与 `direction` 对齐。

```python
@dataclass(frozen=True)
class RiskReason:
    """风控理由 — 由 risk 切面内部生成，使用者不直接构造"""

    name: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskActionBucket:
    """某个盈亏方向上的风险建议，按动作分桶"""

    exit: list[RiskReason] = field(default_factory=list)
    entry_block: list[RiskReason] = field(default_factory=list)

    @property
    def reasons(self) -> list[RiskReason]:
        return [*self.exit, *self.entry_block]


@dataclass
class RiskAdvice:
    """风控建议 — 包含止盈和止损两个方向的动作桶"""

    take_profit: RiskActionBucket = field(default_factory=RiskActionBucket)
    stop_loss: RiskActionBucket = field(default_factory=RiskActionBucket)

    @property
    def all_reasons(self) -> list[RiskReason]:
        return [*self.take_profit.reasons, *self.stop_loss.reasons]


@dataclass
class StrategyAspects:
    direction: DirectionAdvice = field(default_factory=DirectionAdvice)
    risk: RiskAdvice = field(default_factory=RiskAdvice)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def flush_risk_diagnostics(self) -> None:
        """将风控建议展平写入 diagnostics，供策略一次性调用。"""
        self.diagnostics["risk_exit_take_profit"] = [
            r.name for r in self.risk.take_profit.exit
        ]
        self.diagnostics["risk_exit_stop_loss"] = [
            r.name for r in self.risk.stop_loss.exit
        ]
        self.diagnostics["risk_entry_block_take_profit"] = [
            r.name for r in self.risk.take_profit.entry_block
        ]
        self.diagnostics["risk_entry_block_stop_loss"] = [
            r.name for r in self.risk.stop_loss.entry_block
        ]
        self.diagnostics["risk_detail"] = {
            r.name: r.detail for r in self.risk.all_reasons
        }
```

---

## 4. 消费侧设计

**框架不内置优先级、不自动聚合、不短路**。策略在 `on_bar` 中自行消费：

```python
def on_bar(self, state, ctx):
    # 示例：有持仓时任意风控 exit 理由触发即出场
    exit_reasons = (
        ctx.aspects.risk.take_profit.exit
        + ctx.aspects.risk.stop_loss.exit
    )
    if state.position.direction and exit_reasons:
        risk = exit_reasons[0]
        action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
        return Signal(action=action, reason=risk.name, volume=state.position.volume)

    # 示例：空仓时若存在 entry_block 则阻断入场
    if not state.position.direction:
        has_block = ctx.aspects.risk.all_reasons
        if has_block:
            return Signal()
        # ... 正常入场逻辑
```

建议策略在返回前调用 `ctx.aspects.flush_diagnostics()`，将 risk 信息展平到 diagnostics 便于复盘。

---

## 5. AST 节点设计

### 5.1 设计意图

把风控条件从「7 个独立切面文件」收敛为「**4 个 AST 节点 + 1 个统一工厂**」，实现：
- **触发逻辑内聚**：同一类条件（固定比例、ATR、回撤、时间）的逻辑集中在一处
- **切面工厂统一**：`_core.py` 只负责「有持仓/空仓检查 → 调用节点 evaluate → 写入对应桶」
- **未来 DSL 兼容**：新增 `role` 参数由装饰器工厂传入，节点本身不硬编码止盈/止损归属

### 5.2 节点一览

```python
class RiskNode(Protocol):
    def evaluate(
        self, state, ctx, direction=None, role=None
    ) -> tuple[bool, detail] | None: ...

    def data_requirements_builder(self) -> Callable | None:
        return None
```

| 节点 | 参数 | evaluate 行为 | data_requirements |
|------|------|--------------|-------------------|
| `FixedRatioNode(ratio=None)` | 自定义比例或读 config | 比较 `close` vs `entry_price * (1 ± ratio)` | 无 |
| `AtrNode(period="15m")` | 指标周期 | 从 `ctx.multi[period]` 读 ATR，比较 `entry_price ± atr * multiplier` | 自动注册 ATR |
| `TrailingNode(period="15m")` | 指标周期 | 先判断激活阈值（`atr * activation`），再判断回撤比例 | 自动注册 ATR |
| `CooldownNode(minutes)` | 冷却分钟数 | 读 `state.fills[-1]` 时间，比较是否超期 | 无 |

### 5.3 使用界面

```python
from strategies.strategy_aspects import (
    exit_take_profit, exit_stop_loss,
    entry_block_take_profit, entry_block_stop_loss,
    FixedRatioNode, AtrNode, TrailingNode, CooldownNode,
)

@entry_block_take_profit(CooldownNode(minutes=10))
@entry_block_stop_loss(CooldownNode(minutes=10))
@exit_take_profit(TrailingNode("15m"))
@exit_take_profit(AtrNode("15m"))
@exit_stop_loss(AtrNode("15m"))
@exit_take_profit(FixedRatioNode())
@exit_stop_loss(FixedRatioNode())
class MyStrategy(Strategy[MyParams]):
    ...
```

**关键设计**：`role`（`"take_profit"` / `"stop_loss"`）由装饰器工厂 `_exit_aspect` / `_entry_block_aspect` 在调用 `evaluate(..., role=role)` 时传入，节点据此读取 config 中对应字段（`take_profit_ratio` vs `stop_loss_ratio` 等）。节点构造函数**不显式接收 role**，避免 `@exit_take_profit(FixedRatioNode("take_profit"))` 这类冗余。

---

## 6. 切面产物明细

| 切面 | 触发条件 | `RiskReason.name` | `detail` 字段 |
|------|----------|-------------------|---------------|
| `exit_take_profit(FixedRatioNode())` | 有持仓，固定比例止盈触发 | `SIGNAL_TAKE_PROFIT` | `type="fixed_ratio"`, `direction`, `entry_price`, `current_close`, `take_profit_ratio`, `highest_price`, `lowest_price` |
| `exit_stop_loss(FixedRatioNode())` | 有持仓，固定比例止损触发 | `SIGNAL_STOP_LOSS` | `type="fixed_ratio"`, `direction`, `entry_price`, `current_close`, `stop_loss_ratio`, `highest_price`, `lowest_price` |
| `exit_take_profit(AtrNode("15m"))` | 有持仓，ATR 倍数止盈触发 | `SIGNAL_TAKE_PROFIT` | `type="atr"`, `direction`, `entry_price`, `current_close`, `atr_value`, `atr_take_profit_multiplier` |
| `exit_stop_loss(AtrNode("15m"))` | 有持仓，ATR 倍数止损触发 | `SIGNAL_STOP_LOSS` | `type="atr"`, `direction`, `entry_price`, `current_close`, `atr_value`, `atr_stop_loss_multiplier` |
| `exit_take_profit(TrailingNode("15m"))` | 有持仓，回撤止盈激活且触发 | `SIGNAL_TAKE_PROFIT` | `type="trailing_stop"`, `direction`, `entry_price`, `current_close`, `peak_price`, `atr_value`, `trailing_activation_atr`, `trailing_drawdown_ratio` |
| `entry_block_take_profit(CooldownNode(minutes=10))` | 空仓，止盈成交后冷却期未结束 | `SIGNAL_TRADE_COOLDOWN` | `cooldown_minutes`, `elapsed_seconds`, `remaining_seconds` |
| `entry_block_stop_loss(CooldownNode(minutes=10))` | 空仓，止损成交后冷却期未结束 | `SIGNAL_TRADE_COOLDOWN` | `cooldown_minutes`, `elapsed_seconds`, `remaining_seconds` |

---

## 7. 实施记录

所有阶段已完成，独立验证通过（`uv run pytest tests/strategies/strategy_aspects/ --tb=short` + `ruff check`）。

### 阶段 0：基础数据结构

- `primitives.py` 新增 `RiskReason`、`RiskActionBucket`、`RiskAdvice`
- `StrategyAspects` 新增 `risk: RiskAdvice` 字段（取代早期设计的 `list[RiskReason]`）
- `StrategyAspects` 新增 `flush_risk_diagnostics()` 方法

### 阶段 1：四个 risk 切面改造为建议型

- `_stop_take.py` → `_take_profit.py` + `_stop_loss.py`：触发时写入 `risk.take_profit.exit` / `risk.stop_loss.exit`
- `_atr_stop_take.py` → `_take_profit_atr.py` + `_stop_loss_atr.py`：同上
- `_trailing_stop.py` → `_trailing_take_profit.py`：写入 `risk.take_profit.exit`
- `_trade_cooldown.py` → `_cooldown_after_take_profit.py` + `_cooldown_after_stop_loss.py`：写入 `entry_block`

### 阶段 2：ma_strategy 接管 risk 决策

- `on_bar` 新增出场逻辑：有持仓 + `ctx.aspects.risk` exit 非空 → 构造平仓 Signal
- `on_bar` 新增入场阻断：空仓 + `ctx.aspects.risk` 含 entry_block → 不入场
- 注释与文档字符串同步更新

### 阶段 3：命名风格对齐 direction

- 切面函数重命名为 `[exit/entry_block]_[take_profit/stop_loss]_[when/atr/trailing/cooldown]` 风格
- `RiskReason` 新增 `role` 字段（与 `DirectionReason` 对齐）
- `flush_diagnostics` 统一用 `r.key` / `r.name`

### 阶段 4：AST 节点重构

- 新建 `_ast.py`：定义 `RiskNode` Protocol + 4 个 AST 节点（`FixedRatioNode` / `AtrNode` / `TrailingNode` / `CooldownNode`）
- 重写 `_core.py`：4 个公共切面函数（`exit_take_profit` / `exit_stop_loss` / `entry_block_take_profit` / `entry_block_stop_loss`）+ 统一工厂 `_exit_aspect` / `_entry_block_aspect`
- 删除 7 个旧切面文件
- `role` 参数从节点构造函数移除，改由装饰器工厂在 `evaluate(..., role=role)` 时传入

---

## 8. 未来扩展

### 8.1 DSL 语法糖层（待设计）

当前 AST 节点已实现「统一求值器签名」和「条件逻辑内聚」，未来若需引入通用表达式 DSL，可在 `_ast.py` 基座上扩展：

```python
# 目标使用界面（概念验证）
@exit_take_profit(
    BarRef("close") > PosRef("entry_price") * (1 + ConstRef("take_profit_ratio"))
)
```

所需新增组件：
- `ValueRef` 基类：`BarRef`、`PosRef`、`IndicatorRef`、`ConstRef`
- `Expr` 类：`add`、`multiply` 等算术运算
- `Predicate` 类：`gt`、`lt` 等比较运算
- `to_trigger_fn()`：将表达式树编译成 `(state, ctx, direction, role) -> (bool, detail) | None`

### 8.2 与 `at()` 的统一

当前 `at(MACD, "1m")` 在 direction 中作为 `MetricRef` 使用，risk 的 `AtrNode` / `TrailingNode` 目前直接接收 `period: str`。未来若要让 `at()` 成为全系统统一的指标引用入口，可让 `AtrNode` 接收 `MetricRef`：

```python
# 当前
@exit_take_profit(AtrNode("15m"))

# 未来
@exit_take_profit(AtrNode(at(ATR(14), "15m")))
```

此改动需要：
1. `indicators.py` 新增 `ATR` 工厂
2. `AtrNode` / `TrailingNode` 构造函数改为接收 `MetricRef`
3. `evaluate` 和 `data_requirements_builder` 均从 `MetricRef` 提取信息

### 8.3 新增风控节点

基于现有 `RiskNode` Protocol，可轻松新增节点类型而不改 `_core.py`：
- `MaxDrawdownNode(max_pct)`：净值回撤节点
- `TimeStopNode(max_bars)`：最大持仓时间节点
- `VolumeSpikeNode(period, threshold)`：成交量异常节点

---

## 9. 文件清单

```
strategies/strategy_aspects/risk/
├── __init__.py          # 公共 API 导出
├── _core.py             # 统一工厂 + 公共切面函数
└── _ast.py              # AST 节点定义（求值器 + data_requirements_builder）

# 已删除（阶段 4）
# ├── _cooldown_after_stop_loss.py
# ├── _cooldown_after_take_profit.py
# ├── _stop_loss.py
# ├── _stop_loss_atr.py
# ├── _take_profit.py
# ├── _take_profit_atr.py
# └── _trailing_take_profit.py
```
