# 策略当前研究进度

> 类型：Research / 当前策略研究状态\
> 状态：活跃 / 阶段收束，等待扩大样本复验\
> 最近更新：2026-07-01\
> 最新阶段归档：[value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)\
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)

## 1. 当前一句话结论

```text
当前最值得继续的主线是 value_area_reacceptance。
POC / VA 质量诊断阶段已归档；
edge_or_away 是当前最强坏结构候选过滤器，
但仍处于影子评估，下一步应扩大样本验证。
```

当前不要把 `would_filter_edge_or_away` 当作真实过滤条件。

## 2. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| value_area_reacceptance | 主线 / POC 质量诊断已阶段收束 / 影子过滤待复验 | [value-area-reacceptance.md](./themes/value-area-reacceptance.md) |

当前主线摘要：

```text
value_area_reacceptance
+ 5m close-profile previous-day POC / VA
+ min_reaccept_ticks 2~3
+ POC target
+ price_raw_rr / min_target 预筛
+ POC 质量诊断标签
+ edge_or_away 影子过滤评估
```

详细定义、统计结果、分品种结论和下一阶段问题见主题文件。

## 3. 当前阶段状态

最新阶段归档：

- [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)
- [R1~R15 原始实验记录](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/)

阶段性结论：

```text
value_area_reacceptance 的有效性不来自“POC 更远、raw_rr 更高”，
而来自旧 VA 边界被快速拒绝后，
价格仍能回到一个位置合理、未失效、可兑现的 POC / POC band。
```

当前最强坏结构标签：

```text
edge_or_away = poc_edge_bucket == edge
            or current_acceptance_migration_bucket == away
```

R15 影子过滤在当前样本内显著改善结果：

```text
raw:
n=41, win_pct=43.9%, net_pnl=1890.206, left_tail_1000=4

shadow_kept:
n=25, win_pct=64.0%, net_pnl=10754.990, left_tail_1000=1

shadow_filtered:
n=16, win_pct=12.5%, net_pnl=-8864.784, left_tail_1000=3
```

但该结论尚未完成跨合约、跨月份、更长历史验证。

## 4. 下一步优先级

优先做：

```text
1. 扩大样本复验 edge_or_away shadow filter；
2. 建设 report 层 raw / shadow_kept / shadow_filtered 固定视图；
3. 继续评估账户风险预算和品种左尾；
4. 分品种判断 DCE.m 是否适合进入候选策略，SR / rb 是否应降级或排除。
```

当前不建议做：

```text
1. 不继续广撒新入口；
2. 不在当前样本继续切更细标签桶；
3. 不继续优化 fixed ticks；
4. 不直接切换 15m；
5. 不直接切换 range-profile；
6. 不直接启用 edge_or_away 真实过滤。
```

## 5. 文档地图

| 目的 | 文档 |
| --- | --- |
| 当前状态入口 | 本文件 |
| value_area_reacceptance 主题状态 | [themes/value-area-reacceptance.md](./themes/value-area-reacceptance.md) |
| 最新阶段归档 | [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| 最新阶段原始记录 | [raw-workbench](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/) |
| 上一阶段归档入口 | [结构型 Alpha 随机对照阶段归档 README](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md) |
| 上一阶段结题报告 | [structural-alpha-stage-final-report.md](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md) |
| 长期框架 | [strategy-research-framework.md](../roadmap/strategy-research-framework.md) |

## 6. 给 AI 的工作规则

后续 AI 接手时：

1. 先读本文件；
2. 再读 [value_area_reacceptance 主题状态](./themes/value-area-reacceptance.md)；
3. 再读 [最新阶段归档摘要](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)；
4. 不要从 `raw-workbench` 开始理解阶段结论；
5. 不要重复铺开随机对照，除非用户明确要求做覆盖审计；
6. 不要继续广撒新入口；
7. 不要在当前样本上继续切更细标签桶；
8. 新实验过程写入 `docs/workbench`；
9. 若发现回测、数据、vnpy 成交配对、成本口径问题，先写入 `docs/issues` 并暂停受影响实验；
10. 阶段稳定后，再归档到 `docs/archive/strategy-research`。

## 7. 当前状态

```text
value_area_reacceptance POC / VA 质量诊断阶段已归档；
edge_or_away 已是强候选过滤器，但仍处于影子评估；
不扩大样本时，不建议继续做策略发现型实验；
下一步优先扩大样本复验或建设 report 层 shadow filter 视图。
```
