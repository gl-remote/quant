---
name: "quant-math-spec"
description: "Rules for writing and reviewing the strategy math spec document (strategy-math-spec.md). Invoke when creating, editing, or consistency-checking a strategy math spec."
---

# Quant Math Spec

本 skill 只覆盖**策略数学规格文档本身**——即主题目录内的 `strategy-math-spec.md`：如何写、用什么记号、如何做静态一致性检查。

主题目录布局、其他辅助文档（research-status / experiment-plan / parameter-selection-spec / implementation-notes / README）以及跨文档流程，由 `quant-research-layout` 负责，本 skill 不重复。

## 触发时机

- 创建一个新的 `strategy-math-spec.md`；
- 修改现有 `strategy-math-spec.md`；
- 对 `strategy-math-spec.md` 做静态一致性检查；
- 因为规格缺失需要回补，然后再继续实现或实验；
- 需要判断某段内容是否属于策略数学规格（若不属于则应交由 `quant-research-layout` 处理）。

## 核心原则

- `strategy-math-spec.md` 是**策略行为的唯一契约**。实现代码必须以规格为准；发现规格缺失时先回补规格再写代码。
- 单独阅读该文档即可复现策略，不依赖代码实现、聊天上下文或历史实验记忆。
- 变量定义遵循"必要且充分"原则：影响策略语义、执行结果或可能产生歧义的变量必须定义。
- 一眼可辨认、能轻易达成共识的常规字段不必逐项解释（例如 `O_t/H_t/L_t/C_t/V_t` 可整体说明为 OHLCV bar）。
- session、bar 索引、tick、profile、状态变量、策略参数、派生参数、tie-break 规则必须显式定义。
- 所有候选分支必须列成有限集合（例如 `poc_mode ∈ {close, range}`）。
- 所有 tie-break 规则必须显式写出，不能隐藏在 `argmax` 或代码实现里。
- 入场、出场、止损、止盈、仓位、冷却、每日交易次数、状态重置必须以数学 / 伪数学规则固定。
- 数学表达的目标是精确、简要、可实现；不为显然概念写冗长解释。
- 只固定策略定义与候选集合；实验结果、调参过程、临时观察写在 workbench 或归档中。

## strategy-math-spec.md 的推荐结构

按下列骨架组织；结构可按复杂度删减，但不能牺牲独立可复现性：

```text
1. 目标
2. 基础对象与变量表
3. Profile / 结构锚定义
4. 事件定义
5. 状态变量
6. 开仓条件候选
7. 入场函数
8. 执行函数：价格、止损、目标、仓位
9. 退出函数
10. 状态重置
11. 候选矩阵或首轮默认候选
```

## 数学记号规则

数学表达采用纯文本记号，保证 IDE 普通 Markdown、diff、Trae AI 预览与长期归档均可读：

- 不依赖 KaTeX / MathJax / Markdown 插件渲染。
- 数学定义放入 `text` fenced code block。
- 行内少量符号用反引号，如 `τ = price_tick`。
- 用 `:=` 表示定义。
- 用 `∧ / ∨ / ¬ / => / <=>` 表示逻辑关系。
- 用 `Σ / Π / τ / δ / α` 等 Unicode 数学符号，不写 LaTeX 命令。
- 用 `argmax_p (...)`、`argmin_p (...)`、`max{...}`、`min{...}`、`floor(...)` 等纯文本函数形式。
- 不使用 `$...$`、`$$...$$`、`\begin{aligned}`、`\begin{cases}` 等公式渲染语法。

示例：

```text
d-1     := previous trading session used to build profile
I_{d-1} := bar index set of session d-1
C_{d-1} := close price of session d-1
τ       := price_tick

Π_close(p) := Σ_{t∈I_{d-1}} V_t · 1[round_τ(C_t) = p]
M_close    := {p ∈ G_{d-1} | Π_close(p) = max_{u∈G_{d-1}} Π_close(u)}
POC_close  := argmin_{p∈M_close} |p - C_{d-1}|

Enter(s,t;θ) := ExecOK(t)
              ∧ R_s(t)
              ∧ RiskOK(s,t)
              ∧ C_Ω(s,t)
```

## 规格与实现的关系

- 规格先于实现。
- 规格中未定义的行为，代码中不要自行脑补。
- 实现需要新增参数或改变行为时，先更新 `strategy-math-spec.md`。
- 回测计划和实验记录可以引用规格，但不要把实验流水账写进 `strategy-math-spec.md`。

## 每次修改后的静态一致性检查

每次修改 `strategy-math-spec.md` 都必须**主动**执行一轮"通篇检查有没有矛盾、明显不合理、重复、约束不正交"，不等用户提醒。检查前先完整重读文档，再逐条对照下列清单，把发现的问题与修复动作写在同一次答复中。

### 检查清单

1. **符号一致性**
   - 每个符号在使用前是否已定义；同一符号是否在不同位置代表不同含义。
   - 变量的量纲是否统一：`idx(·) / time(·) / τ` 等分区，不同量纲不得在同一比较中出现。
   - 大小写、下标形式（`X_s` vs `X(s,t)`）是否全文统一。
2. **时间与索引**
   - `t_entry, t_exit, t_ref(t)` 是"bar 引用"还是"idx 数值"必须一致；用 `idx(·)` 与 `time(·)` 明确类型。
   - 窗口回溯用 bar 条数（`n_·`）还是钟表时长（`W_·`）必须与实际使用位置一致。
3. **状态变量正交性**
   - `X_s`、`A_s / B_s^- / Z_s^-`、`P_t / D_t / U_t`、`T_refresh / T_adopt`、`T_last_exit / TradeCount_d` 各自的更新触发源是否不重叠。
   - 重置事件（session reset、breakout reset、profile refresh）是否显式声明"影响哪些状态、不影响哪些状态"。
4. **候选集合与配对矩阵**
   - 每组候选（形态 / 风控 / 方向 / 止盈 / ...）内部是否析取（∨），组间是否合取（∧）。
   - 配对矩阵维度是否与所有候选集合数量一致；退化情形（`Ω = {全集}`）是否等价于"不启用该组过滤"。
5. **触发条件冗余与蕴含**
   - `Enter / Exit` 判定式中是否有被其它子式蕴含的项（可降级为注解）。
   - `RiskOK / SpaceOK / DirOK` 之间是否有互相蕴含的严格不等式。
6. **退出优先级与成交模型**
   - `first_true` 顺序是否与优先级声明一致。
   - 每种退出触发的成交价（engine fill vs strategy-level C_t）是否明确到每个候选。
7. **默认候选与参数**
   - 首轮默认（`§11` 或等价小节）是否覆盖 `θ_profile / θ_signal / θ_exec / θ_size` 中所有会影响回测的参数。
   - 有条件参数（例如 `rr_raw_min` 只在 `R1 ∈ Ω_risk` 时有效）是否声明在无关配置下归并为单点。
8. **散文与公式一致性**
   - 每段散文说明是否与紧邻的公式定义完全等价；散文若添加公式未覆盖的约束，应升级为公式。
   - 冗余的"重复解释同一件事"的段落应合并或删除。
9. **量纲汇总表**
   - 若文档含"量纲约定"表，新增变量必须归入其中之一。
10. **孤立符号**
    - 用文本搜索方法检查是否存在只被定义未被使用（死变量），或只被使用未被定义（悬空引用）。

### 产出格式

- 用短表格列出「问题 → 位置 → 修复」；
- 对每处修复实际调用 SearchReplace 工具改动文档；
- 最后附一段"验证正交性"总结，说明本轮修改后各正交维度间的相互作用是否仍然清晰。
- 若清单项均未发现问题，也必须显式说明"本轮无需修复"，不省略该步。

### 触发条件（除主动触发外）

- 用户显式要求"检查一致性 / 冗余 / 正交"时；
- 用户在同一轮修改中新增 / 删除 / 合并了任何状态、参数、候选、退出条件时；
- 用户提出概念性问题后规格随之调整时。

## 与其他 skill 的边界

- 主题目录布局、其他辅助文档写法、跨文档流程、workbench / archive / issues / roadmap 边界：全部见 `quant-research-layout`。
- 本 skill 不涉及回测运行、数据管道、CLI；相关问题分别由 `quant-cli`、`quant-project` 等 skill 负责。
