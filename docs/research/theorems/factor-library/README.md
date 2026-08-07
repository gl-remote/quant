# 因子库 Factor Library

> 可复用的量化因子定义、证据与边界。每个因子一个子目录，包含：
> - `definition.md`：数学定义，可直接编码；
> - `evidence.md`：关键统计证据（IC、mean、样本量、消融）；
> - `boundary.md`：适用边界、失效条件、未验证假设。
>
> 这里只放**蒸馏后的最终规格**。探索过程、证伪记录、中间实验保留在 `docs/research/themes/`。

---

## 因子索引

| 因子 | 一句话 | 状态 | 目录 |
|---|---|---|---|
| ATR Cross-Timeframe Ratio | 跨周期 ATR 比（1h/15m）做四象限状态分类；稳健的风险制度标签，不是方向 alpha | 已归档（商品期货 1h, 2022–2026） | [atr-cross-timeframe-ratio/](atr-cross-timeframe-ratio/) |
| Volume Spike × MADEV | 价格远离长期均线时，放量触发向均线的双向回归；适合作为趋势持仓减仓过滤器，不是独立 alpha | 已归档（商品期货 1h, 2024–2026） | [volume-spike/](volume-spike/) |

---

## 条目质量标准

一个合格的因子库条目必须满足：

1. **定义可编码**：数学公式精确到参数、lookback、归一化方式，不含"大概""可能"；
2. **证据有数字**：IC、样本量、置信区间、时间/品种 OOS 结果；
3. **边界诚实**：写清什么市场/周期/状态下有效，什么情况下失效；
4. **可追溯**：链接回 `docs/research/themes/` 的原始研究，不重复过程。

不合格的条目不进入因子库——它属于 workbench 笔记或研究主题。

---

## 分类约定（待扩展）

- `volume-*`：成交量相关
- `momentum-*`：动量/趋势
- `reversal-*`：反转
- `volatility-*`：波动率
- `liquidity-*`：流动性/微结构
- `cross-section-*`：截面因子
