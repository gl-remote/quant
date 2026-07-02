---
name: "quant-strategy-spec"
description: "Defines strategy math spec rules. Invoke before implementing or rewriting any quant strategy, or when writing strategy spec docs."
---

# Quant Strategy Math Spec

每次实现新策略或重写策略前，必须先在 `docs/workbench/` 写一个完整、严谨、独立可复现的数学规格 Markdown 文档。

该文档是实现前的策略契约。实现代码必须以规格为准；如果实现时发现规格缺失，先回补规格再写代码。

## 核心原则

- 单独阅读文档即可复现策略，不依赖代码实现、聊天上下文或历史实验记忆。
- 变量定义遵循“必要且充分”原则：影响策略语义、执行结果或可能产生歧义的变量必须定义。
- 一眼可辨认、能轻易达成共识的常规字段不必逐项解释，例如 `O_t/H_t/L_t/C_t/V_t` 可整体说明为 OHLCV bar。
- session、bar 索引、tick、profile、状态变量、策略参数、派生参数和 tie-break 规则应显式定义。
- 所有候选分支必须列成有限集合，例如 `poc_mode ∈ {close, range}`。
- 所有 tie-break 规则必须显式写出，不能隐藏在 `argmax` 或代码实现里。
- 入场、出场、止损、止盈、仓位、冷却、每日交易次数、状态重置必须以数学/伪数学规则固定。
- 数学表达的目标是精确、简要、可实现；不要为显然概念写冗长解释。
- 文档只固定策略定义和候选集合；实验结果、调参过程、临时观察另写实验记录。

## 推荐结构

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

结构可按策略复杂度删减，但不能牺牲独立可复现性。

## Markdown 数学规格规则

研究文档中的数学表达优先采用纯文本数学规格，保证 Trae AI 内部预览、IDE 普通 Markdown、diff 和归档长期可读。

- 不依赖 KaTeX / MathJax / Markdown 插件渲染。
- 数学定义放入 `text` fenced code block。
- 行内少量符号可直接使用反引号标记，例如 `τ = price_tick`。
- 使用 `:=` 表示定义。
- 使用 `∧` / `∨` / `¬` / `=>` / `<=>` 表示逻辑关系。
- 使用 `Σ` / `Π` / `τ` / `δ` / `α` 等 Unicode 数学符号，但不要写 LaTeX 命令。
- 使用 `argmax_p (...)`、`argmin_p (...)`、`max{...}`、`min{...}`、`floor(...)` 等纯文本函数形式。
- 不使用 `$...$`、`$$...$$`、`\begin{aligned}`、`\begin{cases}` 等公式渲染语法。

## 示例

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

## 规格与实现关系

- 规格先于实现。
- 规格中未定义的行为，代码中不要自行脑补。
- 实现需要新增参数或改变行为时，先更新规格。
- 回测计划和实验记录可以引用规格，但不要把实验流水账写进规格。
