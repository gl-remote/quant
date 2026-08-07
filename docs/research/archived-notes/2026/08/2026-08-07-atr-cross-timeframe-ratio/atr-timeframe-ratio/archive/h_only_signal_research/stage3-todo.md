# Stage 3 待办清单：state_S 四象限未来路径检验

## 元信息

- 主题：atr-timeframe-ratio
- 阶段：Stage 3 · 假设检验
- 日期：2026-08-07
- 前置：[Stage 1 分布描述](./stage1-distribution.md) 第 9 节
- 脚本目标：`scripts/stage3_state_paths.py`
- 输出目录：`outputs/stage3/`

## 1. 需要验证的假设

### H1：状态转移矩阵

**来源**：第 9.5 节状态转换路径图。

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H1.1 | co_compress 最可能转向 co_expand 或保持 co_compress | 1 步、3 步、5 步转移概率矩阵 |
| H1.2 | H_only 最可能转向 co_expand（S_L 跟进）或回到 co_compress（S_L 不跟） | H_only → co_expand vs H_only → co_compress 的条件概率 |
| H1.3 | L_only 最可能回到 co_compress（衰减），而非升级为 co_expand | L_only → co_compress vs L_only → co_expand 的条件概率 |
| H1.4 | co_expand 最可能回到 co_compress 或经 L_only 衰减 | co_expand → co_compress 直接转移 vs co_expand → L_only → co_compress |
| H1.5 | "健康路径" compress → H_only → expand 的频率显著高于 compress → L_only → expand | 两条路径的实际出现次数和概率 |

### H2：co_compress（双压缩）后波动扩张

**来源**：第 9.1 节。

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H2.1 | co_compress 后 5–20 根 \|r_future\| 显著高于无条件基准 | 各象限 \|r_5\|、\|r_20\| 均值对比，bootstrap CI |
| H2.2 | co_compress 后 ATR 扩张概率高于其他象限 | 未来 5/20 根 S_H、S_L 上升的比例 |
| H2.3 | 压缩越深（S_H、S_L 越低），后续扩张幅度越大 | 按 S_H×S_L 分位分组，看后续 \|r\| 和 ATR 变化 |
| H2.4 | co_compress 不预测方向 | sign(r_20) 应接近 50/50 |
| H2.5 | 压缩持续越久，后续扩张越大 | 按 co_compress 持续 bar 数分组 |

### H3：co_expand（共振扩张）后的均值回归

**来源**：第 9.2 节。

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H3.1 | co_expand 后短期 \|r\| 仍高，但 20–100 根向均值回归 | \|r_5\|、\|r_20\|、\|r_100\| 时间序列 |
| H3.2 | 进入 co_expand 前趋势强 → 趋势延续；趋势弱或反转后 → 双向波动 | 按进入前 MADEV / 动量分组，看 r_future sign |
| H3.3 | S_diff > 0（高周期扩张更猛）→ R_bar 继续上升，趋势加速 | 按 S_diff 分组看 R_bar 变化和收益 |
| H3.4 | S_diff < 0（低周期扩张更猛）→ 趋势末端，反转概率高 | S_diff < 0 组的 r_20、r_100 |
| H3.5 | D 组累计变化高 + E 组速度转负 → 扩张衰竭 | 按 dLogH_20 高 + vel_sign_H_5 < 0 分组看后续 |

### H4：H_only（高周期独扩）的确认与失败

**来源**：第 9.3 节。**这是最关键的假设。**

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H4.1 | H_only 后 1–5 根内 S_L 抬升概率显著高于无条件 | 条件概率 P(S_L_t+k > 1 \| state_t = H_only) |
| H4.2 | S_L 跟进（→ co_expand）后 20 根收益延续入场方向 | 按确认/失败分组，对比 r_20 |
| H4.3 | S_L 不跟进（→ co_compress）后收益反转或回到震荡 | 失败组 r_20、\|r_20\| |
| H4.4 | H_only 比 co_compress 更有方向含义 | H_only 后 \|r_20\| > co_compress 后 \|r_20\|，且 sign 更集中 |
| H4.5 | H_only + R_bar 高 + dLogL_5 转正 → 最佳趋势启动信号 | 三条件组合的后续收益和胜率 |
| H4.6 | dLogL_5 是 S_L 是否跟进的前瞻指标 | dLogL_5 与未来 3–5 根 S_L 变化的相关性 |

### H5：L_only（低周期独扩）的衰减

**来源**：第 9.4 节。

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H5.1 | L_only 后 5–20 根 \|r\| 偏高但方向随机 | sign(r_20) 接近 50/50，\|r_20\| 高于无条件 |
| H5.2 | L_only 持续超过 5 根不升级为 co_expand → 衰减概率高 | 按持续 bar 数分组，看转移概率 |
| H5.3 | 长期 co_compress 后出现 L_only → 可能是扩张前兆 | 按前置 co_compress 持续时间分组 |
| H5.4 | co_expand 后出现 L_only → 残余波动，趋势结束 | 前置状态为 co_expand 的 L_only 后续路径 |
| H5.5 | L_only 是四象限中方向预测力最弱的 | 各象限 sign(r_20) 的集中度对比 |

### H6：R_bar × state_S 联合分层

**来源**：第 9.6 节。

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H6.1 | R_bar 高 + H_only → 后续收益方向最明确、\|r\| 最大 | 六组联合分层的 r_20、\|r_20\| 对比 |
| H6.2 | R_bar 低 + co_compress → 典型 squeeze，\|r\| 放大但无方向 | 同上 |
| H6.3 | R_bar 低 + L_only → 噪声，\|r\| 低且方向随机 | 同上 |
| H6.4 | R_bar 高 + co_expand → 趋势中段，收益取决于 S_diff | 再按 S_diff 三分位拆分 |
| H6.5 | 控制 state_S 后 R_bar 是否仍有增量 | 同 state_S 内 R_bar 高/低的 r_future 差异 |

### H7：稳健性

| 编号 | 假设 | 验证方法 |
|---|---|---|
| H7.1 | 四象限路径在板块间方向一致（能化/有色/农产品/黑色） | 按板块分组重复 H2–H6 |
| H7.2 | 四象限路径在年份间稳定 | 按年份分组 |
| H7.3 | 结论不被单一合约主导 | LOPO：逐合约排除后结果是否一致 |
| H7.4 | 重叠 bar 不夸大显著性 | 按合约-日期聚类 bootstrap，并报告独立日数 |
| H7.5 | bar 对齐与时钟对齐结论一致 | R_bar 和 R_clock 双口径互验 |

## 2. 需要提取的数据字段

### 2.1 基础标识字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | str | 合约代码，如 DCE.c2601 |
| `exchange` | str | 交易所（从 symbol 解析） |
| `sector` | str | 板块（能化/有色/黑色/农产品/贵金属） |
| `datetime` | datetime | 1h bar 收盘时间 |
| `date` | date | 交易日期（用于聚类） |
| `year` | int | 年份 |
| `session` | str | 日盘/夜盘（按 bar 时间判断） |

### 2.2 当前状态字段（t 时刻）

| 字段 | 来源 | 说明 |
|---|---|---|
| `R_bar` | A 组 | 跨周期比值 |
| `R_bar_pct` | A 组 | R_bar 滚动分位 |
| `R_clock` | A 组 | 时钟对照片值 |
| `H` | B 组 | ATR_1h(14) |
| `L` | B 组 | ATR_15m(56) |
| `H_pct` | B 组 | H 滚动分位 |
| `L_pct` | B 组 | L 滚动分位 |
| `H_norm` | B 组 | H / close |
| `common_vol` | B 组 | sqrt(H_norm × L_norm) |
| `S_H` | C 组 | ATR_1h(14)/ATR_1h(50) |
| `S_L` | C 组 | ATR_15m(56)/ATR_15m(200) |
| `S_diff` | C 组 | S_H_pct - S_L_pct |
| `state_S` | C 组 | co_compress / co_expand / H_only / L_only |
| `state_duration` | C 组 | 当前 state_S 已持续 bar 数 |
| `dLogH_5` | D 组 | 高周期 5 根累计变化 |
| `dLogL_5` | D 组 | 低周期 5 根累计变化 |
| `dLogR_5` | D 组 | 跨周期比值 5 根变化 |
| `dLogH_20` | D 组 | 高周期 20 根累计变化 |
| `dLogL_20` | D 组 | 低周期 20 根累计变化 |
| `dLogR_20` | D 组 | 跨周期比值 20 根变化 |
| `R_rank_chg_5` | F 组 | R_bar 分位 5 期变化 |
| `R_vs_MA20` | F 组 | R_bar 相对 20 期均值偏离 |
| `vel_sign_H_5` | E 组（备选） | 高周期变化速度方向 |
| `vel_sign_L_20` | E 组（备选） | 低周期变化速度方向 |

### 2.3 前置趋势字段（t 时刻已知，用于条件分组）

| 字段 | 定义 | 用途 |
|---|---|---|
| `ret_20` | 过去 20 根 1h 收益 | 判断进入状态前的趋势方向 |
| `ret_60` | 过去 60 根 1h 收益 | 更长周期趋势 |
| `MADEV_20` | close 相对 20 期 MA 的标准化偏离 | 判断价格相对均线位置 |
| `MADEV_60` | close 相对 60 期 MA 的标准化偏离 | 长周期均线偏离 |
| `trend_strength` | abs(MADEV_60) 或 abs(ret_60) 分位 | 区分强趋势/弱趋势 |
| `prev_state` | 前一根 state_S | 判断状态转换方向 |
| `compress_duration` | 进入当前状态前 co_compress 持续 bar 数 | H5.3 用 |

### 2.4 前向响应字段（t+1 到 t+k，禁止用于 t 时刻决策）

| 字段 | 定义 | 用途 |
|---|---|---|
| `fwd_ret_5` | close_{t+5} / close_t - 1 | 5 根方向收益 |
| `fwd_ret_20` | close_{t+20} / close_t - 1 | 20 根方向收益 |
| `fwd_ret_100` | close_{t+100} / close_t - 1 | 100 根方向收益 |
| `fwd_abs_ret_5` | abs(fwd_ret_5) | 5 根波动幅度 |
| `fwd_abs_ret_20` | abs(fwd_ret_20) | 20 根波动幅度 |
| `fwd_abs_ret_100` | abs(fwd_ret_100) | 100 根波动幅度 |
| `fwd_max_ret_20` | max(close_{t+1..t+20}) / close_t - 1 | 20 根内最大有利收益（多） |
| `fwd_min_ret_20` | min(close_{t+1..t+20}) / close_t - 1 | 20 根内最大不利收益 |
| `fwd_H_5` | ATR_1h at t+5 | 高周期 ATR 演化 |
| `fwd_L_5` | ATR_15m at t+5 | 低周期 ATR 演化 |
| `fwd_S_H_5` | S_H at t+5 | 高周期短长比演化 |
| `fwd_S_L_5` | S_L at t+5 | 低周期短长比演化 |
| `fwd_R_bar_5` | R_bar at t+5 | 跨周期比值演化 |
| `fwd_state_1` | state_S at t+1 | 1 步转移 |
| `fwd_state_3` | state_S at t+3 | 3 步转移 |
| `fwd_state_5` | state_S at t+5 | 5 步转移 |
| `fwd_state_20` | state_S at t+20 | 20 步转移 |
| `fwd_S_L_up_3` | S_L_{t+3} > 1（bool） | H_only 确认标志 |
| `fwd_S_L_up_5` | S_L_{t+5} > 1（bool） | H_only 确认标志 |
| `fwd_max_abs_ret_5` | max(abs(ret_{t+1..t+5})) | 5 根内最大单根波动 |
| `fwd_ATR_expand_5` | H_{t+5} > H_t 且 L_{t+5} > L_t | 双周期扩张确认 |

### 2.5 分组标签字段

| 字段 | 定义 |
|---|---|
| `R_bar_tercile` | R_bar 三分位（low/mid/high），每合约内部计算 |
| `S_diff_tercile` | S_diff 三分位 |
| `H_pct_tercile` | H_pct 三分位 |
| `trend_group` | MADEV_60 高/中/低 × sign |
| `state_combo` | R_bar_tercile × state_S（6–12 组） |
| `H_only_outcome` | 仅当 state_S=H_only：confirmed（3–5 根内 S_L>1）/ failed / pending |

## 3. 输出表清单

| 输出文件 | 内容 | 对应假设 |
|---|---|---|
| `stage3_transition_matrix.csv` | 1/3/5/20 步状态转移概率 | H1 |
| `stage3_state_returns.csv` | 各象限 fwd_ret 和 fwd_abs_ret 均值/中位/CI | H2–H5 |
| `stage3_state_duration.csv` | 各象限持续时间分布 | H2.5, H5.2 |
| `stage3_compress_depth.csv` | co_compress 按深度分组的后续 \|r\| | H2.3 |
| `stage3_expand_sdiff.csv` | co_expand 按 S_diff 分组的后续收益 | H3.3, H3.4 |
| `stage3_h_only_outcomes.csv` | H_only 确认/失败比例及后续收益 | H4.1–H4.6 |
| `stage3_l_only_decay.csv` | L_only 按持续时间和前置状态分组 | H5.1–H5.4 |
| `stage3_Rbar_state_combo.csv` | R_bar × state_S 联合分层 | H6 |
| `stage3_rbar_incremental.csv` | 同 state_S 内 R_bar 高/低差异 | H6.5 |
| `stage3_by_sector.csv` | 按板块分组的核心结果 | H7.1 |
| `stage3_by_year.csv` | 按年份分组的核心结果 | H7.2 |
| `stage3_lopo.csv` | LOPO 稳健性 | H7.3 |
| `stage3_path_frequency.csv` | compress→H_only→expand 等路径频率 | H1.5 |

## 4. 统计方法要求

- 所有均值报告 95% bootstrap CI，按 symbol-date 聚类；
- 同时报告 event 数和独立合约日数；
- 分层组 n < 30 时标注"样本不足"，不做结论；
- 方向胜率用二项检验对比 50%；
- LOPO：逐合约排除，检查核心指标（H_only 确认率、co_compress 后 \|r\|）是否稳定；
- 不做多重检验校正以外的调参；所有阈值（三分位、1.0）在 Stage 1 已固定，不在 Stage 3 优化。

## 5. 执行顺序

1. 提取全字段面板（2.1–2.5），保存 parquet；
2. 计算状态转移矩阵（H1）；
3. 各象限基础收益和波动表（H2–H5 主表）；
4. H_only 确认/失败专项（H4，最关键）；
5. R_bar × state_S 联合分层（H6）；
6. 稳健性：板块、年份、LOPO（H7）；
7. 汇总为 stage3-results.md。
