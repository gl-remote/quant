# 方向+强度配合 · 实验计划

> 类型：Research / 实验计划
> 关联主题：theme:direction-strength-combo
> 上游：theme:direction-strength-combo#screening-methodology

## 一、实验目标

验证方向+强度配合的核心假设：存在某些结构性特征，它们天然同时编码了方向偏置和强度信息，通过联合利用可以获得比单独使用任何一种信息更高的风险调整收益。

## 二、候选矩阵

### 2.1 方向信号来源

| 方向信号 | 描述 | 数据来源 | 优先级 |
|----------|------|----------|--------|
| **ema_cross** | EMA20 上穿/下穿 EMA60 | 待构造 | P0（主方向） |
| **rsi_signal** | RSI(14) > 70 → short，RSI < 30 → long | 待构造 | P0（主方向） |
| **ma_cross** | MA50 上穿/下穿 MA200 | 待构造 | P1（替代方向） |

### 2.2 强度条件来源

| 强度条件 | 描述 | 分档方式 | 优先级 |
|----------|------|----------|--------|
| **atr_rank** | 当前 ATR 在滚动窗口（10 日）中的百分位 rank | 3 档（低/中/高） | P0 |
| **skew_abs_rank** | A3_skew 绝对值在滚动窗口中的百分位 rank | 3 档（低/中/高） | P0 |
| **volume_rank** | 成交量在滚动窗口（20 日）中的百分位 rank | 3 档（低/中/高） | P1 |
| **composite_strength** | (atr_rank + skew_abs_rank + volume_rank) / 3 | 3 档（低/中/高） | P2 |

### 2.3 候选组合矩阵

| 编号 | 方向信号 | 强度条件 | 模式 | 优先级 | 预期结果 |
|------|----------|----------|------|--------|----------|
| C1 | ema_cross | atr_rank | 模式 B | P0 | 高 ATR 时段方向信号更有效 |
| C2 | ema_cross | skew_abs_rank | 模式 A | P0 | skew 大时方向信号更有效 |
| C3 | rsi_signal | atr_rank | 模式 B | P0 | 高 ATR 时段方向信号更有效 |
| C4 | rsi_signal | skew_abs_rank | 模式 A | P0 | skew 大时方向信号更有效 |
| C5 | ema_cross | volume_rank | 模式 B | P1 | 高成交量时段方向信号更有效 |
| C6 | ema_cross | composite_strength | 模式 C | P2 | 综合强度高时方向信号更有效 |

## 三、验证顺序

### 3.1 第一阶段：模式 A + B（基础验证）

1. **C1**：ema_cross + atr_rank
2. **C2**：ema_cross + skew_abs_rank
3. **C3**：rsi_signal + atr_rank
4. **C4**：rsi_signal + skew_abs_rank

**判定标准**：
- 任一组合通过 Gate 1+2 → 进入第二阶段
- 全部组合 Gate 1 不过 → 重新审视假设

### 3.2 第二阶段：模式 C（综合验证）

5. **C5**：ema_cross + volume_rank
6. **C6**：ema_cross + composite_strength

**判定标准**：
- 配合增益是否高于单因子
- 是否稳定

## 四、判定标准

### 4.1 Gate 判决（见 screening-methodology §四）

| Gate | 判据 | 通过条件 |
|------|------|----------|
| Gate 1 | ANOVA p-value | < 0.05 |
| Gate 2 | 配合增益 | ≥ 1.2 |
| Gate 3 | 时间半分稳定性 | 后半段增益 ≥ 前半段 80% |

### 4.2 分级标准

| 等级 | 条件 | 结论 |
|------|------|------|
| L1 强配合 | Gate 1+2+3 全过，增益 ≥ 1.5 | 核心策略组件 |
| L2 边缘配合 | Gate 1+2 过，Gate 3 边缘 | 融合池候选 |
| L3 弱配合 | Gate 1 过，增益 1.1–1.2 | 辅助过滤 |
| L4 无配合 | Gate 1 不过或增益 < 1.1 | 归档反例 |

## 五、固定参数

### 5.1 数据参数

- 品种：玉米 3 合约（c2601 / c2603 / c2605）
- 周期：1h
- 数据窗口：约 1252 bar（与 strength-factor-screening 一致）

### 5.2 塑形容器参数（来自 KF-27）

- K_S = 2.5 ATR（跳空安全下限）
- K_T = 10.0 ATR（非对称塑形）
- RR = 4.0
- τ = 前 65% 段

### 5.3 特征参数

| 参数 | 值 | 来源 |
|------|-----|------|
| atr_rank_win | 10 | 经验值 |
| skew_rank_win | 10 | 经验值 |
| volume_rank_win | 20 | 经验值 |
| ema_short | 20 | 经验值 |
| ema_long | 60 | 经验值 |
| rsi_period | 14 | 经验值 |

## 六、实验输出

### 6.1 每个候选的输出

- 各强度分档的 E_net、胜率、盈亏比
- 配合增益（高强度 / 平均）
- ANOVA / Kruskal-Wallis p-value
- 时间半分稳定性指标
- Gate 判决结果
- 分级结果

### 6.2 汇总输出

- 候选矩阵汇总表
- 通过候选清单
- 关键发现（写入 research-status.md 的 KF 清单）

## 七、时间计划

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| 第一阶段 | C1-C3 实验 | 1-2 天 |
| 第二阶段 | C4 实验 | 0.5-1 天 |
| 第三阶段 | C5-C6 实验 | 1 天 |
| 总结 | KF 登记 + 文档更新 | 0.5 天 |

## 八、风险与边界

### 8.1 数据泄露风险

- 强度条件必须使用事前信息
- 滚动窗口必须 shift(1)，避免使用当日数据

### 8.2 过拟合风险

- 分档数限制为 3 档
- 时间半分验证作为最终 gate

### 8.3 相关性风险

- 如果方向信号和强度条件高度相关，配合效应可能是伪影
- 需要报告相关性系数

## 九、后续工作

1. 实现 workbench 脚本
2. 执行实验
3. 更新 research-status.md
4. 根据结果决定是否继续深入或归档
