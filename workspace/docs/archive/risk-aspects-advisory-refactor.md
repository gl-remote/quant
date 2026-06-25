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
| 抽象形态 | 单工厂 × 正交三轴（8 全满） | 四个独立切面，无统一轴模型 |
| 安全级别 | 策略全责 | 策略全责 |

**关键简化**：reason 载荷不引入 `severity`、`action`、`volume` 等决策权重字段——切面只提供**纯信息**，消费语义（包括优先级、聚合规则）**完全由策略自定义**。

---

## 3. 目标数据结构

挂载到现有 [StrategyAspects](file:///Users/gaolei/Documents/src/quant/workspace/strategies/strategy_aspects/primitives.py#L53-L80)，新增 `risk`（与 `direction` 平级）。

```python
@dataclass(frozen=True)
class RiskReason:
    """风控理由 — 由 risk 切面内部生成，使用者不直接构造"""

    name: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyAspects:
    direction: DirectionAdvice = field(default_factory=DirectionAdvice)
    risk: list[RiskReason] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def flush_risk_diagnostics(self) -> None:
        """将风控建议展平写入 diagnostics，供策略一次性调用。"""
        self.diagnostics["risk_reasons"] = [r.name for r in self.risk]
        self.diagnostics["risk_detail"] = {r.name: r.detail for r in self.risk}
```

---

## 4. 消费侧设计

**框架不内置优先级、不自动聚合、不短路**。策略在 `on_bar` 中自行消费：

```python
def on_bar(self, state, ctx):
    # 示例：有持仓时任意风控理由触发即出场
    if state.position.direction and ctx.aspects.risk:
        risk = ctx.aspects.risk[0]
        action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
        return Signal(action=action, reason=risk.name, volume=state.position.volume)

    # 示例：空仓时若存在 cooldown 则阻断入场
    if not state.position.direction:
        has_cooldown = any(r.name == SIGNAL_TRADE_COOLDOWN for r in ctx.aspects.risk)
        if has_cooldown:
            return Signal()
        # ... 正常入场逻辑
```

建议策略在返回前调用 `ctx.aspects.flush_risk_diagnostics()`，将 risk 信息展平到 diagnostics 便于复盘。

---

## 5. 切面产物明细

| 切面 | 触发条件 | `RiskReason.name` | `detail` 字段 |
|------|----------|-------------------|---------------|
| `with_stop_take_profit` | 有持仓，固定比例止盈/止损触发 | `SIGNAL_TAKE_PROFIT` / `SIGNAL_STOP_LOSS` | `type="fixed_ratio"`, `direction`, `entry_price`, `current_close`, `take_profit_ratio` / `stop_loss_ratio`, `highest_price`, `lowest_price` |
| `with_atr_stop_take_profit` | 有持仓，ATR 倍数止盈/止损触发 | `SIGNAL_TAKE_PROFIT` / `SIGNAL_STOP_LOSS` | `type="atr"`, `direction`, `entry_price`, `current_close`, `atr_value`, `atr_take_profit_multiplier` / `atr_stop_loss_multiplier` |
| `with_trailing_stop` | 有持仓，回撤止盈激活且触发 | `SIGNAL_TAKE_PROFIT` | `type="trailing_stop"`, `direction`, `entry_price`, `current_close`, `peak_price`, `atr_value`, `trailing_activation_atr`, `trailing_drawdown_ratio` |
| `with_trade_cooldown` | 空仓，成交后冷却期未结束 | `SIGNAL_TRADE_COOLDOWN` | `cooldown_minutes`, `elapsed_seconds`, `remaining_seconds` |

---

## 6. 实施记录

所有阶段已完成，独立验证通过（`uv run pytest workspace/tests/strategies/strategy_aspects/risk/ workspace/tests/strategies/test_ma_strategy.py --tb=short` + `ruff check`）。

### 阶段 0：基础数据结构

- `primitives.py` 新增 `RiskReason` dataclass
- `StrategyAspects` 新增 `risk: list[RiskReason]` 字段
- `StrategyAspects` 新增 `flush_risk_diagnostics()` 方法

### 阶段 1：四个 risk 切面改造为建议型

- `_stop_take.py`：触发时 `ctx.aspects.risk.append(RiskReason(...))`，不再 `return Signal`
- `_atr_stop_take.py`：同上
- `_trailing_stop.py`：同上
- `_trade_cooldown.py`：同上

### 阶段 2：ma_strategy 接管 risk 决策

- `on_bar` 新增出场逻辑：有持仓 + `ctx.aspects.risk` 非空 → 取第一个 risk reason 构造平仓 Signal
- `on_bar` 新增入场阻断：空仓 + `ctx.aspects.risk` 含 cooldown → 不入场
- 注释与文档字符串同步更新

### 阶段 3：测试更新

- `test_stop_take.py` / `test_atr_stop_take.py` / `test_trade_cooldown.py`：断言从 `signal.action == ...` 改为 `ctx.aspects.risk[0].name == ...`
- `test_ma_strategy.py`：出场/入场用例保持通过（因策略消费逻辑与旧拦截型行为等价）
