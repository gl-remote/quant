# value\_area\_reacceptance 阶段规划：风险预算、品种适配与尾部补证

> 类型：Workbench / 阶段规划\
> 状态：活跃规划\
> 创建日期：2026-06-30\
> 当前研究入口：[strategy-current.md](../../../../research/strategy-current.md)\
> 长期框架：[strategy-research-framework.md](../../../../roadmap/strategy-research-framework.md)\
> 上一阶段归档：[结构型 Alpha 随机对照阶段归档](../../2026-06-29-structural-alpha-random-baseline/README.md)

## 1. 当前阶段判断

上一阶段已经完成“结构入口是否整体等同随机”的验证，当前结论是：

```text
结构入口不是整体随机；
价值区 VAH / VAL 重新接受是当前最值得继续的主线；
但方向 edge 尚未证明能在账户风险预算、品种适配、尾部风险和成本约束下稳定兑现。
```

因此，本阶段不继续广撒新结构入口，也不急于优化主动止盈 / 分段目标 / MFE 回撤退出，而是围绕 `value_area_reacceptance` 做补证。

当前主线版本：

```text
value_area_reacceptance
+ POC 空间
+ price_raw_rr 预筛
+ min_reaccept_ticks 2~3
+ max_hold_bars ≈ 12
```

结构含义：

```text
前日 VAL 下破失败后重新接受回价值区内 → 做多，目标 POC；
前日 VAH 上破失败后重新接受回价值区内 → 做空，目标 POC；
不在刚贴边收回时立刻入场，而等待 5m 收盘价进入价值区内侧一定深度；
只保留到 POC 有足够空间且价格原始盈亏比不太差的样本。
```

## 2. 本阶段目标

本阶段目标不是证明策略已经可实盘，而是回答：

```text
value_area_reacceptance 是否值得进入下一轮策略实现和参数平台验证？
```

需要补足四类证据：

```text
账户风险预算是否可执行
→ 品种机制差异是否可解释
→ 重新接受深度是否能归一化
→ 尾部风险、成本和滑点安全边际是否可接受
```

若上述证据不足，则本主线应降级为观察结构或质量标签，不进入更复杂的退出优化。

## 3. 不做什么

本阶段明确不做：

1. 不继续广撒新结构入口；
2. 不把 `2~3 ticks` 当最终稳定参数；
3. 不直接进入 Optuna / Bayesian search；
4. 不把主动止盈、分段目标、MFE 回撤退出作为主线优化对象；
5. 不为凑交易数放宽价值区重新接受定义；
6. 不用止损放宽硬修边界太近或接受质量不足的问题；
7. 不只看收益率、夏普、最大回撤和最优参数；
8. 不忽略合约乘数、最小手数、滑点、跳空和 force\_flat 对账户风险的影响。

## 4. 核心研究假设

### 4.1 方向假设

```text
价格假突破 VAH / VAL 后重新接受回前日价值区内，
可能说明市场拒绝区间外价格，
并倾向向 POC 或价值区内部回归。
```

### 4.2 风险空间假设

```text
重新接受深度足够时，
入场价格、严格失败边界和 POC 盈利上界之间，
可能形成比同事件同方向随机风险空间更好的账户风险结构。
```

### 4.3 品种适配假设

```text
DCE.m 与 CZCE.SR 的价值区机制不同；
不同品种可能需要不同的 reaccept 深度定义、价值区宽度约束和风险预算过滤，
但不能依赖完全不相关的品种专属规则。
```

### 4.4 质量标签假设

```text
成交量冲击不适合作为独立主入口，
但可能改善价值区重新接受的接受质量、降低左尾或提高 POC 兑现概率。
```

## 5. 阶段验证顺序

本阶段按以下顺序推进：

```text
1. 账户风险预算预筛
2. 品种适配诊断
3. reaccept 深度、POC 与价值区定义诊断
4. 尾部风险与成本压力测试
5. 成交量冲击质量标签验证
6. 是否进入下一阶段策略实现 / 参数平台验证的决策
```

## 5.1 R1~R4 阶段性汇总

截至 R4，当前阶段已经形成以下中间结论：

```text
R1 风险预算预筛：
DCE.m2601 与 CZCE.SR601 在 5m、2~3 ticks、max_hold_bars≈12 下，
单次账户风险预算初步可执行，没有被合约乘数、最小手数或实际止损距离第一层否决。

R2 品种适配诊断：
品种分层明显。DCE.m2601 保留主线；CZCE.SR601 降为观察；
SHFE.rb2601 作为负面对照；DCE.c2601 / DCE.cs2601 因交易机会不足暂不评价。

R3 fixed ticks 邻域：
DCE.m2601 的有效区间集中在 2~3 ticks，但这不应被解释为精确最优参数。
1 tick 噪声偏多，4 ticks 又损失 POC 空间或样本质量。
该敏感性本身是重要发现：当前 POC / value area 参考系可能偏粗糙，
使重新接受深度、目标有效性和 raw_rr 过滤都依赖一个相对脆弱的锚点。

R4 周期敏感性：
真实 15m 交易周期不适合作为当前主线。提高周期虽可能降低噪声，
但也会改变“失败后快速重新接受并回归 POC”的信号语义，
使信号变慢、变模糊，并错过 POC 回归窗口。

R5~R9 POC / VA 定性诊断：
POC / VA 形态比 fixed ticks 更接近当前结构质量解释变量。
POC 靠边是明显风险信号；target_to_va 过大并不代表更好盈亏比，
反而常常说明 POC 不易在短持仓窗口内兑现。
R7 的 DCE.m2601 K 线路径复盘进一步确认：
好样本不是 POC 更远，而是旧 VA 边界被快速拒绝后，
价格仍能回到一个距离适中、位置合理、可兑现的 POC / POC band；
差样本常见当前日接受区迁移、旧 POC 失效或 VAH / VAL 只表现为历史密集区边缘。
R8 的 profile 定义对照显示：close-profile POC 并非完全错误，
在关键盈利样本上反而比 range-profile 更贴近短期可兑现目标；
但单点 POC 不能处理多峰，naive 全局 POC band 会产生假阳性，
后续应优先定义局部连续的 POC acceptance node 和 POC 质量标签。
R9 的 POC 质量标签分桶显示：当前最有解释力的是 POC edge distance
和 current-day acceptance migration；它们共同指向同一问题：
旧 POC 是否仍是短期可兑现共识锚。
local band、multi-modal 和 close-vs-range divergence 更适合作为警示/诊断标签，
暂不适合直接硬过滤。
R10 的 VA width 归一化 reaccept 深度尝试显示：
把 fixed 2~3 ticks 改成 VA width 10% / 15% 后，
交易数量大体可接近原组，但 DCE.m2601 收益被压缩，CZCE.SR601 转负，SHFE.rb2601 仍为负；
说明 2~3 ticks 的敏感性不是单纯尺度归一化问题，
而是在“足够进入价值区”和“不能错过 POC 回归窗口”之间形成的经验折中。
R11 已完成 POC 质量标签诊断 payload 最小实现：
POC edge distance、current-day acceptance migration、local band、multi-modal、close-vs-range divergence
已经写入 backtest_trades.decision_payload_json，并由 clearing 透传到 trade_clearings.diagnostics_json；
这一步不改变交易信号，只把结构快照从事后临时脚本推进为策略运行时保留的数据字段。
R12 基于 diagnostics_json 重新分桶复验后确认：
R9 的核心结论可以直接复现，POC edge = edge 与 current acceptance migration = away 仍是明显风险桶；
但 central / near_poc 不是充分入场条件，只表示旧 POC 仍有可能作为短期可兑现锚，
还必须结合失败边界、target_to_va、成本和品种左尾。
profile 形态类标签仍应作为诊断/警示，不适合独立硬过滤。
R13 的组合标签诊断显示：
排除 edge_or_away 后，全样本净收益从 1890.206 提升到 10754.990，
胜率从 43.9% 提升到 64.0%，left_tail_1000 从 4 降到 1；
但 central_and_not_away 仍出现 SHFE.rb2601 左尾，说明组合标签已接近过滤候选，
但还需要日级去重和品种级验证，不能直接固化为交易规则。
R14 的日级去重验证将 41 笔清算压缩为 23 个 symbol / trading_day / direction 结构后，
edge_or_away 仍显著负向：优先 2 ticks 口径下 bad=-4197.644、not_bad=4613.664；
同结构平均 PnL 口径下 bad=-4503.392、not_bad=4633.791。
这说明 edge_or_away 不是重复样本造成的假象，
但 SHFE.rb2601 的 not_bad 仍为负，候选过滤器仍需影子评估和更大样本验证。
R15 已将 edge_or_away 推进为运行时影子过滤标签：
策略会写入 would_filter_edge_or_away / would_filter_reason，但不会改变 entry signal。
重新跑 456~461 后，raw 清算口径下 shadow_kept=10754.990、shadow_filtered=-8864.784；
日级平均 PnL 口径下 shadow_kept=4633.791、shadow_filtered=-4503.392。
影子过滤效果稳定，但 SHFE.rb2601 日级 shadow_kept 仍为负，说明品种左尾需单独处理。
当前更准确的理解是：POC / VA 真正有效时，
它们提供的是“较近失败边界 + 适中可兑现目标 + 足够原始盈亏比”，
而不是单纯提供更远目标或更高账面 raw_rr。
```

因此，实验线 C 仍有意义，但定位需要调整：

```text
不再把 reaccept 深度归一化理解为继续寻找最优 ticks；
而应先把 tick 敏感性作为 POC / value area 定义脆弱性的证据，
围绕 5m 执行周期，定性诊断 POC / VA 是否足以代表“共识价格区间”。
```

阶段性工作重心相应调整为：

```text
5m 执行周期暂时保留；
15m 不直接作为交易周期，只可作为 context / 质量标签候选；
后续优先做 POC / VA 定义、POC 空间、价值区宽度、重新接受深度之间的解释性诊断；
在 POC / VA 参考系被确认前，不进入 Optuna / Bayesian 参数搜索。
```

## 6. 实验线 A：账户风险预算预筛

### 6.1 要回答的问题

```text
strict failure 和 actual stop 在合约乘数、最小手数、滑点、跳空、force_flat 后，
是否仍能把单次账户风险控制在 2%~3%？
```

### 6.2 需要计算的字段

| 字段                         | 含义                                                     |
| -------------------------- | ------------------------------------------------------ |
| entry\_price               | 重新接受确认后的入场价格                                           |
| strict\_failure\_price     | 方向假设理论失效位置                                             |
| actual\_stop\_price        | 实际止损边界，若有止损放宽必须记录                                      |
| strict\_failure\_distance  | 入场到严格失败边界的价格距离                                         |
| actual\_stop\_distance     | 入场到实际止损边界的价格距离                                         |
| target\_price              | 默认目标为 POC 或价值区内部目标                                     |
| expected\_profit\_distance | 入场到目标价的价格距离                                            |
| price\_raw\_rr             | expected\_profit\_distance / strict\_failure\_distance |
| account\_risk              | 按合约乘数、手数、滑点后估计的单笔账户亏损                                  |
| account\_risk\_pct         | account\_risk / account\_equity                        |
| min\_lot\_executable       | 最小手数下是否仍能满足 2%\~3% 风险预算                                |
| force\_flat\_loss          | 非正常退出或收盘强平导致的亏损                                        |
| slippage\_stress\_loss     | 滑点上升后的单笔亏损                                             |

### 6.3 通过条件

至少需要满足：

```text
最小手数下单次账户风险可控制在 2%~3%；
actual stop 后账户风险仍不超预算；
滑点上升后没有立刻破坏风险预算；
force_flat 不产生系统性超预算亏损；
price_raw_rr 和 account_raw_rr 不因风险预算换算后失效。
```

### 6.4 失败处理

若失败原因是：

| 失败原因                          | 处理                 |
| ----------------------------- | ------------------ |
| 合约乘数 / 最小手数导致风险过大             | 该品种不适合当前账户规模，排除或降级 |
| strict failure 太近，正常噪声反复触及    | 不用止损放宽硬修，回到接受质量诊断  |
| actual stop 放宽后必须大幅降仓，账户盈亏比不足 | 暂停该参数组             |
| force\_flat / 跳空导致左尾不可控       | 暂停该品种或加入状态过滤后重测    |

## 7. 实验线 B：品种适配诊断

### 7.1 要回答的问题

```text
哪些品种天然适合价值区重新接受？
哪些品种只是偶然有效？
DCE.m 与 CZCE.SR 的差异是否可以被规则化解释？
```

### 7.2 诊断维度

| 维度                          | 目的                           |
| --------------------------- | ---------------------------- |
| value\_area\_width          | 判断价值区是否过窄或过宽                 |
| POC distance                | 判断到目标空间是否足够                  |
| tick\_size / tick\_value    | 判断 reaccept ticks 和账户风险是否可执行 |
| intraday\_range / ATR       | 判断价值区空间相对当日波动是否合理            |
| reaccept\_depth             | 判断重新接受是否只是贴边噪声               |
| event\_count                | 判断交易机会是否足够评价                 |
| stop\_loss / force\_flat 分布 | 判断左尾是否集中在特定品种                |
| POC hit rate                | 判断方向 edge 是否能兑现              |

### 7.3 初始对照

初始不追求大范围铺开，先比较：

```text
DCE.m 系列
CZCE.SR 系列
```

若两者机制可以被解释，再扩展到同类型或相似波动结构的品种。

### 7.4 输出

每个品种至少给出：

```text
适合 / 暂缓 / 排除
```

以及原因：

```text
账户风险预算；
价值区宽度；
POC 空间；
重新接受质量；
尾部风险；
成本敏感度；
样本数量。
```

## 8. 实验线 C：reaccept 深度、POC 与价值区定义诊断

### 8.1 背景

R3 的 fixed ticks 邻域和 R4 的周期敏感性显示：

```text
min_reaccept_ticks = 2~3 仍是重要正反馈，
但不能直接视为稳定参数平台或可优化参数。
```

更合理的阶段性解释是：

```text
当前 POC / value area 定义并不严格：
实验主线使用 5m close-profile 构造前日 POC / VA，
POC 同时承担目标价、空间过滤和 raw_rr 计算锚点。

因此，收益对 1~2 ticks 的重新接受深度非常敏感，
可能不是因为市场真的存在精确 tick 阈值，
而是因为当前 POC / VA 参考系偏粗糙，
导致边界、目标和空间判断都比较脆弱。
```

R4 也说明：

```text
直接提高交易周期并不是简单降噪。
15m 会改变信号语义，使重新接受确认变慢、变模糊，
并可能错过 POC 回归窗口。
```

因此，实验线 C 继续保留，但目标从“寻找 reaccept 深度最优归一化参数”调整为：

```text
解释 tick 敏感性从何而来；
判断当前 POC / VA 是否足以表达共识价格区间；
再决定是否有必要做深度归一化或参数平台验证。
```

### 8.2 当前 POC / VA 定义需要先被定性审查

当前策略主线的定义是：

```text
以前一交易日为 session；
用 5m bar 构造 volume profile；
实验主线 profile_mode = close，即每根 bar 的全部 volume 归到该 bar close；
POC = profile volume 最大的价格；
VAH / VAL = 从 POC 向两侧按相邻 volume 贪心扩展，直到覆盖 70% volume。
```

这一定义的风险是：

```text
close-profile 不是真实逐笔 volume profile；
POC 是单点锚，且同时影响目标、过滤和 raw_rr；
70% value area 可能过宽或过窄；
多峰分布下，单一 POC 可能不能代表共识价格区间；
POC 若略有偏移，成交数量、target_valid、min_target_ticks 和 raw_rr 都会显著变化。
```

因此，C 线下一步先做定性诊断，不急于调参数。

### 8.3 诊断问题

本线优先回答：

```text
1. 赚钱样本中的 POC 是否真的像“可回归的共识价格”？
2. 亏损样本中的 POC 是否常常偏离真实日内接受区？
3. VAH / VAL 是否像明确失败边界，还是只是粗略成交密集区边缘？
4. 2~3 ticks 的优势，是否只是补偿当前 POC / VA 定义粗糙性的经验阈值？
5. DCE.m 与 SR 的差异，是否来自 POC 空间、VA 宽度、多峰结构或 POC 稳定性不同？
6. 15m context 是否能作为质量标签，而不是直接作为交易周期？
```

### 8.4 候选解释维度

本线不再把 fixed ticks 当作唯一主变量，而是同时观察：

| 维度 | 含义 | 目的 |
|------|------|------|
| fixed_ticks | `reaccept_depth >= n ticks` | 保留 R3 现象，只作为观察标签 |
| VA width fraction | `reaccept_depth / previous_value_area_width` | 判断 ticks 是否只是价值区宽度的代理 |
| recent range fraction | `reaccept_depth / 最近 5m 波动` | 判断重新接受是否只是噪声尺度问题 |
| inside percentile | 收盘价进入前日价值区内部的位置分位 | 判断是否需要“进入区间内部”而非固定 ticks |
| POC distance | entry 到 POC 的距离 | 判断目标空间是否足以支撑结构 |
| POC stability | 多日 POC 漂移、value area overlap | 判断 POC 是否稳定可用 |
| VA shape | 单峰 / 多峰、VA 宽窄 | 判断单一 POC 是否有解释力 |
| context agreement | 15m / rolling context 与前日 POC 是否同向 | 判断高周期是否只能作为质量标签 |

### 8.5 评价标准

本线暂不以收益率最大化为目标，而以解释力为目标。

需要同时看：

```text
POC hit rate；
price_raw_rr；
account_raw_rr；
target_invalid / min_target_reject / raw_rr_reject 的来源；
stop_loss / force_flat 左尾；
成本后盈亏比；
盈利样本与亏损样本的 POC / VA 形态差异；
DCE.m 与 SR 是否能被同一组结构变量解释。
```

### 8.6 预期输出

本线输出不是单一最优参数，而是：

```text
1. 当前 POC / VA 定义是否足以支撑 value_area_reacceptance 主线；
2. tick 敏感性是否来自真实接受深度，还是来自 POC / VA 参考系粗糙；
3. fixed ticks、VA width fraction、波动 fraction、inside percentile 中，哪些只是现象标签，哪些有解释力；
4. 是否需要先改进 POC / VA 定义，再继续做 reaccept 深度归一化；
5. 15m 是否只适合作为 context / 质量标签，而不是交易周期。
```

### 8.7 C 线边界

本线明确不做：

```text
不把 R3 的 2~3 ticks 当作最终稳定参数；
不继续扩大 fixed ticks 网格；
不直接进入 Optuna / Bayesian search；
不为了提升收益立即调整 POC / VA 参数；
不把 15m 直接替换为主交易周期。
```

## 9. 实验线 D：尾部风险与成本压力测试

### 9.1 要回答的问题

```text
价值区重新接受的收益是否会被少数 stop_loss / force_flat / 滑点异常吞噬？
```

### 9.2 必看指标

| 指标              | 目的                               |
| --------------- | -------------------------------- |
| 最大单笔亏损          | 判断是否存在超预算左尾                      |
| 最大连续亏损          | 判断账户生存能力                         |
| 最差亏损簇           | 判断亏损是否集中出现                       |
| 最大单笔亏损 / 平均账户盈利 | 判断一次亏损回吐多少笔平均盈利                  |
| 成本 / 平均账户盈利     | 判断小盈利是否被成本吞噬                     |
| 成本 / 单次账户风险     | 判断成本是否过高                         |
| 滑点上升后期望变化       | 判断安全边际                           |
| exit reason 分布  | 判断收益来自 POC、止损、时间退出还是 force\_flat |
| MAE / MFE       | 判断止损和目标是否合理                      |

### 9.3 压力场景

至少检查：

```text
基准滑点；
滑点上升；
手续费不变但平均盈利下降；
force_flat 保守处理；
actual stop 放宽但同步降仓；
低交易机会窗口。
```

## 10. 实验线 E：成交量冲击质量标签

### 10.1 定位

成交量冲击不作为独立入口，只作为价值区重新接受的质量标签候选。

### 10.2 要回答的问题

```text
成交量冲击是否提高 POC 兑现概率？
是否降低 stop_loss / force_flat 左尾？
是否改善接受 / 拒绝质量？
是否只是减少样本后造成的偶然改善？
```

### 10.3 对照方式

对同一批 `value_area_reacceptance` 事件做分桶：

```text
无成交量冲击；
边界突破阶段有成交量冲击；
重新接受阶段有成交量冲击；
突破和重新接受阶段均有成交量冲击。
```

观察不同分桶的：

```text
胜率；
POC hit rate；
price_raw_rr；
account_raw_rr；
左尾；
成本后期望；
交易数。
```

## 11. 阶段决策标准

### 11.1 进入下一阶段的条件

若满足以下条件，可以进入下一阶段策略实现 / 参数平台验证：

```text
1. 至少部分品种能稳定满足 2%~3% 单次账户风险预算；
2. POC / value area 定义足以解释“共识价格区间”，而不是只依赖粗糙 close-profile；
3. tick 敏感性可以被 POC 空间、VA 宽度、波动尺度或内部分位解释；
4. 到 POC 或 POC band 的盈利空间足以支撑价格原始盈亏比和账户原始盈亏比；
5. stop_loss / force_flat 左尾没有吞噬长期期望；
6. 成本和滑点压力测试后仍有安全边际；
7. 品种差异可以被结构变量解释，而不是完全依赖品种专属调参。
```

### 11.2 降级或暂停条件

若出现以下情况，应暂停或降级：

```text
1. 最小手数下无法控制 2%~3% 单次账户风险；
2. POC / value area 定义无法解释为共识价格区间，只是参数化成交密集区；
3. POC 空间不足，导致 price_raw_rr 长期偏低；
4. tick 敏感性无法被 VA 宽度、波动尺度、内部分位或 POC 稳定性解释；
5. 重新接受深度只在单品种、单参数有效；
6. 左尾主要来自无法控制的 force_flat、跳空或滑点；
7. 成本 / 平均盈利过高，小盈利被成本吞噬；
8. 胜率提升需要牺牲过多盈亏比；
9. 成交量冲击过滤只是降低样本后的偶然改善；
10. 收益无法解释为价值区接受 / 拒绝、POC 空间、风险预算或状态差异。
```

## 12. 阶段产出

本阶段结束时至少应产出：

```text
1. value_area_reacceptance 风险预算诊断表；
2. DCE.m / CZCE.SR 品种适配对照；
3. reaccept 深度、POC 与价值区定义诊断摘要；
4. 尾部风险与成本压力测试摘要；
5. 成交量冲击质量标签分桶结果；
6. 是否进入下一阶段的阶段决策。
```

若阶段结论稳定，再压缩归档到：

```text
docs/research/archived-notes/<YYYY-MM-DD>-value-area-reacceptance-risk-budget/
```

## 13. 当前下一步

当前已完成：

```text
R1 账户风险预算预筛；
R2 品种适配诊断；
R3 fixed ticks 邻域；
R4 交易周期敏感性；
R5 POC / VA 定性字段诊断；
R6 POC / VA 形态分桶诊断；
R7 DCE.m2601 关键样本 K 线路径复盘；
R8 close-profile / range-profile / POC band 定义对照；
R9 POC 质量标签分桶诊断；
R10 VA width 归一化 reaccept 深度尝试；
R11 POC 质量标签诊断 payload 最小实现；
R12 基于 diagnostics_json 的 POC 标签分桶复验；
R13 POC 质量组合标签诊断；
R14 日级去重组合标签验证；
R15 edge_or_away 候选过滤器影子评估。
```

当前 C 线结论：

```text
POC / VA 的核心价值不是提供更远目标，
而是确认旧 VA 边界被快速拒绝后，
entry 到 POC / POC band 存在适中、可兑现的回归空间。

close-profile POC 当前仍有解释力，
不能被 range-profile 直接替代；
但单点 POC 无法处理多峰，
naive 全局 POC band 容易产生假阳性。

当前最有解释力的 POC 质量标签是：
POC edge distance 与 current-day acceptance migration。
local band、multi-modal 和 close-vs-range divergence 暂时更适合作为警示/诊断标签。

POC 靠边、target_to_va 过大、当前日接受区迁移、
或 VAH / VAL 只表现为历史密集区边缘时，
2~3 ticks 的重新接受确认无法修复结构问题。

VA width 归一化也不能修复这些结构问题：
它能生成接近 fixed ticks 的样本数量，
但会在较宽 VA 日期延迟入场、压缩 POC 回归空间；
本轮不支持用 `min_reaccept_va_width_ratio` 直接替代 `min_reaccept_ticks`。

POC 质量标签已进入诊断 payload / clearing 统计链路，
R12 已直接基于 `trade_clearings.diagnostics_json` 复现 R9 核心结论：
POC edge = edge 与 current acceptance migration = away 是明显风险桶。
R13 进一步显示，排除 edge_or_away 后收益、胜率和左尾都明显改善。
R14 日级去重后确认 edge_or_away 仍显著负向，
不是 2/3 ticks 重复结构造成的假象。
R15 已把 edge_or_away 作为 would_filter 影子标签写入运行时 diagnostics，
影子过滤在 raw / 日级去重 / 日级平均 PnL 口径下均稳定改善结果。
但 central / near_poc / not_bad / shadow_kept 仍不是充分条件，尤其不能自动修复 SHFE.rb2601 的品种左尾。
```

下一步仍在修正后的实验线 C 内：

```text
扩大样本做影子过滤复验，
暂不改变交易信号。
```

优先目标不是继续跑参数，而是确认 edge_or_away 影子过滤是否跨样本稳定：

```text
1. 保留现有交易信号和参数；
2. 选择更多合约或更长历史区间；
3. 继续写入 would_filter=edge_or_away；
4. 报告 raw / shadow_kept / shadow_filtered 三组结果；
5. 分品种判断 DCE.m 是否适合进入候选策略，SR / rb 是否应降级或排除；
6. 在更大样本稳定前，不把 would_filter 变成真实 entry filter。
```

执行约束：

```text
不急于调参；
不继续扩大 fixed ticks 或 VA width ratio 网格；
不进入 Optuna / Bayesian search；
不把 2~3 ticks 当最终参数；
不直接把 15m 替换为交易周期；
先把 tick 敏感性视为重要研究知识，而不是参数优化目标。
```
