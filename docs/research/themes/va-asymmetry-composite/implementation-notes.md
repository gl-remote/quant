# va-asymmetry-composite · Implementation Notes

> 类型：Implementation Notes
> 版本：v0.1（立题占位版 · 阶段 4 工程化时补全）
> 最近更新：2026-07-09
> 主题 README：[README.md](README.md)
> 策略数学契约：[strategy-math-spec.md](strategy-math-spec.md) v0.1

**v0.1 = 立题占位**：阶段 0~3 只做向量化模拟（读 parquet + pandas/numpy 计算），
不需要工程化。阶段 4 工程化时本文件从占位 → 完整版。

## 1. 阶段 0~3 · 向量化模拟路线（立题时确定）

阶段 0-3 不写 vnpy Strategy 类，直接走向量化模拟，原因：
- 每秒可跑全量 143 合约 × 36625 events，速度比 vnpy BacktestEngine 快 100~1000x
- 组合搜索（阶段 2 ~27 配置）+ bootstrap（阶段 1+2 的 paired 检验）需要反复跑，
  vnpy 不适合这个阶段

**向量化模拟的数据链**：

```
[1] classifier timeline parquet（3 维 rank + tier · 1h 粒度）
    ↓
[2] 读 contract_specs（佣金/tick/slip/乘数）
    ↓
[3] 塑形参数 × 品种筛选 × 强度加权 × 多空权重（参数化函数）
    ↓
[4] 向量化 SL 触发检查（用 rolling min/max 近似，或读 1h 高/低价）
    ↓
[5] 时间退出检查（8h / 10h 后 close）
    ↓
[6] 成本计算（entry/exit 单边 realistic-cost）
    ↓
[7] 压仓（按时间排序的仓位循环，逐个名义累加超 100% 就按规则砍）
    ↓
[8] Trade-level parquet 输出（strategy-math-spec.md §10 字段）
    ↓
[9] 权益曲线聚合 + 指标（夏普 / 年化 / MaxDD / 月度胜率 / 品种保留率 / ν_implied）
```

**阶段 0~3 脚本临时路径**（按项目约束）：
- `scripts/ai_tmp/va_composite_*.py`（前缀 `va_composite_`，便于后续归档）
- 临时数据：`project_data/ai_tmp/va_composite_*`（前缀同上）

## 2. 阶段 4 · vnpy 集成占位（待补）

### 2.1 代码结构（预计）

```
workspace/
├── strategies/
│   ├── classifiers/
│   │   └── poc_va.py                       # 上游已提取（poc-value-area-asymmetry 阶段 4）
│   └── va_asymmetry_composite.py           # 本主题策略类（阶段 4 写）
└── common/
    ├── contract_specs.py                   # 已存在
    ├── symbol_utils.py                     # 已存在
    └── va_composite_risk.py                # 阶段 4 提取：压仓 / 风控 / 熔断
```

### 2.2 数据缓存（预计）

- 分类器特征（signed_skew_rank / daily_atr_bps_rank / trend_rank）：预计算并缓存为
  per-contract parquet，避免每次回测重算
- 缓存键：`<contract>_<start>_<end>_va_classifier_features.parquet`
- 失效条件：分类器契约升级（罕见）→ 手动清缓存

### 2.3 vnpy 桥接注意事项（预计 · 继承项目惯例）

- vnpy 日志目录：项目根 `.vntrader/log/`（按 project_memory：避免 HOME 权限问题）
- vnpy import：桥接模块用 lazy import（`__getattr__`），模块导入不触发 vnpy 立
  刻写文件的副作用
- Runner：`unset PYTHONHOME && unset PYTHONPATH && uv run python ...`（项目约束：
  sandbox PYTHONHOME=3.13 与项目 venv 3.12 冲突）

### 2.4 交叉验证（阶段 4 必做）

- 向量化模拟（阶段 0-3 路线） vs vnpy BacktestEngine（阶段 4 新路线）各跑一份 B0
- Trade-level PnL 99% 分位绝对差 < 1bp → 视为通过
- 若不通过：优先排查「成交价模型」（open_{t+1} vs close_t）、「SL 触发价」
  （bar 内 high/low 是否正确应用）、「压仓顺序」（时间戳精度）

## 3. 阶段 4 · 报表输出（预计）

| 报表 | 频率 | 内容 |
|:---|:---:|:---|
| 交易明细 parquet | 每次回测 | strategy-math-spec.md §10 字段 |
| 日度权益 CSV | 每次回测 | date · equity · drawdown · exposure_notional · margin_ratio |
| Tier 归因表 | 每次回测 | 各 tier 的 trades / mean_net_bps / IR / ν_implied / p(ν>0) |
| 品种类型归因表 | 每次回测 | A/B/C 类的贡献度 / 正收益占比 / 压仓比例 |
| 参数平台热力图 | 阶段 2+ | L1-L2 参数搜索结果 |
| Bootstrap 诊断 | 每次 Gatekeeper | paired diff 的 date-cluster CI 与 p 值 |
| Walk-Forward 滚动报表 | 阶段 3+ / 实盘 | 每 fold/split 的 OOS 指标 |

## 4. 变更记录

| 版本 | 日期 | 变更 |
|:---:|:---:|:---|
| v0.1 | 2026-07-09 | 立题占位版：阶段 0~3 向量化模拟路线确定；阶段 4 vnpy 集成 + 报表框架占位（空） |
