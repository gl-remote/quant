# structural-shaping-alpha · Research Status

> 类型：Research Status
> 状态：**立题（假设生成期）**
> 最近更新：2026-07-05
> 主题 README：[README.md](README.md)
> 实验计划：[experiment-plan.md](experiment-plan.md)

## 一句话结论

**主题刚立题，尚无实验结果**。核心问题："结构塑形技巧（仓位 / 时间退出 /
止盈止损）本身是否具有独立 alpha？"—— 待阶段 1 广度扫描验证。

## 边界

**立题时假设的边界**（结果尚未验证）：

1. **不使用 value-area 家族已证伪的入场信号**（POC / reacceptance / rolling POC / 距离档过滤）
2. **入场固定为 no_trigger baseline** 或 random 时点，避免变成入场信号研究
3. **结构塑形维度**限定为四类：仓位管理 / 时间退出 / 止损 / 止盈
4. **判据必须多层对照**：标准结构 baseline + random 入场 baseline + 至少一种备用 baseline 交叉验证

## 下一步

**阶段 1 · 广度扫描（Gatekeeper）**：

四个子维度并行扫描，任何一个通过（相对标准结构 baseline 显著优于），即
进入阶段 2；全部不通过则冻结主题。

- 阶段 1a：仓位维度
- 阶段 1b：时间退出维度
- 阶段 1c：止损维度
- 阶段 1d：止盈维度

判据细节见 [experiment-plan.md](experiment-plan.md)。

## 立题日期

**2026-07-05**
