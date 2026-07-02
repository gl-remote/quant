# value_area_reacceptance 主题研究现状

> 类型：Research / 主题状态
> 状态：活跃 / R29 扩样未通过 / R30 结构分支验证
> 最近更新：2026-07-02
> 当前归档：[R29 扩样与随机基准复验](../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
> 前置归档：[R28 结构诊断](../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md)
> 返回总入口：[strategy-current.md](../strategy-current.md)

## 1. 主题一句话结论

```text
value_area_reacceptance 不再作为一个可直接上线的固定交易策略推进。

旧实现已重命名为 value_area_reacceptance_baseline，用于复现 R27-R29 历史规则和做结构基准。

R29 扩样没有通过，但随机入场基准显示 VA reacceptance 事件仍有信息量。
因此下一阶段不是继续调旧参数，而是拆成两条结构线：
1. VA 边界 → POC 的多次回归测试；
2. failed reacceptance / continuation 对照线。
```

边界：

```text
1. R28 DCE.p 四样本不能再视为已验证主线；
2. R29 失败不能直接否定 VA reacceptance 事件；
3. seq1/seq2/seq3 不应继续被机械地混成一套 reentry 逻辑；
4. R30 先验证结构条件，不先调 stop/target。
```

## 2. 当前保留代码与基准

```text
value_area_reacceptance_baseline
- 旧候选策略的 baseline 版本；
- 保留 R27-R29 回测口径、诊断字段、退出逻辑；
- 不再代表当前候选交易策略。

value_area_random_baseline
- 长期随机入场基准；
- 复用 VA baseline 的事件、止损和退出口径；
- 用 same-direction / random-direction 随机入场判断结构入口是否优于随机。
```

轻量随机基准 runner：

```text
scripts/analysis/value_area_random_baseline_compare.py
```

注意：runner 的 `total_net_pnl` 使用 vnpy BacktestResult 口径，只能做同一 runner 内相对比较，不和 trade_clearings 清算口径混算。

## 3. 已完成阶段结论

### 3.1 R27 扩样后的降级

```text
旧 m/SR + 1m + A4_ratio_80 + actual RR=0.8 + min_reaccept_ticks=2/3 外推失败；
旧 m/SR 单笔 POC 回归线不再作为主候选。
```

### 3.2 R28 结构诊断

```text
DCE.p 四样本内：
- max_trades_per_day=1 时首笔 VA reacceptance 收益有限；
- max_trades_per_day=3 后主要收益来自第 2 笔；
- 第 1 笔更像 VA reversion；
- 第 2/3 笔可能更像 continuation / retry；
- reentry target 1.0R~1.35R 构成样本内平台，但继续细调会过拟合。
```

### 3.3 R29 扩样与随机基准

```text
固定 R28 后的保守候选没有通过扩样：
- DCE.m 明显失败；
- DCE.y 接近但未通过；
- DCE.c / DCE.cs 信号不足或弱负；
- DCE.p 更早历史窗口失败，seq1 强负，seq2 接近打平。

随机入场复验显示：
- 结构规则虽然亏损，但仍优于 same-direction random；
- 旧 DCE.p 失败样本上，结构没有退化成随机噪声；
- 问题更可能在环境过滤、风险空间、交易序列或退出兑现层。
```

## 4. R30 主规则设想

R30 将旧的“上一笔 stop_loss / 亏损后才 reentry”改成结构状态判断。

### 4.1 VA 回归主线

只做 VA 边界 → POC 更近方向：

```text
VAL reacceptance long：entry 在 POC 下方，做多回归 POC；
VAH reacceptance short：entry 在 POC 上方，做空回归 POC。
```

同侧多次交易不再按第几笔定义，而是记录同侧 VA 边界测试状态：

```text
last_breakout_ticks：上一次同侧打破 VA 边界的突破距离；
last_reached_poc：上一次同侧回归是否充分测试 POC；
attempt_count：当前 session 内同侧回归尝试次数。
```

允许开仓的候选条件：

```text
B1：首次测试 POC；
B2：current_breakout_ticks < last_breakout_ticks，说明外部接受力度减弱；
B3：last_reached_poc is False，说明上次 POC 共识测试未完成。
```

### 4.2 continuation 对照线

做远离 POC 的方向：

```text
VAL reacceptance 后寻找继续向下 / failed reacceptance；
VAH reacceptance 后寻找继续向上 / failed reacceptance。
```

这条线不再解释为 VA 回归，而是 continuation 候选；必须单独统计，不和 VA 回归主线混评。

## 5. R30 小矩阵

| 组合 | 方向分支 | 开仓条件 | 目的 |
| --- | --- | --- | --- |
| R30-A | 更接近 POC | 首次测试 POC | 验证最纯 VA 回归是否仍有边际 |
| R30-B | 更接近 POC | 突破距离弱于上次 | 验证外部接受衰减是否提高胜率 |
| R30-C | 更接近 POC | 上次 POC 未充分测试 | 验证多次回归是否有结构价值 |
| R30-D | 更接近 POC | B2 或 B3 | 验证完整多次 VA 回归规则 |
| R30-E | 更远离 POC | 单独记录 | continuation 候选对照 |

核心观测指标：

```text
POC touch rate
entry_to_poc_ticks
breakout_ticks
breakout_ticks_delta
by_condition pnl
overlap pnl
stop_loss 占比
by_environment
random baseline percentile
```

## 6. 当前不建议继续的方向

| 方向 | 当前处理 | 原因 |
| --- | --- | --- |
| 继续调旧 value_area_reacceptance_baseline | 停止 | baseline 只保留历史口径，不再叠加新逻辑 |
| DCE.p 四样本内继续细调 1.3 / 1.35 / 1.4 | 停止 | R29 已证明不能直接外推 |
| 把 seq2 直接解释为 VA 回归 | 暂停 | 可能属于 continuation，需要拆分验证 |
| 直接用 strong_trend 过滤 | 暂缓 | 需要先看结构条件是否解释失败 |
| ATR / volatility normalization 入主规则 | 暂缓 | 可能有助于泛化，但不应先混入主效应 |
| range-profile 替换 close-profile | 暂缓 | 当前主问题不是 profile 定义替换 |

## 7. 下一阶段待验证

```text
1. 新建 R30 workbench 文档；
2. 实现独立的新策略或诊断策略，不在 baseline 上继续叠加；
3. 固定 R29 样本和基础参数，先验证结构条件；
4. 分别输出 B1/B2/B3 及 overlap 的 POC touch rate、pnl、stop_loss 占比；
5. 用 value_area_random_baseline 做同 runner 随机对照；
6. 如果 VA 回归主线失败而 continuation 对照更好，再把 continuation 独立成下一条策略线。
```

## 8. 关联文档

| 目的 | 文档 |
| --- | --- |
| 总入口 | [strategy-current.md](../strategy-current.md) |
| R29 扩样与随机基准复验 | [value-area-reacceptance-r29-expanded-validation.md](../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md) |
| R28 结构诊断 | [value-area-reacceptance-r28-structure-diagnosis.md](../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md) |
| R27 扩样复验 | [value-area-reacceptance-r27-expanded-sample.md](../../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md) |
| POC / VA 质量诊断阶段归档 | [value_area_reacceptance POC / VA 质量诊断阶段归档](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| R16-R24 actual RR 重整 | [value-area-reacceptance-r16-r24-1m-actual-rr-summary.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md) |
| R25 1m vs 5m | [value-area-reacceptance-r25-1m-vs-5m-actual-rr.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md) |
| R26 稳定性检查 | [value-area-reacceptance-r26-1m-stability-check.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r26-1m-stability-check.md) |
