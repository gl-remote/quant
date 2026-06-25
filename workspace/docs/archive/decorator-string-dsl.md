# 策略装饰器 DSL 字符串化设计（方向 + 风控）

> 类型：已实现设计记录
> 状态：已实现
> 完成日期：2026-06-26
> Git 参考：`4576cbe 阶段5: 完整测试迁移与验证`

***

## 背景与动机

当前建议型切面 DSL 使用 Python 对象表达式声明条件，以 `ma_strategy.py` 为例：

```python
# ── 做多方向切面（5 个）──
@confirm_long(at(MACD, "1m"), ">", 0)
@confirm_long(at(MACD, "5m"), ">", 0)
@confirm_long(at(KDJ, "1m"), "<", "kdj_oversold")
@confirm_long(at(KDJ, "5m"), "<", "kdj_oversold")
@trend_long(at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "5m"))

# ── 做空方向切面（5 个）──
@confirm_short(at(MACD, "1m"), "<", 0)
@confirm_short(at(MACD, "5m"), "<", 0)
@confirm_short(at(KDJ, "1m"), ">", "kdj_overbought")
@confirm_short(at(KDJ, "5m"), ">", "kdj_overbought")
@trend_short(at(SMA("{sma_short}"), "5m"), "<", at(SMA("{sma_long}"), "5m"))

# ── 风控切面（7 个）──
@entry_block_after_take_profit(CooldownNode(minutes=10))
@entry_block_after_stop_loss(CooldownNode(minutes=10))
@exit_for_take_profit(TrailingNode("15m"))
@exit_for_take_profit(AtrNode("15m"))
@exit_for_stop_loss(AtrNode("15m"))
@exit_for_take_profit(FixedRatioNode())
@exit_for_stop_loss(FixedRatioNode())
```

痛点：
1. **视觉噪音**：`at()`、`MetricRef`、`RiskNode` 等构造器使策略声明冗长。
2. **学习成本**：使用者需理解 `MetricRef`、`IndicatorSpec`、`RiskNode` 等内部类型。
3. **组合能力缺失**：不支持 `&&` / `||` 组合多个条件，只能通过堆叠装饰器实现隐式 AND（由 `__direction_keys__` 子集判断），无法表达 OR 或嵌套逻辑。
4. **与配置字段混用**：`"kdj_oversold"` 作为阈值时与数值 `0` 在参数类型上不一致，静态检查困难。

目标：将装饰器参数简化为**纯字符串表达式**，支持布尔组合，内部解析为现有 AST/谓词体系，**功能完全等价**。

***

## 目标语法

### 方向切面（字符串化后）

```python
# ── 做多方向切面（5 个）──
@confirm_long("macd@1m > 0")
@confirm_long("macd@5m > 0")
@confirm_long("kdj@1m < {kdj_oversold}")
@confirm_long("kdj@5m < {kdj_oversold}")
@trend_long("sma({sma_short})@5m > sma({sma_long})@5m")

# ── 做空方向切面（5 个）──
@confirm_short("macd@1m < 0")
@confirm_short("macd@5m < 0")
@confirm_short("kdj@1m > {kdj_overbought}")
@confirm_short("kdj@5m > {kdj_overbought}")
@trend_short("sma({sma_short})@5m < sma({sma_long})@5m")
```

组合条件（`&&` / `||`）：

```python
@confirm_long("macd@1m > 0 && macd@5m > 0")
@confirm_long("(kdj@1m < {kdj_oversold}) || (kdj@5m < {kdj_oversold})")
```

### 风控切面（字符串化后）

值分为两类：**指标引用**（需要 `@period` 指定 K 线周期）和**内置函数**（从持仓/bar/fills 实时计算）。

```python
# ── 入场阻断切面（2 个）──
@entry_block_after_take_profit("cooldown() < {cooldown_minutes} && count@{risk_data_period} < 2")
@entry_block_after_stop_loss("cooldown() < {cooldown_minutes} && count@{risk_data_period} < 2")

# ── 出场切面（5 个）──
@exit_for_take_profit("peak_profit() > {trailing_activation_atr} * atr@{risk_data_period} && drawdown_pct() > {trailing_drawdown_ratio}")
@exit_for_take_profit("profit_abs() > {atr_take_profit_multiplier} * atr@{risk_data_period}")
@exit_for_stop_loss("profit_abs() > {atr_stop_loss_multiplier} * atr@{risk_data_period}")
@exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
@exit_for_stop_loss("profit_pct() >= {stop_loss_ratio}")
```

每个表达式的行为与当前对应节点的 `evaluate` 完全一致（见第 5.3 节）。

`&&` 组合的典型用法：

| 组合 | 含义 | 对应节点 |
|------|------|---------|
| `cooldown() < N && count@{period} < 2` | 自然冷却期 + K 线柱数双重条件 | `CooldownNode(N)` + 无显式节点 |
| `peak_profit() > N * atr@15m && drawdown_pct() > M` | 激活 + 回撤触发 | `TrailingNode("15m")` |

风控节点的 `&&` 与方向切面的 `&&` 共用同一套解析器。

***

## 表达式语法规范（EBNF）

```ebnf
expr        := or_expr
or_expr     := and_expr ( ( "||" | "or" ) and_expr )*
and_expr    := compare ( ( "&&" | "and" ) compare )*
compare     := value ( ">" | "<" | ">=" | "<=" | "==" | "!=" ) value
value       := metric_ref | func_call | number | config_ref
metric_ref  := indicator ( "(" param_list ")" )? "@" period
indicator   := identifier | "count"
param_list  := param ( "," param )*
param       := number | "{" identifier "}" | identifier
config_ref  := "{" identifier "}"
func_call   := func_name "(" ")"
func_name   := "cooldown" | "profit_abs" | "profit_pct" | "peak_profit" | "drawdown_pct"
period      := identifier
number      := [0-9]+ ( "." [0-9]+ )?
identifier  := [a-zA-Z_][a-zA-Z0-9_]*
```

语义说明：
- `metric_ref`：指标引用，本质上是**绑定 K 线周期的函数调用**。`indicator(params)@period` 是完整形式，`(params)` 省略时等价于 `indicator()@period`（使用该指标的默认参数）。如 `atr@15m` 等价于 `atr()@15m`（ATR 使用默认参数）。`count` 是特殊指标（数柱数而非读列值），但语法与常规指标一致
- `func_call`：内置函数，无周期绑定，从当前持仓/bar/fills 实时计算。所有函数均为无参调用，`cooldown()` 返回已过分钟数、`profit_abs()` 返回绝对盈亏等。返回值通过常规比较运算符参与表达式（如 `cooldown() < {cooldown_minutes}`）
- `config_ref`：如 `{kdj_oversold}` — 从策略 `config` 读取字段值

***

## 设计原则

### `@period` 约定

`@` 后缀是"绑定 K 线周期"的标记。左侧是指标（可带参数），右侧是周期标识符（字面量或 `{config_ref}`）。

所有指标的完整语法为 `indicator(params)@period`，`(params)` 可省略（等价于 `indicator()@period`，使用默认参数）：

```
sma({sma_short})@5m  → 从 5m K 线的 sma({sma_short}) 列读数
macd@1m              → macd()@1m 的简写，从 1m K 线的 macd 列读数
atr@{period}         → atr()@{period} 的简写，从 config.period 指定周期的 ATR 列读数
count@{p}            → count()@{p} 的简写，从 config.p 指定周期的 K 线时间戳计数
```

不携带 `@period` 的值（内置函数、config 引用、数值）与周期无关。

### 表达式树求值时机

解析发生在**装饰器执行阶段**（类定义时），表达式树在**每个 bar 运行时**求值。`{config_ref}` 在求值时从 `state.strategy_config` 解析，而不是在解析时。

### 空安全

当某个值的数据不可用时，求值器**静默跳过**（返回 None，视为未触发），不会抛出异常。适用场景：

- 指标数据尚未就绪（如 ATR 在首个 lookback 窗口内）
- 持仓状态不存在时调用位置函数（如空仓时 `profit_abs()` — 但 exit 装饰器只在有持仓时调用，理论上不应发生）
- 缺失的 K 线数据源

### 阻断语义

`entry_block_*` 装饰器的表达式为 true → 阻断入场。这适用于所有可能的阻断条件，协作者新增条件时应遵循这一方向。

### 运算符优先级

`&&` 优先级高于 `||`（标准布尔代数），括号可用于分组：

```python
"a < 1 && b < 2 || c < 3"       # (a<1 && b<2) || c<3
"(a < 1 || b < 2) && c < 3"     # 括号改变分组
```

***

## 解析方案对比

### 方案 A：Pratt Parser（推荐）

手写自顶向下运算符优先级解析器（Pratt Parser），直接输出表达式树。核心思路：每个 token 关联 prefix 和 infix 解析函数，运算符优先级由 binding power 表声明式配置。

```
token 类型：NUMBER / IDENTIFIER / LPAREN / RPAREN / OP / AND / OR / AT
precedence 表：||(10) < &&(20) < > >= < <= == !=(30)
```

解析流程：
1. `tokenize()` → tokens（词法分析，~30 行）
2. 每个 token 注册 prefix_handler（字面量、括号分组）和 infix_handler（中缀运算符）
3. 递归下降时按 binding power 自动决定优先级和结合性
4. 输出 `BoolOp` / `Compare` / `MetricRef` / `FuncCall` 等节点

优点：
- 零第三方依赖，手写 ~80-100 行
- 天然支持运算符优先级、括号嵌套（由算法保证，无需手写层级）
- 无需占位符映射（`@` 和 `{}` 直接作为 token 处理）
- 错误信息原生干净，无间接层
- 扩展算术运算只需在 precedence 表加行 + 新增 infix handler

缺点：
- 需理解 Pratt 算法（团队知识成本一次性）
- 不适合语句级语法（但我们的 DSL 是纯表达式）

### 方案 B：Python `ast` 模块

将字符串预处理为合法 Python 表达式，用 `ast.parse(..., mode='eval')` 解析。

优点：
- 零第三方依赖
- 自动运算符优先级、括号嵌套

缺点：
- 需要占位符映射与还原（`@` 和 `{}` → 占位符 → 还原）
- 错误信息是 Python AST 层面的，需包装
- 预处理逻辑与 parser 逻辑耦合

### 方案 C：手写递归下降解析器

按 EBNF 手写分层 `Parser` 类（`or_expr → and_expr → compare → value`）。

优点：
- 完全控制语法和错误信息

缺点：
- 约 150~200 行，扩展新运算符需改多层函数
- 每层优先级需要一层函数嵌套

### 结论

推荐**方案 A（Pratt Parser）**：DSL 是纯表达式语法，Pratt 算法是它的"自然解法"——代码量最小（~100 行）、无占位符 hack、错误信息干净、扩展运算符只需加 precedence 表行。与方案 B（`ast` hack）相比，避免了预处理/还原的间接层；与方案 C（递归下降）相比，运算符优先级由 binding power 表声明式管理，无需手写层级嵌套。

***

## 风控与方向的统一

方向切面和风控切面共用同一套字符串表达式语法和求值器，不再保留独立的 `RiskNode` 协议。

### 条件类型映射

条件类型由解析器从表达式结构自动识别，8 个装饰器均通过同一个 `_evaluate` 求值器处理：

| 装饰器 | 表达式示例 | 求值行为 |
|--------|-----------|---------|
| `confirm_long` / `confirm_short` / `trend_long` / `trend_short` | `"macd@1m > 0"` | 读 `ctx.multi["1m"]` 的 macd 值，与 0 比较 |
| `exit_for_take_profit` | `"profit_abs() > N * atr@{period}"` | 有持仓时读 entry_price + close + ATR，判断盈利方向是否超过 N 倍 ATR |
| `exit_for_stop_loss` | `"profit_pct() >= {ratio}"` | 有持仓时读 entry_price + close，判断亏损方向是否超过比例 |
| `entry_block_after_take_profit` / `entry_block_after_stop_loss` | `"cooldown() < {minutes} && count@{period} < 2"` | 空仓时检查冷却期 + K 线柱数双重条件 |

### 求值上下文

求值器在运行时可以访问以下上下文数据，**所有数据对所有表达式可见**（空安全机制保障缺失数据时静默跳过）：

| 上下文 | 说明 | 有值时 |
|--------|------|--------|
| `ctx.multi[period].indicator(col)` | 指标读数 | 数据窗口就绪后 |
| `ctx.bar.close` / `.high` / `.low` | 当前 Bar 数据 | 始终有值 |
| `state.strategy_config` | 策略参数 | 始终有值 |
| `state.position.dir` / `.entry_price` / `.highest_price` | 持仓状态 | 有持仓时 |
| `state.fills[-1]` | 最近成交记录 | 有历史成交时 |

不区分"方向可用/风控可用"——表达式引用什么数据就访问什么数据，求值器不做人工拦截。

### 值类型

表达式中的值分为**指标引用**（`@period` 绑定 K 线周期）和**内置函数**（实时计算，无周期绑定）。

**指标引用（方向 + 风控通用）：**

`@period` 指明从哪条 K 线读取。常规指标读 `ctx.multi[period]` 的列值，`count` 是特殊指标（基于成交记录 + 时间戳计算柱数），但语法一致。

| 语法 | 来源 | 举例 |
|------|------|------|
| `{indicator}({params})@{period}` | `ctx.multi[period]` 指标列 | `"macd@1m"`、`"sma({sma_short})@5m"` |
| `atr@{period}` | `ctx.multi[period]` ATR 列 | `"atr@15m"` |
| `count@{period}` | `state.fills[-1]` + `ctx.multi[period]` 时间戳 | `"count@15m < 2"` |

**内置函数：**

无 `@period`，不绑定特定 K 线。所有函数均为无参调用，返回值通过常规比较运算符参与表达式。方向切面和风控切面均可使用（空仓时位置函数返回 None，由空安全机制静默跳过）。

| 函数 | 返回值 | 求值方式 | 对应节点 |
|------|--------|---------|---------|
| `profit_abs()` | 价格 | `abs(close - entry_price)` — 绝对盈亏 | `AtrNode(period)` |
| `profit_pct()` | 比例 | `abs(close - entry_price) / entry_price` — 盈亏比例 | `FixedRatioNode()` |
| `peak_profit()` | 价格 | `abs(peak_price - entry_price)` — 最大浮动收益 | `TrailingNode(period)` |
| `drawdown_pct()` | 比例 | `abs(peak_price - close) / peak_price` — 回撤比例 | `TrailingNode(period)` |
| `cooldown()` | 分钟数 | 自上次成交以来的自然时间 | `CooldownNode(N)` |

使用示例：
- `cooldown() < {cooldown_minutes}` — 冷却期未过，阻断入场
- `profit_abs() > {atr_take_profit_multiplier} * atr@{period}` — 盈利超过 N 倍 ATR

### 条件表达式的语义映射

出场条件的求值器会在比较前应用方向归一化——表达式中只表达"盈利方向的幅度"或"亏损方向的幅度"，direction 由外层的 role 分类器处理：

| 表达式 | `exit_for_take_profit` 行为（role="take_profit"） | `exit_for_stop_loss` 行为（role="stop_loss"） | 对应节点 |
|--------|-------------------------------------------------|----------------------------------------------|---------|
| `profit_pct() >= {take_profit_ratio}` | 盈利方向价格涨幅 ≥ 比例 → 止盈 | — | `FixedRatioNode()` |
| `profit_pct() >= {stop_loss_ratio}` | — | 亏损方向价格跌幅 ≥ 比例 → 止损 | `FixedRatioNode()` |
| `profit_abs() > {atr_take_profit_multiplier} * atr@{period}` | 盈利方向 abs 超过 N 倍 ATR → 止盈 | — | `AtrNode(period)` |
| `profit_abs() > {atr_stop_loss_multiplier} * atr@{period}` | — | 亏损方向 abs 超过 N 倍 ATR → 止损 | `AtrNode(period)` |
| `peak_profit() > {trailing_activation_atr} * atr@{period} && drawdown_pct() > {trailing_drawdown_ratio}` | 激活 + 回撤触发 → 止盈 | — | `TrailingNode(period)` |

这保持了当前 `_exit_aspect`（role）的设计——role 决定条件触发后写入 `take_profit.exit` 还是 `stop_loss.exit`，表达式中不需要显式区分多空。不同角色使用不同的 config 字段名（如 `{atr_take_profit_multiplier}` vs `{atr_stop_loss_multiplier}`），由解析器在运行时从 `state.strategy_config` 读取。

### cooldown 与 count 支持配置参数

```python
@entry_block_after_take_profit("cooldown() < {cooldown_minutes} && count@{risk_data_period} < 2")
```

`{cooldown_minutes}` 和 `{risk_data_period}` 均从 `state.strategy_config` 读取。

### 配置字段设计建议

```python
@dataclass
class MACrossParams:
    # ... 现有字段 ...

    cooldown_minutes: int = 10
    """止盈/止损后冷却期（分钟），默认 10"""

    risk_data_period: str = "15m"
    """风控指标数据源周期，默认 15m（用于 atr、trailing、count 节点）"""
```

统一后的风控写法：

```python
@entry_block_after_take_profit("cooldown() < {cooldown_minutes} && count@{risk_data_period} < 2")
@entry_block_after_stop_loss("cooldown() < {cooldown_minutes} && count@{risk_data_period} < 2")
@exit_for_take_profit("peak_profit() > {trailing_activation_atr} * atr@{risk_data_period} && drawdown_pct() > {trailing_drawdown_ratio}")
@exit_for_take_profit("profit_abs() > {atr_take_profit_multiplier} * atr@{risk_data_period}")
@exit_for_stop_loss("profit_abs() > {atr_stop_loss_multiplier} * atr@{risk_data_period}")
@exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
@exit_for_stop_loss("profit_pct() >= {stop_loss_ratio}")
```

***

## 实现方案

### 新增模块

```
strategies/strategy_aspects/
├── _parser.py          # 字符串表达式解析器（Pratt Parser 方案）
│   └── parse_expr(str) -> _Predicate | _CombinedPredicate
```

所有装饰器（方向 + 风控）共用同一个 `parse_expr`，解析器自动识别条件类型：
- 比较表达式：`macd@1m > 0` → `_ThresholdPredicate` 或 `_ComparePredicate`
- 风控内置值：`cooldown()`、`profit_pct() >= {ratio}` → 对应风控特有求值逻辑

### 表达式树节点

```python
class _CombinedPredicate:
    """布尔组合谓词：AND / OR — 方向与风控共用"""
    op: Literal["and", "or"]
    left: _Predicate | _CombinedPredicate
    right: _Predicate | _CombinedPredicate
```

求值器统一行为：
- `evaluate()` 递归求值左、右子树，按 `op` 组合
- `metrics` 收集全部子树的 `MetricRef`（包括 `count@` 等内置值）
- `default_name` 由子树名用 `_and_` / `_or_` 拼接（装饰器指定 `tag` 时完全覆盖该值）

### 装饰器签名改造

所有装饰器统一接收 `str` 表达式，内部委托 `parse_expr`：

```python
def confirm_long(expr: str, *, tag: str | None = None) -> Callable[[T], T]: ...
def confirm_short(expr: str, *, tag: str | None = None) -> Callable[[T], T]: ...
def trend_long(expr: str, *, tag: str | None = None) -> Callable[[T], T]: ...
def trend_short(expr: str, *, tag: str | None = None) -> Callable[[T], T]: ...

def exit_for_take_profit(expr: str) -> Callable[[T], T]: ...
def exit_for_stop_loss(expr: str) -> Callable[[T], T]: ...
def entry_block_after_take_profit(expr: str) -> Callable[[T], T]: ...
def entry_block_after_stop_loss(expr: str) -> Callable[[T], T]: ...
```

### 取消除 `RiskNode` 协议

`risk/_ast.py` 中的 `RiskNode` Protocol、`FixedRatioNode`、`AtrNode`、`TrailingNode`、`CooldownNode` 在实现阶段一并删除，全部逻辑收敛到 `_parser.py` + `direction/_core.py` 中的求值器。

***

## 已确定的语法细节

| # | 问题 | 决定 |
|---|------|------|
| 1 | 比较运算符全集 | `> < >= <= == !=`，全量实现 |
| 2 | 布尔运算符符号 | 同时支持 `&&`/`\|\|` 和 `and`/`or`（token 层面归一化） |
| 3 | 错误信息语言 | 中文（与项目日志语言统一） |

***

## 实施阶段（已实现）

| 阶段 | 内容 | 产出 | Commit |
|------|------|------|--------|
| 1 | 实现 `_parser.py`：Pratt Parser，支持 comparison + 布尔组合 + 算术运算 | 解析器通过全部边界 case | `fca1709` |
| 2 | 改造方向装饰器为 `confirm_long` / `confirm_short` / `trend_long` / `trend_short`，委托 `parse_expr` | 4 个装饰器支持 `str` 表达式 | `a5ff9cb` |
| 3 | 改造风控装饰器为 `exit_for_*` / `entry_block_after_*`，委托 `parse_expr`；删除 `RiskNode` 协议及 4 个节点类 | 4 个风控装饰器支持 `str` 表达式，`risk/_ast.py` 清理完成 | `6d86cb9` |
| 4 | `ma_strategy.py` 迁移为字符串语法 | 验证功能等价（对比回测结果） | `41be15c` |
| 5 | 测试验证 + 归档 | 165 测试全部通过，文档归档 | `4576cbe` |

***

## 参考

### 现有代码结构

```
strategies/strategy_aspects/
├── __init__.py          # 公共 API 导出（方向 8 个 + 风控 8 个装饰器 + 节点类 + 基类型）
├── _parser.py           # 字符串表达式解析器（Pratt Parser）— 新增
├── primitives.py        # 基础数据结构（MetricRef / DirectionReason / RiskReason / StrategyAspects 等）
│
├── direction/
│   ├── __init__.py      # 导出 4 个方向装饰器
│   └── _core.py         # _Predicate Protocol / _direction_aspect 工厂 / 4 个公开装饰器
│
├── risk/
│   ├── __init__.py      # 导出 4 个风控装饰器
│   └── _core.py         # _exit_aspect / _entry_block_aspect 工厂 + 4 个公开装饰器
│
└── indicators.py        # IndicatorSpec 工厂（MACD / KDJ / SMA / ATR）
```

### 方向侧关键类型

| 类型/函数 | 文件 | 用途 |
|----------|------|------|
| `MetricRef` | `primitives.py` | 指标引用：`period + IndicatorSpec`。构造方式 `at(indicator, period)` |
| `at(indicator, period)` | `primitives.py` | 构造 `MetricRef` 的便捷函数 |
| `IndicatorSpec` | `core/indicators.py` | 指标规格：`name + params + window + func` |
| `_Predicate` (Protocol) | `direction/_core.py` | 条件谓词协议：`metrics` 属性（注册数据需求）、`default_name` 属性（默认理由名）、`evaluate(ctx, config)` 方法（评估逻辑） |
| `_direction_aspect(role, direction, predicate, tag)` | `direction/_core.py` | 方向切面统一工厂。包装 `data_requirements`（自动注册指标）+ 包装 `on_bar`（评估谓词写入 `ctx.aspects.direction`）+ 注册 `__direction_keys__` |

### 风控侧关键类型

| 类型/函数 | 文件 | 用途 |
|----------|------|------|
| `_exit_aspect(role, reason_name, node)` | `risk/_core.py` | 出场切面工厂。有持仓时调用 `predicate.evaluate()`，触发则写入 `ctx.aspects.risk.{role}.exit` |
| `_entry_block_aspect(role, reason_name, node)` | `risk/_core.py` | 入场阻断切面工厂。空仓且 `state.fills` 非空时调用 `predicate.evaluate()`，触发则写入 `ctx.aspects.risk.{role}.entry_block` |

### `__direction_keys__` 机制

```python
# 类装饰器在方向切面评估前注册 reason name：
cls.__direction_keys__ = {
    "long": {"macd_1m", "sma5_vs_sma15", ...},
    "short": {"macd_1m", ...},
}
```

策略通过 `required` 参数选择需要的理由子集：

```python
@direction_aspect(required=["macd_1m", "sma5_vs_sma15"])
```

方向切面的消费语义是 AND / 子集校验：`required <= __direction_keys__[direction]`。字符串 DSL 的 `&&` 和 `||` 组合会产生复合 `default_name`（如 `"macd_1m_gt_0_and_kdj_1m_lt_oversold"`），装饰器可通过 `tag` 覆盖为简洁名称。使用 `tag` 后，策略的 `required` 列表只需引用 `tag` 值，无需关心内部组合结构。

### `data_requirements` 自动注册流程

1. 策略类定义时，装饰器读取 `predicate.metrics`（`_Predicate`）或调用 `node.data_requirements_builder()`（`RiskNode`）
2. 包装 `cls.data_requirements`：在原始 `data_requirements` 返回结果上，merge 自动生成的 `DataRequirements`（含指标列 + lookback_bars）
3. 每个 bar 运行时，框架调用 `cls.data_requirements(config)` 决定加载哪些数据

### 后续

- [risk-aspects-advisory-refactor.md](file:///Users/gaolei/Documents/src/quant/workspace/docs/archive/risk-aspects-advisory-refactor.md) — 风控切面建议化重构（已完成）
