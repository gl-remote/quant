# Issues 工作流

本目录记录实验或研究过程中发现的底层框架问题。

## 什么时候在这里提 issue

当策略实验中发现问题不再属于策略逻辑本身，而可能来自以下层面时，应在本目录新增 issue 文档：

- 回测引擎统计口径异常；
- DataFeed / 缓存 / 周期加载不一致；
- vnpy 桥接、开平仓、成交配对异常；
- CLI / runner 与策略 `data_requirements` 不一致；
- 指标、成本、滑点、手续费、PnL 等基础口径存在疑问。

## 处理原则

发现底层框架 bug 后，默认流程是：

1. **停止当前策略实验**  
   不继续把受污染结果当作策略证据。

2. **在本目录提 issue**  
   记录现象、影响面、最小复现方向、关联实验和相关代码。

3. **中断推进并等待确认**  
   不在同一实验上下文里盲目修改框架代码后继续跑结果。

4. **单独修复框架问题**  
   框架修复应有明确边界、回归测试和验证命令。

5. **修复确认后再恢复实验**  
   恢复实验时需要在实验文档中说明哪些历史结果受影响，哪些结果是修复后重新生成的。

## issue 文档建议结构

```text
# 问题标题

> 类型：框架缺陷 / 数据口径 / 回测链路
> 状态：待排查 / 已确认 / 已修复 / 已验证
> 发现日期：YYYY-MM-DD
> 发现分支：...
> 关联实验：...
> 相关代码：...

## 背景

## 现象

## 影响

## 最小复现方向

## 当前处理建议
```

## 当前 issue 索引

| Issue | 状态 | 说明 |
|-------|------|------|
| [cli-entry-workspace-pythonpath.md](./cli-entry-workspace-pythonpath.md) | 已确认 | CLI 入口未自动暴露 `workspace` 包路径 |
| [vnpy-close-trade-pairing-warning.md](../archive/backtest/vnpy-close-trade-pairing-warning.md) | 已验证 / 已归档 | vnpy 平仓未配对警告影响成交级统计口径 |
| [vnpy-tradedata-dynamic-payload.md](./vnpy-tradedata-dynamic-payload.md) | 已确认 | vnpy `TradeData` 动态扩展承载策略决策 payload 存在桥接边界风险 |
| [prevday-volume-random-baseline-performance.md](./prevday-volume-random-baseline-performance.md) | 待排查 | `prevday_volume_filter` 随机对照批量运行性能异常偏慢 |

## 重要约定

- issue 文档记录的是框架问题，不是策略结论。
- 未修复 issue 影响到的实验结果，不能作为主结论。
- AI 助手发现底层框架 bug 时，应先写 issue 并暂停，除非用户明确要求继续修复。
