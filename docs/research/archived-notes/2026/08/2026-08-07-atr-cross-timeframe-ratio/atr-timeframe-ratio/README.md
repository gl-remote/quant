# 研究文档索引

> ATR 跨周期波动率比值对市场环境分层的研究

## 当前主线文档

| 文档 | 内容 | 状态 |
|---|---|---|
| [atr-timeframe-ratio.md](./atr-timeframe-ratio.md) | 原始研究设计与因子定义（A–G 组） | 设计文档 |
| [stage1-distribution.md](./stage1-distribution.md) | 因子分布 EDA（32 合约牛市样本） | 历史 |
| [quadrant-profile.md](./quadrant-profile.md) | **四象限市场环境画像（全周期 2022–2026）** | **当前主参考** |
| [transition-paths.md](./transition-paths.md) | **压缩→共振的转换路径分析（H_path vs L_path）** | **当前主参考** |
| [wrap-up-and-next-direction.md](./wrap-up-and-next-direction.md) | 阶段性总结、方法论教训、方向校准 | 导航 |

## 已归档：H_only 交易信号探索（Stage 3–9 + 辅助验证）

这部分文档探索"H_only 是否可作为交易信号"，最终结论是**不可交易**（正收益来自多头 beta，非信号 alpha）。详见：

- [archive/h_only_signal_research/](./archive/h_only_signal_research/) — 所有阶段结果、VRP 验证、熊市验证、机制分析
- [archive/h_only_signal_research/README.md](./archive/h_only_signal_research/README.md) — 归档索引和结论链

## 脚本

| 脚本 | 用途 |
|---|---|
| [scripts/profile_quadrants_full.py](./scripts/profile_quadrants_full.py) | 全周期四象限画像（主画像） |
| [scripts/transition_paths.py](./scripts/transition_paths.py) | 状态转换路径分析 |
| [scripts/compare_5m_15m.py](./scripts/compare_5m_15m.py) | 5m vs 15m 口径对比 |
| [scripts/term_structure.py](./scripts/term_structure.py) | F 组跨期限结构（牛市样本，方向信号已被否定） |
| [scripts/fetch_bear_market.py](./scripts/fetch_bear_market.py) | 2022–2023 熊市数据下载 |
| `scripts/stage*.py`, `scripts/term_validation.py`, `scripts/vrp_validation.py` 等 | 已归档阶段的脚本 |

## 数据输出

- `outputs/profile_full/` — 全周期画像结果（主）
- `outputs/transition_paths/` — 转换路径结果（主）
- `outputs/compare_5m_15m/` — 5m/15m 对比
- `outputs/term_structure/`, `outputs/term_validation/`, `outputs/term_bear_validation/` — F 组分析（方向结论已归档）
- `outputs/stage*/`, `outputs/vrp_study/` — 已归档阶段输出

## 核心结论速览

1. **跨周期 ATR 比值是市场状态描述工具，不是方向信号**；
2. 四象限（双压缩 / H_only / L_only / 共振扩张）在牛熊中分布和波动率有显著差异；
3. 压缩→共振主要经 H_path（65%），L_path（14%）是少数但有不同特征；
4. **L_path 在熊市和有色板块更常见**，前向波动高、牛熊方向收益均正，值得后续研究；
5. 当前波动率（H_norm）预测未来波动率的能力（corr 0.41）远强于跨周期比值（0.05）；
6. 所有方向交易信号（H_only、R_1h_d、随机+止损）在 2022–2023 熊市中均失效，确认是 beta 而非 alpha。
