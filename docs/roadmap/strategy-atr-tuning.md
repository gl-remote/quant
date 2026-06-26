# ATR 策略稳健正期望 Roadmap

> 类型：Roadmap / 待实现调优方案  
> 状态：P1 初版已实现，工具链已补齐，待扩大样本验证  
> 创建日期：2026-06-26  
> 开发分支：feat/atr-strategy-tuning  
> 开分支 hash：88d2563  
> 实现提交 hash：待提交  
> 策略代码：[atr_strategy.py](../../workspace/strategies/atr_strategy.py)  
> 目标：不追求单次回测暴利，优先获得较稳定、可迁移、长期正期望的 CTA 策略。

## 0. 核心结论

**有搞头，但方向要收敛。**

ATR 本身不是 alpha，它只解决“亏多少、赚了怎么拿住、仓位怎么按波动归一”的问题；真正决定长期正期望的是：

1. 只在有大级别趋势背景时交易；
2. 不追 DMI/ADX 瞬时强势，尽量等回调或再启动；
3. 单笔风险固定，靠亏小赚大和多品种分散获得期望；
4. 用 Walk-Forward 和多品种验证过滤过拟合参数。

当前 [atr_strategy.py](../../strategies/atr_strategy.py) 是一个不错的起点，因为它已经有 ATR 止损、ATR 止盈、移动止盈和冷却机制。但当前入场仍是“5m SMA 趋势 + 1m/5m MACD + 1m/5m KDJ”的 5-AND 结构，问题是：

- 信号可能过少；
- KDJ 超买/超卖与趋势跟随天然冲突；
- 1m 信号噪声大；
- 固定仓位不利于跨品种和跨波动环境；
- DMI/ADX 如果作为追单主信号，容易在趋势尾段进场。

因此，后续不把 DMI 当主方向，只把 ADX/DMI 放在“过滤和降权”位置。

---

## 1. 当前策略诊断

### 1.1 已有实现

当前策略文件：[atr_strategy.py](../../strategies/atr_strategy.py)

`ATRCrossParams` 当前参数包含：

| 参数组 | 参数 | 当前默认 | 说明 |
|--------|------|----------|------|
| 趋势 | `sma_short` / `sma_long` | 10 / 40 | 5m SMA 趋势判断 |
| 固定风控 | `stop_loss_ratio` / `take_profit_ratio` | 0.03 / 0.05 | 固定比例兜底止损止盈 |
| 仓位 | `position_ratio` | 0.1 | 固定资金比例仓位 |
| ATR 风控 | `atr_period` | 14 | ATR 计算周期 |
| ATR 风控 | `atr_stop_loss_multiplier` | 2.0 | ATR 止损倍数 |
| ATR 风控 | `atr_take_profit_multiplier` | 3.0 | ATR 止盈倍数 |
| 移动止盈 | `trailing_activation_atr` | 1.0 | 移动止盈激活 ATR 倍数 |
| 移动止盈 | `trailing_drawdown_ratio` | 0.25 | 激活后回撤止盈比例 |
| KDJ | `kdj_oversold` / `kdj_overbought` | 20 / 80 | 入场过滤阈值 |

### 1.2 当前入场结构

当前做多条件：

```python
@confirm_long("macd@1m > 0")
@confirm_long("macd@5m > 0")
@confirm_long("kdj@1m < {kdj_oversold}")
@confirm_long("kdj@5m < {kdj_oversold}")
@trend_long("sma({sma_short})@5m > sma({sma_long})@5m")
```

当前做空条件：

```python
@confirm_short("macd@1m < 0")
@confirm_short("macd@5m < 0")
@confirm_short("kdj@1m > {kdj_overbought}")
@confirm_short("kdj@5m > {kdj_overbought}")
@trend_short("sma({sma_short})@5m < sma({sma_long})@5m")
```

### 1.3 核心问题

| 问题 | 判断 |
|------|------|
| ATR 是否能带来 alpha | 不能。ATR 主要用于风控和仓位，不直接产生方向优势 |
| 当前 5-AND 是否稳健 | 不一定。条件过多会减少交易样本，也容易把结果调成偶然 |
| KDJ 超卖/超买是否适合趋势跟随 | 只适合做“回调入场”，不适合和强动量追涨同时强绑定 |
| 1m 指标是否适合做主信号 | 不适合。1m 噪声和滑点影响太大，更适合做触发，不适合做方向 |
| DMI/ADX 是否适合追 | 不建议。ADX/DMI 高时常常已经走出一段，追进去容易吃回撤 |

---

## 2. 稳健正期望的策略框架

推荐从“追强势”改成“趋势背景下的回调/再启动”。

### 2.1 三层结构

| 层级 | 作用 | 推荐指标 | 说明 |
|------|------|----------|------|
| 大级别背景 | 决定只做多/只做空/不交易 | 15m 或 30m 均线、MACD | 慢，不频繁翻向 |
| 入场触发 | 在背景方向内找相对低风险位置 | 5m KDJ/RSI 回调、5m MACD 回正 | 不追尖峰 |
| 风控与仓位 | 控制亏损和盈亏比 | ATR 止损、移动止盈、ATR 仓位 | 稳定长期期望 |

### 2.2 建议的 v1 方向逻辑

不先引入 DMI，先用当前已有指标做低复杂度版本。

做多：

```python
@trend_long("sma({sma_short})@15m > sma({sma_long})@15m")
@confirm_long("macd@5m > 0")
@confirm_long("kdj@5m < {kdj_pullback_long}")
```

做空：

```python
@trend_short("sma({sma_short})@15m < sma({sma_long})@15m")
@confirm_short("macd@5m < 0")
@confirm_short("kdj@5m > {kdj_pullback_short}")
```

解释：

- 15m SMA 只判断背景方向；
- 5m MACD 负责确认短周期动量重新回到趋势方向；
- 5m KDJ 不是追涨杀跌，而是要求价格刚经历过回调；
- 暂时去掉 1m 条件，减少噪声和过拟合。

### 2.3 DMI/ADX 的定位

你的判断是对的：**追 DMI 风险太大，只能辅助使用。**

建议只做三类辅助：

1. **低 ADX 禁入**：ADX 太低说明无趋势，减少震荡亏损；
2. **极端 ADX 降权或禁入**：ADX 太高可能是趋势末段，不追；
3. **DMI 只确认方向一致**：例如 `+DI > -DI` 才允许做多，但不能因为 `+DI` 快速上穿就直接追多。

如果后续实现 DMI/ADX，推荐范围：

| 用法 | 建议 | 不建议 |
|------|------|--------|
| ADX 过滤 | `adx_min <= ADX <= adx_max` | `ADX 越高越买` |
| DMI 方向 | 多头背景下要求 `+DI > -DI` | `+DI 上穿 -DI 直接追多` |
| 风险控制 | ADX 过高时减仓或等待回调 | 高 ADX 满仓追入 |

建议默认：

```text
adx_min = 18 ~ 22
adx_max = 35 ~ 45
```

也就是说：低于 `adx_min` 不做，高于 `adx_max` 不追。

---

## 3. 参数体系调整

### 3.1 当前参数保留与调整

| 参数 | 建议 | 理由 |
|------|------|------|
| `sma_short` | 保留，默认 20 | 作为 15m 背景短均线，不追太快 |
| `sma_long` | 保留，默认 60 | 作为 15m 背景长均线 |
| `atr_period` | 保留，默认 14 或 20 | 波动估计不用频繁优化 |
| `atr_stop_loss_multiplier` | 保留，默认 2.0 ~ 2.5 | 给趋势回调留空间 |
| `atr_take_profit_multiplier` | 保留，默认 3.0 ~ 5.0 | 保持盈亏比大于 1 |
| `trailing_activation_atr` | 保留，默认 2.0 | 太早激活容易被洗出 |
| `trailing_drawdown_ratio` | 保留，默认 0.25 ~ 0.35 | 趋势策略要容忍回撤 |
| `position_ratio` | 短期保留，长期替换 | 当前实现只有固定仓位 |
| `kdj_oversold` / `kdj_overbought` | 重命名或语义调整 | 从“极端超买超卖”改成“回调阈值” |

### 3.2 建议新增参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `kdj_pullback_long` | 45 | 多头背景下，KDJ 低于该值视为回调过 |
| `kdj_pullback_short` | 55 | 空头背景下，KDJ 高于该值视为反弹过 |
| `time_stop_bars` | 60 | 入场后长时间不盈利则退出 |
| `target_risk` | 0.005 ~ 0.01 | ATR 仓位模式下单笔账户风险 |
| `adx_min` | 20 | 后续可选：低于该值不交易 |
| `adx_max` | 40 | 后续可选：高于该值不追 |

### 3.3 搜索空间原则

不要把搜索空间开太大。稳定正期望优先看“参数平台”，不是单点最优。

| 参数 | 建议搜索范围 |
|------|--------------|
| `sma_short` | 15 ~ 30 |
| `sma_long` | 50 ~ 100 |
| `kdj_pullback_long` | 35 ~ 55 |
| `kdj_pullback_short` | 45 ~ 65 |
| `atr_stop_loss_multiplier` | 1.8 ~ 3.2 |
| `atr_take_profit_multiplier` | 3.0 ~ 6.0 |
| `trailing_activation_atr` | 1.5 ~ 3.0 |
| `trailing_drawdown_ratio` | 0.20 ~ 0.40 |
| `target_risk` | 0.005 ~ 0.01 |

---

## 4. 实施路线

### 4.0 当前实测记录（2026-06-26）

已用现有工具链执行两轮小样本验证，数据范围为本地 `DCE.m2601/m2603/m2605`，回测周期 `5m`，成本配置为手续费率 `0.0003`、滑点 `1 tick`。

#### Baseline：当前 5-AND 结构

命令：

```bash
./run.sh backtest --env backtest --pattern "DCE\\.m.*" --strategy atr --mode search --optimizer bayesian --trials 5 --early-stop-patience 0 --capital 100000 --contract-size 10 --no-search
```

结果：

| 合约 | 交易数 | 总收益 | 最大回撤 | 备注 |
|------|--------|--------|----------|------|
| `DCE.m2601` | 1 | 12.52% | -0.36% | 样本不足 |
| `DCE.m2603` | 1 | 7.62% | -2.25% | 样本不足 |
| `DCE.m2605` | 1 | 13.89% | 0.00% | 样本不足 |

结论：结果看起来为正，但每个合约只有 1 笔交易，不能作为策略有效性证据；只能说明当前 5-AND 入场过严，必须先提高样本量。

#### P1 初版：15m 趋势 + 5m 回调/再启动

已实现：

```python
@trend_long("sma({sma_short})@15m > sma({sma_long})@15m")
@confirm_long("macd@5m > 0")
@confirm_long("kdj@5m < {kdj_pullback_long}")

@trend_short("sma({sma_short})@15m < sma({sma_long})@15m")
@confirm_short("macd@5m < 0")
@confirm_short("kdj@5m > {kdj_pullback_short}")
```

P1 初版默认参数：

| 参数 | 当前值 |
|------|--------|
| `sma_short` | 20 |
| `sma_long` | 60 |
| `kdj_pullback_long` | 45 |
| `kdj_pullback_short` | 55 |
| `atr_stop_loss_multiplier` | 2.5 |
| `atr_take_profit_multiplier` | 4.0 |
| `trailing_activation_atr` | 2.0 |
| `trailing_drawdown_ratio` | 0.3 |

P1 初跑结果：

| 合约 | 交易数 | 总收益 | 最大回撤 | 备注 |
|------|--------|--------|----------|------|
| `DCE.m2601` | 1 | 4.70% | -1.74% | 样本不足 |
| `DCE.m2603` | 1 | 8.10% | 0.00% | 样本不足 |
| `DCE.m2605` | 1 | -7.89% | -7.89% | 样本不足 |

结论：P1 结构方向正确，但在当前本地豆粕短窗口上仍不足以形成统计样本。下一轮不应继续优化 ATR 参数，而应先解决样本量和工具链问题。

#### 工具链修复与并行小样本验证

已补齐：

1. `run.sh` 运行时自动把 `workspace/` 加入 `PYTHONPATH`；
2. `backtest-atr.sh` 默认传入 `--env backtest`；
3. `DataManager` 在缺少 `ExportMetadata` 时，可从本地 CSV 自动反向补齐元数据；
4. 并行优化 worker 初始化时继承数据环境，`DataFeed.create()` 可在子进程内正常使用 `DataManager()`。

并行验证命令：

```bash
./run.sh backtest --env backtest --pattern "DCE\\.m.*" --strategy atr --mode search --optimizer bayesian --parallel --workers 2 --trials 3 --early-stop-patience 0 --capital 100000 --contract-size 10
```

结果：run `r6` 成功完成，`3 trials × 3 合约` 全部跑通，报告已生成；最佳参数为：

| 参数 | 值 |
|------|----|
| `atr_stop_loss_multiplier` | 1.8 |
| `atr_take_profit_multiplier` | 3.0 |
| `trailing_activation_atr` | 2.1 |
| `trailing_drawdown_ratio` | 0.35 |
| `kdj_pullback_long` | 40 |
| `kdj_pullback_short` | 60 |

run `r6` 最佳 trial 对应结果：

| 合约 | 交易数 | 总收益 | 最大回撤 | 备注 |
|------|--------|--------|----------|------|
| `DCE.m2601` | 1 | 4.70% | -1.74% | 样本不足 |
| `DCE.m2603` | 1 | 8.10% | 0.00% | 样本不足 |
| `DCE.m2605` | 1 | -4.39% | -4.39% | 样本不足 |

结论：当前工具链已经能执行 ATR 并行参数搜索，但搜索结果仍不可用于策略判断。每个合约仍只有 1 笔交易，`3 trials` 仅用于验证流程可用，不用于选择生产参数。

数据一致性修复（2026-06-26）：

1. 逐笔 `commission` 已改为每条成交按 `price × volume × size × rate` 记录，不再只集中到平仓记录；
2. `profit_days + loss_days` 校验已改为“不超过 total_days”，允许无交易日存在；
3. 最小 ATR 并行回测 run `r3` 生成回测 ID `145/146/147` 后，`DataManager.validate_consistency()` 均返回空错误。

下一轮优先级：

1. 扩大验证样本到更多品种或更长历史窗口；
2. 在交易数足够后，再进入参数搜索和 Walk-Forward；
3. 暂不根据当前豆粕短样本调参或引入 DMI/ADX。

### P0 — 建立基线，不引入 DMI

目标：验证当前 ATR 策略有没有基础正期望，并确认交易样本是否足够。

1. 跑当前 `atr` baseline；
2. 记录交易次数、胜率、盈亏比、平均持仓时间、最大回撤、夏普、手续费滑点影响；
3. 检查信号数量，如果交易过少，不先调 ATR 参数，先放松入场结构；
4. 做 0/1/2 tick 滑点压力测试。

验收标准：

- 交易次数足够支撑统计判断；
- 加 2 tick 滑点后结果不能完全崩掉；
- 单笔平均盈利要显著大于交易成本；
- 最优参数不能集中在搜索边界。

### P1 — 改成“慢趋势 + 回调/再启动”

目标：把策略从 1m 噪声确认改为更稳的 15m 背景 + 5m 触发。

建议改动：

1. 趋势周期从 `5m` 改为 `15m`；
2. 移除 `macd@1m`；
3. 移除 `kdj@1m`；
4. KDJ 阈值从 20/80 放宽到 45/55 一带；
5. 移动止盈激活从 1 ATR 提高到 1.5~2 ATR。

预期效果：

- 信号更少受 1m 噪声影响；
- 入场不再追最强瞬间；
- 胜率未必明显提升，但盈亏比和滑点鲁棒性应改善。

### P2 — ATR 仓位和时间止损

目标：提高长期稳定性，而不是提高单次收益率。

1. 加 `time_stop_bars`：入场后 N 根 1m K 线未盈利则退出；
2. 将固定 `position_ratio` 改为 ATR 风险仓位：

```python
volume = account_equity * target_risk / (atr_value * atr_stop_loss_multiplier * contract_size)
```

3. 每笔风险控制在账户 0.5%~1%；
4. 多品种运行时按组合总风险限制同时持仓。

### P3 — DMI/ADX 只做辅助过滤

目标：减少震荡期交易和趋势末端追单。

实现前提：先新增 ADX/DMI 指标能力。

推荐规则：

```text
ADX < adx_min：不交易
ADX > adx_max：不新开仓，只管理已有仓位
做多：+DI > -DI 仅作为确认，不作为触发
做空：-DI > +DI 仅作为确认，不作为触发
```

不要做：

```text
+DI 上穿 -DI 直接买
-DI 上穿 +DI 直接卖
ADX 越高仓位越大
```

### P4 — 多品种验证

长期正期望更依赖组合，而不是单品种神参数。

推荐先用低相关组合：

| 类别 | 品种 |
|------|------|
| 黑色 | 螺纹钢、热卷、铁矿、焦炭 |
| 农产品 | 豆粕、菜粕 |
| 有色/贵金属 | 沪铜、沪金 |

验证重点：

1. 同一套参数能否跨品种不亏；
2. 参数微调后是否仍有平台区；
3. 组合净值是否降低最大回撤；
4. 是否存在某一品种贡献全部收益的问题。

---

## 5. 判断“有搞头”的标准

不要只看最高夏普，重点看以下指标：

| 指标 | 最低要求 |
|------|----------|
| 交易次数 | 每个样本段不能太少，否则统计无意义 |
| Profit Factor | > 1.15，越稳定越好 |
| 平均单笔盈亏 | 明显大于 2 tick 成本 |
| 最大回撤 | 可由仓位缩放控制，而不是来自极端连亏 |
| Walk-Forward | OOS 不崩，WFE 不太低 |
| 参数稳定性 | 附近参数仍为正，不依赖尖峰 |
| 多品种迁移 | 至少不是只在一个品种上有效 |

如果结果是“单品种某组参数很好，换时段/换品种就失效”，那不是策略有搞头，是过拟合。

---

## 6. 暂不做

- 不再继续改 MA 策略；
- 不把 DMI/ADX 当主入场信号；
- 不追求单品种单参数最高收益；
- 不在没有 baseline 前引入过多新指标；
- 不做机器学习模型；
- 不做基本面因子；
- 不改策略 `on_bar` 接口和现有建议型切面 DSL。

---

## 7. 下一步

1. 跑当前 `atr` baseline，确认交易数量和成本敏感性；
2. 如果交易过少，优先改入场为“15m 趋势 + 5m 回调/再启动”；
3. 再调 ATR 止损、止盈、移动止盈；
4. 然后加时间止损和 ATR 仓位；
5. 最后再加 ADX/DMI 辅助过滤。
