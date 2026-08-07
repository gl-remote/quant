# Stage 5 待办清单：H_only confirmed 的前瞻指标（成交量 / OI / 跳空）

## 元信息

- 主题：atr-timeframe-ratio
- 阶段：Stage 5 · 前瞻指标筛选
- 日期：2026-08-07
- 前置：
  - [Stage 3 结果解读](./stage3-results.md)：H_only confirmed 是唯一有显著性的方向模式
  - [Stage 4 结果解读](./stage4-results.md)：trend_strength=strong 可二次过滤，但 confirmed 仍需等 5 根才能判定
- 核心瓶颈：**confirmed/failed 只能在 t+5 事后标注，t 时刻无法预知**。本阶段寻找 t 时刻可观察的成交量、持仓量、跳空指标，用于在 H_only 出现时预测确认概率和后续收益。
- 脚本目标：`scripts/stage5_leading_indicators.py`
- 输出目录：`outputs/stage5/`

## 1. 研究问题

1. H_only 出现时，成交量、OI、跳空的哪些特征能区分 confirmed 与 failed？
2. 这些前瞻指标能否在 t 时刻提升确认概率的预测力？
3. 加入前瞻指标后，H_only + trend_strength=strong + 前瞻过滤的组合能否进一步提升收益和盈亏比？
4. 前瞻指标在超卖反弹和趋势延续两种机制下是否有不同表现？

## 2. 需要验证的假设

### H1：成交量水平

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H1.1 | H_only 出现时成交量放大（相对近期均值）→ confirmed 概率更高 | vol_ratio 在 confirmed vs failed 组的均值差异、AUC |
| H1.2 | 成交量放大的 H_only 后续 fwd_ret_20 更高 | 按 vol_ratio 三分位分组看 fwd_ret_20 |
| H1.3 | 成交量萎缩的 H_only 更容易 failed | vol_ratio 低组 confirmed 率 vs 高组 |
| H1.4 | 成交量趋势（过去 5 根持续放大）比单根成交量更有预测力 | vol_slope_5 分组对比 |

### H2：成交量变化方向

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H2.1 | H_only 当根成交量 > 前 5 根均值 → 确认概率高 | 二分组 confirmed 率对比 |
| H2.2 | 成交量与价格方向配合（量价齐升/量价齐跌）→ 确认更可靠 | 按 sign(ret_1) × sign(vol_chg) 四象限拆分 |
| H2.3 | 下降趋势中放量 + H_only → 恐慌释放后反弹（超卖反弹机制） | downtrend + high vol 组的 fwd_ret_20 |

### H3：持仓量（OI）水平与变化

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H3.1 | H_only 出现时 OI 处于高位 → 趋势延续概率更高 | OI_pct 分组 confirmed 率和 fwd_ret |
| H3.2 | OI 上升（新资金入场）→ confirmed 概率更高 | dLogOI_5 / dLogOI_20 分组对比 |
| H3.3 | OI 下降（平仓/止损）→ 超卖反弹机制，短期反弹更强 | downtrend + OI 下降组的 fwd_ret_20 |
| H3.4 | OI 变化方向比 OI 水平更有预测力 | dLogOI 与 OI_pct 的 AUC 对比 |

### H4：量价 OI 组合

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H4.1 | 成交量上升 + OI 上升 = 新资金推动趋势 → confirmed 且趋势延续 | 四象限（vol↑↓ × OI↑↓）拆分 |
| H4.2 | 成交量上升 + OI 下降 = 老仓位平仓 → 可能是反转/反弹 | 同上，重点看 downtrend 子组 |
| H4.3 | 成交量下降 + OI 上升 = 观望中新开仓 → 信号弱 | confirmed 率和收益应最低 |
| H4.4 | 成交量下降 + OI 下降 = 流动性枯竭 → squeeze 前兆但方向不明 | 作为对照 |

### H5：跳空

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H5.1 | H_only 当根伴随跳空（开盘价偏离前收）→ confirmed 概率更高 | gap_atr 分组 confirmed 率 |
| H5.2 | 跳空方向与高周期 ATR 扩张方向一致 → 确认更可靠 | sign(gap) × sign(MADEV_60) 分组 |
| H5.3 | 下降趋势中向下跳空 + H_only → 恐慌跳空后反弹（超卖反弹） | downtrend + gap_down 组 fwd_ret_20 |
| H5.4 | 跳空回补（当根收盘回补缺口）→ failed 概率高 | gap_filled 标志位分组 |

### H6：前瞻指标的预测力

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H6.1 | 成交量/OI/跳空指标组合能在 t 时刻预测 confirmed（AUC > 0.6） | 单变量和多变量 logistic regression / AUC |
| H6.2 | 前瞻指标在 trend_strength=strong 子组中预测力更强 | 分层 AUC |
| H6.3 | 前瞻指标对 fwd_ret_20 的预测独立于 confirmed 状态 | 控制 confirmed 后前瞻指标仍有增量 |
| H6.4 | 最优前瞻组合能将 H_only 样本筛选为高确认率子组（>35%）且 fwd_ret_20 显著为正 | 组合过滤后 confirmed 率和收益 |

### H7：稳健性

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H7.1 | 前瞻指标效应在板块间方向一致 | 按板块分组重复 H1–H5 |
| H7.2 | 前瞻指标效应在年份间稳定 | 按年份分组 |
| H7.3 | 结论不被单一合约主导 | LOPO |
| H7.4 | 非重叠抽样下结论不变 | 按合约日聚合 / 只取状态首次出现 |
| H7.5 | 含简单成本后最优组合仍有正期望 | 扣除固定双边成本后的净收益 |

## 3. 需要提取的数据字段

### 3.1 t 时刻已知的成交量字段（来自 1h CSV）

| 字段 | 定义 | 用途 |
|---|---|---|
| `volume` | 当根 1h 成交量 | 基础 |
| `vol_ma_5` | 过去 5 根成交量均值 | 短期参照 |
| `vol_ma_20` | 过去 20 根成交量均值 | 长期参照 |
| `vol_ratio` | `volume / vol_ma_20` | 相对放量倍数 |
| `vol_ratio_5` | `volume / vol_ma_5` | 短期放量倍数 |
| `vol_pct_100` | volume 在过去 100 根的滚动分位 | 异常放量检测 |
| `vol_z_100` | volume 的滚动 z-score | 标准化放量 |
| `vol_chg_1` | `volume / volume.shift(1) - 1` | 单根变化 |
| `vol_chg_5` | `volume / volume.shift(5) - 1` | 5 根变化 |
| `vol_slope_5` | 过去 5 根成交量线性回归斜率 / vol_ma_5 | 成交量趋势方向 |
| `vol_std_20` | 过去 20 根成交量标准差 | 波动稳定性 |
| `amount` | 当根成交额（如有） | 辅助验证 |

### 3.2 t 时刻已知的 OI 字段（来自 1h CSV 的 open_oi / close_oi）

| 字段 | 定义 | 用途 |
|---|---|---|
| `oi` | 当根 close_oi（用收盘持仓量） | 基础 |
| `oi_open` | 当根 open_oi | 开盘持仓 |
| `oi_chg_bar` | `close_oi - open_oi` | 当根内 OI 变化 |
| `oi_ma_20` | 过去 20 根 OI 均值 | 参照 |
| `oi_ma_60` | 过去 60 根 OI 均值 | 长期参照 |
| `oi_pct_100` | OI 在过去 100 根的滚动分位 | OI 相对高低 |
| `oi_z_100` | OI 的滚动 z-score | 异常 OI |
| `dLogOI_5` | `log(oi_t / oi_{t-5})` | 5 根 OI 变化 |
| `dLogOI_20` | `log(oi_t / oi_{t-20})` | 20 根 OI 变化 |
| `oi_slope_5` | 过去 5 根 OI 线性回归斜率 / oi_ma_20 | OI 趋势 |
| `oi_norm` | `oi / oi_ma_60` | 跨期可比的相对 OI |

注意：部分合约 CSV 的 `open_oi` / `close_oi` 可能为空，需要统计覆盖率；缺失时不计算 OI 因子，并在样本量中标注。

### 3.3 t 时刻已知的跳空字段

| 字段 | 定义 | 用途 |
|---|---|---|
| `gap` | `open_t / close_{t-1} - 1` | 当根跳空（含夜盘/日盘切换） |
| `gap_abs` | `abs(gap)` | 跳空幅度 |
| `gap_atr` | `gap_abs / H_t` | 跳空相对 ATR 的倍数 |
| `gap_direction` | sign(gap)：up / down / flat | 跳空方向 |
| `gap_filled` | 当根 low ≤ prev_close ≤ high（bool） | 跳空是否在当根回补 |
| `gap_overnight` | 若当前 bar 是日盘第一根或夜盘第一根，gap 为隔夜/隔午休跳空；否则为盘中连续 | 区分跳空类型 |
| `gap_prev_day` | 今日 open / 昨日日盘收盘 - 1（日级别跳空） | 日级别跳空 |
| `gap_session` | 夜盘开盘 vs 前日日盘收盘 | 夜盘跳空 |

跳空计算需要考虑交易时段：
- 1h bar 的 09:00 / 21:00 等开盘根的 gap 才有意义；
- 盘中连续 bar 的 gap 应接近 0，不作为跳空信号；
- 需要用合约交易时段表或简单规则（当前 bar 与前一根时间差 > 2 小时）判断是否为 session 开盘。

### 3.4 量价 OI 组合字段

| 字段 | 定义 | 用途 |
|---|---|---|
| `vol_oi_state` | vol_ratio 高/低 × dLogOI_5 正/负 四象限 | H4 |
| `vol_price_state` | sign(ret_1) × sign(vol_chg_1) 四象限 | H2.2 |
| `capitulation` | downtrend + vol_ratio 高 + dLogOI_5 < 0（恐慌平仓） | 超卖反弹机制 |
| `new_money` | vol_ratio 高 + dLogOI_5 > 0（新资金入场） | 趋势延续机制 |
| `gap_vol_combo` | gap_atr 高 + vol_ratio 高（跳空放量） | H5 |

### 3.5 前置和响应字段（复用 Stage 3/4）

直接从 Stage 3 面板读取：

- 状态：`state_S`、`H_only_outcome`、`state_duration`、`prev_state`
- 趋势：`MADEV_20`、`MADEV_60`、`trend_strength`、`trend_group`、`ret_20`、`ret_60`
- ATR：`S_H`、`S_L`、`H_pct`、`L_pct`、`dLogH_5`、`dLogL_5`
- 响应：`fwd_ret_5/20/100`、`fwd_abs_ret_5/20/100`、`fwd_max_ret_20`、`fwd_min_ret_20`、`fwd_S_L_up_5`
- 标识：`symbol`、`sector`、`date`、`year`

## 4. 输出表清单

| 输出文件 | 内容 | 对应假设 |
|---|---|---|
| `stage5_oi_coverage.csv` | 各合约 OI 字段覆盖率 | 数据质量 |
| `stage5_univariate_auc.csv` | 每个前瞻指标单独预测 confirmed 的 AUC、均值差异 | H1–H5 |
| `stage5_vol_groups.csv` | vol_ratio 三分位 × outcome 的 confirmed 率和 fwd_ret | H1 |
| `stage5_oi_groups.csv` | dLogOI_5 / OI_pct 三分位 × outcome | H3 |
| `stage5_vol_oi_quadrant.csv` | vol × OI 四象限 confirmed 率和收益 | H4 |
| `stage5_gap_groups.csv` | gap_atr 分组 × outcome | H5 |
| `stage5_gap_direction.csv` | gap 方向 × 趋势方向 × outcome | H5.2, H5.3 |
| `stage5_multivariate.csv` | 多变量 logistic regression 系数、AUC、CV | H6 |
| `stage5_combo_filter.csv` | 最优前瞻组合过滤后的 confirmed 率和 fwd_ret | H6.4 |
| `stage5_trend_interaction.csv` | 前瞻指标 × trend_strength × MADEV_60 方向 | H6.2, 机制拆分 |
| `stage5_by_sector.csv` | 按板块拆分核心结果 | H7.1 |
| `stage5_by_year.csv` | 按年份拆分核心结果 | H7.2 |
| `stage5_lopo.csv` | LOPO 稳健性 | H7.3 |
| `stage5_nonoverlap.csv` | 非重叠抽样结果 | H7.4 |
| `stage5_cost_sensitivity.csv` | 不同成本水平下最优组合净收益 | H7.5 |

## 5. 统计方法要求

- **单变量筛选**：
  - 连续变量报告 confirmed vs failed 组均值差、Mann-Whitney U p 值、AUC；
  - 分类变量报告 confirmed 率差异和卡方/Fisher 检验；
- **多变量模型**：
  - 用 logistic regression（L1 正则）预测 confirmed，5-fold 交叉验证 AUC；
  - 同时报告系数方向和显著性；
  - 为避免过拟合，候选指标不超过 10 个，样本量 confirmed ≥ 200；
- **收益分析**：
  - 所有均值报告 95% bootstrap CI，按 symbol-date 聚类；
  - 同时报告 event 数和独立日数；
  - n < 30 标注样本不足；
- **非重叠抽样**：
  - 方案 A：每个 H_only 连续段只取第一根；
  - 方案 B：按合约日聚合（同一交易日多个 H_only 只取最早一个）；
- **成本敏感性**：
  - 双边成本取 0bp、1bp、2bp、3bp 四档；
  - fwd_ret_20 假设入场为 t+1 open、出场为 t+20 close；
  - 报告扣成本后均值、CI、胜率；
- **不在本阶段调参**：三分位、阈值、视野长度均沿用 Stage 3/4。

## 6. 执行顺序

1. 数据准备：
   - 从 1h CSV 重新加载 volume、open_oi、close_oi；
   - 合并到 Stage 3 面板；
   - 统计 OI 覆盖率，剔除 OI 缺失率 > 50% 的合约；
   - 识别 session 开盘根，计算跳空字段；
2. 描述性统计：
   - H_only 子样本中各前瞻指标的分布；
   - confirmed vs failed 单变量对比和 AUC；
3. 成交量假设（H1–H2）；
4. OI 假设（H3）；
5. 量×OI 四象限（H4）；
6. 跳空假设（H5）；
7. 多变量模型和最优组合（H6）；
8. 与 trend_strength / MADEV_60 方向的交互（机制拆分：超卖反弹 vs 趋势延续）；
9. 稳健性：板块、年份、LOPO、非重叠、成本（H7）；
10. 汇总为 stage5-results.md。

## 7. 预期产出与判断标准

本阶段结束后，需要能回答：

1. 是否存在 t 时刻可用的前瞻指标，将 H_only confirmed 预测 AUC 提升到 0.6 以上？
2. 最优前瞻组合是什么？组合后的 confirmed 率、fwd_ret_20、盈亏比、样本量分别是多少？
3. 前瞻指标的作用机制更偏向"超卖反弹"还是"趋势延续"？还是两者都有？
4. 扣 2bp 成本后，最优组合是否仍有正期望？
5. 结论在板块、年份、LOPO、非重叠抽样下是否稳定？

若上述问题多数为"是"，可以进入 Stage 6 构建可交易信号原型；若多数为"否"，则 H_only confirmed 应降级为事后解释变量，不作为交易信号基础。
