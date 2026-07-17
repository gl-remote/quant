# value-area-rolling-reacceptance · Research Status

> 类型：Research Status
> 状态：**已冻结（Frozen 2026-07-05）**
> 主题 README：[README.md](README.md)
> 归档：[../../../../archive/strategy-research/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md](../../../../archive/strategy-research/2026/07/2026-07-05-value-area-rolling-reacceptance-freeze/freeze-summary.md)

## 一句话结论

**主题假设完全失败**。POC 无独特引力（fixed 与 rolling 双版本证伪），
reacceptance 非特殊触发器，4+ ATR 距离档本身也没有可交易的 mean-reversion
edge。5m 与 15m 双周期一致证伪。

## 边界

**已被证伪的假设（禁止再作为策略依据）**：

1. POC 是特殊的均值锚（fixed 定义）—— Stage 1.5-A5/A5b 证伪
2. Rolling POC 相对 fixed POC 有独立价值 —— Stage 4 显著性检验证伪
   （配对差值 -0.137, p=0.646）
3. Reacceptance 事件是特殊触发器 —— Stage 4b 证伪
   （vs no_trigger diff +0.019 (5m) / -0.088 (15m)，p 均不显著）
4. 4+ ATR 距离档本身提供 mean-reversion edge —— Stage 4b 证伪
   （no_trigger baseline 期望净值 ≈ 0）

**保留可复用的资产**：

1. **方法论**：ATR 归一化 / 期望净值判据 / 结构×距离档二维 / 多锚点+多触发器
   +no_trigger baseline / 配对检验 / cluster bootstrap
2. **技术设施**：volume profile / reacceptance detection / 六触发器检测 /
   六种交易结构模拟 / bootstrap 双检验（脚本已归档到 archive/raw-scripts/）
3. **反例经验**：距离档过滤不等于 edge / 未配对差异易假象 / 单一变量对照
   易得假象

## 下一步

**不再作为独立策略推进**。与前主题 `value-area-reacceptance` 相同命运。

**后续主题使用本主题成果的方式**：

- 立新的 mean-reversion / structural alpha 主题时，**必须遵循**归档
  `freeze-summary.md §8.2` 的五条方法论要求
- 若使用本主题的技术设施，从 `archive/raw-scripts/` 拷贝并适配
- 若发现本主题 §8.3 提到的三个潜在方向值得研究，需另立独立主题
  （例：15m black 反向 edge / agri_dce 品种特异性 / rolling window 在非
  POC 场景的价值）

## 冻结日期

**2026-07-05**
