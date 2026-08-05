# Stage 3 · 放量后路径形态分析（统一规律 vs 发散）

> 日期：2026-08-05
> 脚本：`docs/workbench/volume-spike-regime-shift/scripts/stage3_path_divergence.py`
> 数据：`project_data/research/volume-spike-regime-shift/stage3_paths.parquet`、`stage3_path_analysis.json`

## 问题

成交放量能否认为是"之前的市场制度走到盛极反衰"？放量后的行情是有统一规律，还是往不同方向发散？

## 方法

- 1454 个 spike 事件（$Z\ge2$，同时段口径），4293 个 baseline；
- 对称 20 根 bar：pre $[t-20,t-1]$、event bar $t$、post $[t+1,t+20]$；
- cluster bootstrap（2000 次，cluster=(symbol, session_date)）；
- 分层：pre 窗累计收益三分位（pre_down/flat/up）、spike bar 阴阳；
- 路径离散度：post 累计路径标准差、窗内最大有利/不利偏移。

## 结果

### 1. post 累计收益无统一方向

| 组 | mean | median | p10 | p90 | % 负 | % 正 |
|---|---:|---:|---:|---:|---:|---:|
| spike | +0.00094 | +0.00083 | −0.0149 | +0.0167 | 45.7% | 52.5% |
| baseline | +0.00149 | +0.00128 | −0.0127 | +0.0157 | 43.8% | 54.7% |

spike post mean 95% CI [−0.0007, +0.0026] 含 0，与 baseline 的 DiD −0.00055 也不显著。涨跌比例接近对半。

### 2. pre 趋势分层：没有统一反转

| pre 桶 | pre_cum | post mean | 95% CI | post 中位 | % 负 |
|---|---:|---:|---|---:|---:|
| pre_down | −1.25% | −0.00002 | [−0.0027, +0.0026] | +0.00093 | 46.2% |
| pre_flat | +0.33% | +0.00225 | [+0.0008, +0.0039] | +0.00142 | 40.7% |
| pre_up | +2.12% | +0.00060 | [−0.0027, +0.0037] | −0.00033 | 50.1% |

- "盛极反衰"只在 pre_up 桶有弱迹象（中位转负、50% 下跌），但均值不显著；
- pre_flat 后反而继续正漂移；pre_down 后走平。

### 3. spike bar 颜色不延续

- 阳线 spike 后 post mean +0.00141（CI 含 0）；
- 阴线 spike 后 post mean +0.00031（CI 含 0）；
- signed post 全部不显著。

### 4. 路径发散（唯一稳健规律）

| 度量 | spike | baseline | DiD |
|---|---:|---:|---:|
| path_disp | 0.00529 | 0.00451 | +0.00079 |
| max_fav | +0.00937 | +0.00829 | +0.00108 |
| max_adv | −0.00822 | −0.00664 | −0.00158 |
| post_abs | 0.00219 | 0.00193 | +0.00026 |

放量后双向尾部都放大，向下尾部扩张更明显。跨品种主符号比例仅 48.5%–69.2%，无方向共识。

## 结论

- 放量不是统一反转信号；它是**波动簇峰值 + 不确定性跃升**。
- "盛极反衰"只描述约 1/3（pre_up）场景，不能推广。
- 因子价值在 regime 标记（"接下来波动更大、尾部更宽"），不在方向预测。
- 撤回 Stage 2.5 的"买盘衰竭/负向漂移"措辞——严格对称窗口 + placebo 后不显著。
