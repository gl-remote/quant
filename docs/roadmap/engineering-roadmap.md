# 工程长期路线图

> 版本: 0.5.0-dev | 最后更新: 2026-06-28 | 主线: 结构型 Alpha 研究支撑与策略研发基础设施
>
> 本文档定位：**长期工程规划框架 + 重要事件记录档案**，集中保留需持续关注的工程路线图、待办、已知缺陷和风险。策略研究方法论见 [策略研究框架](./strategy-research-framework.md)。

---

## 一、项目现状

### 模块架构

```
main.py
├── cli/                    命令接口
├── strategies/             策略核心 (框架无关)
│   ├── core/               ABC + 类型定义
│   ├── runtime/            DataFeed / PeriodData / 多周期视图
│   ├── bridges/            vnpy / 天勤 桥接
│   └── ma_strategy.py      MA 基线策略
├── backtest/               回测与优化引擎 (含参数优化)
│   ├── vnpy_backtest_engine.py  批量回测
│   ├── walk_forward.py          Walk-Forward 时间窗口
│   ├── runners.py               批量回测编排
│   └── optimizer.py             Optuna 参数优化
├── data/                   数据层 (多数据源 + SQLite + peewee)
├── common/                 纯函数工具层
├── report/                 React SPA 报告系统
│   ├── builder.py          编排入口
│   ├── cache/              增量构建缓存
│   ├── reporter/           ECharts option 生成
│   ├── writer/             JSON 导出
│   └── web/                Vite + TypeScript 前端
├── config/                 Pydantic 配置管理
└── tools/                  运维脚本
```

### 架构决策

| 决策 | 说明 |
|------|------|
| Strategy + Bridge 分离 | 策略核心不依赖任何交易/回测框架 |
| DataFeed 统一指标路径 | backtest/test/live 复用 PeriodData + 指标注册/计算逻辑 |
| test/live 命令分离 | test 永不下单；live 才允许 TargetPosTask 下单 |
| 复用 vnpy 回测引擎 | 订单撮合/滑点/手续费/逐日盯市 |
| React SPA + 数据预加载 | `window.__DATA__` 内联，支持 `file://` 离线访问 |
| 增量构建缓存 | KlineCache + BuildCache，避免重复计算 |
| UTC 时间戳全链路 | CSV→JSON→前端 Unix timestamp，显示层 `new Date()` 转本地时区 |

---

## 二、版本路线图

| 阶段 | 目标 | 状态 |
|------|------|------|
| **S2-A** 策略研发基础设施 | 回测/test/live 链路、DataFeed、报告、质量门禁 | ✅ 已完成（0.3.0） |
| **S2-B** 指标型 baseline 收敛 | MA / ATR 主触发研究归档，保留 baseline 与风控模块 | ✅ 已归档 |
| **S2-C** 结构型 Alpha 验证 | 围绕共识价格区间、失败边界、盈利上界和账户风险预算推进短期研究 | 🟡 0.5 主线 |
| **S2-D** 上线前验证流程 | paper trading、dry-run、最小仓位试运行流程 | ⬜ S3 前置 |
| **S3** 生产加固 | 风控熔断 + 通知 | ⬜ 未开始 |
| **S4** 基础设施 | Docker + CI 增强 | 🟡 0.4 已推进，Docker 未做 |
| **S5** 策略研发工具增强 | 结构诊断、参数邻域、结果 diff、归因、蒙特卡洛 | ⬜ 未开始 |

### S2-A: 策略研发基础设施（0.3.0 已完成）

0.3.0 的定位不是“策略已完成”，而是“策略研发和实时验证基础设施完成”。

| 模块 | 0.3.0 完成内容 |
|------|----------------|
| 回测链路 | vnpy 回测、批量回测、参数优化、Walk-Forward 工具链可用 |
| 实时链路 | tqsdk test/live 路径打通，test 使用实时行情但不下单，live 才下单 |
| DataFeed | 多周期 PeriodData、指标注册、初始化全量计算、实时单周期增量触发 |
| 指标一致性 | backtest/test/live 复用同一套指标计算机制，并补充覆盖测试 |
| 报告系统 | React SPA 报告、图表、表格、主题体系、数据预加载与展示增强 |
| 质量门禁 | ruff / ruff-format / mypy / pytest smoke test 通过 pre-commit 触发 |
| 安全治理 | 清理敏感凭证历史，test/live 形成明确安全边界 |

### S2-B: 指标型 baseline 收敛（已归档）

> 2026-06-26：MA 与 ATR 作为主触发 / 主 alpha 方向均已完成阶段性复盘。结论是：指标组合和参数搜索不能承担创造策略优势的职责；MA 保留为 baseline，ATR 保留为波动归一、止损、止盈和账户风险预算模块。
>
> 后续不再以“扩大 MA / ATR trial、叠加 MACD / KDJ / 均线确认、继续调 ATR 止损止盈”为 0.5 主线。相关研究已归档到 [2026-06-26-indicator-baseline](../archive/strategy-research/2026-06-26-indicator-baseline/)。

| 工作项 | 说明 | 状态 |
|--------|------|------|
| MA 正期望优化复盘 | MA baseline 主线阶段性退出，作为后续策略对照基准保留 | ✅ 已归档，见 [ma-positive-expectancy.md](../archive/strategy-research/2026-06-26-indicator-baseline/ma-positive-expectancy.md) |
| ATR 策略研究复盘 | ATR 主触发方向降级，保留为风控和波动归一模块 | ✅ 已归档，见 [strategy-atr-tuning.md](../archive/strategy-research/2026-06-26-indicator-baseline/strategy-atr-tuning.md) |
| MA / ATR baseline 维护 | 仅在后续结构实验需要对照或复用风控时维护，不再作为主线调参对象 | 🟡 按需维护 |
| 指标型组合信号 | MACD / KDJ / 均线等仅作为趋势背景、动量变化和状态诊断工具 | ✅ 定位完成 |

### S2-C: 结构型 Alpha 验证（0.5 主线）

当前策略工程主线服务于 [策略短期研究计划](./strategy-short-term-plan.md)：不做原创预测型 alpha discovery，也不依赖长期 beta 暴露，而是围绕共识价格区间、失败边界、盈利上界、账户风险预算和胜率 / 盈亏比转化效率，验证是否存在结构型 alpha。

| 方向 | 工程目标 | 状态 |
|------|----------|------|
| `structural-alpha-r1` 实验支撑 | 支持共识价格区间、严格失败边界、盈利上界和账户风险预算的最小实验闭环 | 🟡 当前主线 |
| 共识价格区间候选 | 优先支持 Initial Balance、前日高低点 / 昨收 / 开盘区间、VAH / VAL / POC、密集成交区边缘等客观边界 | 🟡 候选方向 |
| 结构塑形翻译 | 每个候选结构必须能记录传统解释、结构塑形解释、方向假设、失败边界、盈利上界和接受 / 拒绝证据 | 🟡 文档 + 实验约束 |
| 账户风险预算预筛 | 回测前检查合约乘数、最小手数、滑点、跳空后，严格失败边界能否映射到 2%~3% 单次账户风险 | ⬜ 待强化 |
| 价格 / 账户原始盈亏比诊断 | 输出预期盈利上界、严格失败距离、价格原始盈亏比和账户原始盈亏比 | ⬜ 待强化 |
| 胜率 / 盈亏比转化诊断 | 对比严格失败退出、主动止盈、时间退出、有限止损放宽 + 同步降仓后的成本后期望变化 | ⬜ 待强化 |
| 接受 / 拒绝质量诊断 | 输出严格边界快速再触及率、MAE / MFE、失败测试质量和 exit reason 分布 | ⬜ 待强化 |
| 参数搜索 / Walk-Forward | 只在结构初步成立、参数邻域稳定、样本量足够后启用 | ⬜ 后置 |

### S2-D: 上线前验证流程（S3 前置）

| 工作项 | 说明 | 状态 |
|--------|------|------|
| test 实时信号观察 | 连接实时行情，仅记录信号，不下单；不承担完整模拟交易语义 | ✅ 基础链路已完成 |
| paper trading | 长时间模拟盘运行，验证稳定性和信号质量；需与 test 信号观察显式区分 | ⬜ 待做 |
| 小仓位试运行 | 满足策略验收后，用最小仓位验证实盘链路 | ⬜ 待做 |
| 运行监控 | 异常通知、断线重连、订单状态监控 | ⬜ 待做 |

---

## 三、dev/0.5 起始状态快照

| 类别 | 当前状态 |
|------|----------|
| 当前分支 | `dev/0.5` |
| 当前版本 | `0.5.0-dev` |
| 上一阶段复盘 | 0.4 主要推进基础设施、报告、契约、质量门禁和工程治理；策略有效性验证未形成主线闭环 |
| 最新发布 | `v0.3.0` 已合并至 `main` 并推送远端 |
| 测试基线 | 沿用 0.4 质量门禁基线，变更后按需重新刷新 |
| 质量门禁 | pre-commit 已启用 ruff / ruff-format / mypy / pytest smoke |
| CI | GitHub Actions 已覆盖 Python 3.12、ruff、mypy、pytest、覆盖率门槛、前端 lint/test/build |
| 当前主线 | 结构型 Alpha 验证；围绕共识价格区间、账户风险预算、原始盈亏比和胜率 / 盈亏比转化推进 `structural-alpha-r1` |

---

## 四、策略架构改进

> 围绕结构型 Alpha 实验的最小必要能力改进。0.5 中这些工作不是通用框架重构主线，只在直接阻碍 `structural-alpha-r1` 诊断时处理。

### 0.5 可选项

#### 1. ~~data_requirements 空壳问题~~ ✅ 已完成
**现状**：装饰器已自动注册数据需求，但 `data_requirements()` 还需返回空 `DataRequirements()`
**目标**：框架自动合并装饰器注册的需求，策略无需实现 `data_requirements` 或返回 None 即可
**方案**：`Strategy.data_requirements` 基类默认返回空 `DataRequirements`，装饰器在此基础上 merge；策略无需覆写

#### 2. 结构实验诊断字段
**现状**：当前报告和交易记录更偏向收益、胜率、PnL，不足以直接判断结构型 Alpha 是否成立。
**目标**：让策略实验能稳定输出严格失败边界、预期盈利上界、价格原始盈亏比、账户原始盈亏比、止损放宽倍数、仓位调整倍数、严格边界快速再触及率、MAE / MFE 和 exit reason。
**方案**：优先在策略 diagnostics / backtest trade artifact / report JSON 中补齐结构诊断字段；字段必须保持数值化或显式类型化，避免再次触发诊断字段格式化问题。

#### 3. 账户风险预算预筛
**现状**：策略回测后才能发现合约乘数、最小手数、滑点或跳空导致 2%~3% 单次账户风险不可执行。
**目标**：在回测前提供最小预筛能力，判断严格失败距离能否映射到目标账户风险预算。
**方案**：复用合约乘数、最小手数、手续费、滑点配置，计算单手严格失败损失、目标账户风险、理论仓位和最小手数约束；预筛不通过的结构不进入参数搜索。

#### 4. 主动止盈 / 时间退出 / 有限止损放宽对照
**现状**：历史 low-validation-cost 实验能比较严格止损和放宽止损，但缺少账户风险同步降仓和胜率 / 盈亏比转化效率的统一诊断。
**目标**：固定输出严格失败退出、主动止盈、时间退出、有限止损放宽 + 同步降仓的对照结果。
**方案**：在 `structural-alpha-r1` 最小策略实现中显式记录退出原因、止损放宽倍数、仓位调整倍数、胜率提升、盈亏比下降、成本后期望净变化。

### 后续周期

#### 5. 参数优化空间声明（Hyperopt 集成）
**现状**：`MACrossParams` 的参数是固定默认值，无法声明优化范围
**目标**：支持 `IntParameter` / `DecimalParameter` 声明参数搜索空间
**方案**：
```python
@dataclass
class MACrossParams:
    sma_short: int = IntParameter(5, 30, default=10)
    stop_loss_ratio: float = DecimalParameter(0.01, 0.10, default=0.03)
```
需要对接 Optuna / Freqtrade Hyperopt 等优化引擎

#### 6. IDE 友好性提升
**现状**：`__direction_keys__` 动态注册，IDE 无法跳转和补全
**目标**：提升开发体验
**方案**：
- 生成 `__init__.pyi` 类型存根
- 或在装饰器内用 `__class_getitem__` 提供类型提示
- 声明式 DSL 的通病，优先级低

#### 7. 策略模板 / 脚手架
**现状**：新建策略需手动复制装饰器组合
**目标**：CLI 一键生成策略骨架
**方案**：`quant create-strategy --name rsi --indicators RSI,MACD --stops atr_stop,take_profit`

#### 8. 统一 TqSdk 单标的与 vn.py 批量回测生命周期（自 backtest-refactor-plan 阶段 10 移入）
**现状**：TqSdk 单标的路径不创建 run、不挂 `RunLogHelper`/`RunFinalizer`、不生成前端 JSON，仅写 `backtests`/`backtest_trades` 表（`report --id N` 可查）；vn.py 批量路径已走完整 run 生命周期。
**目标**：让 TqSdk 路径也走统一 run 生命周期、日志、持久化与前端 JSON 输出。
**前置障碍（决定为何后置）**：
- bridge 仅产出 `fills`，无账户净值序列（daily/equity），前端 run 视图核心曲线接进去是空的。
- 逐笔 `pnl`/`commission` 当前为占位值（见 `_persist_tq_backtest_result`），需补真实逐笔盈亏。
- `RunFinalizer` 会触发 `build_frontend` 全量重建，单标的/`--gui` 场景的收尾时机需单独处理。
**结论**：机械搬运（建 run / 接 persister / finalizer）不难，但需先补 bridge 数据缺口，否则只是接空壳。详细方案见 [backtest-refactor-plan.md 阶段 10](file:///Users/gaolei/Documents/src/quant/docs/archive/backtest/backtest-refactor-plan.md#L1506-L1534)。

---

## 五、生产加固（S3）

| 编号 | 行动 | 优先级 | 说明 |
|------|------|--------|------|
| A15 | 实盘风控熔断 | P0 | 单日亏损、连续亏损、最大持仓、异常价格保护 |
| A17 | 异常通知 | P0 | 微信/邮件/日志告警 |

---

## 六、基础设施（S4）

| 编号 | 行动 | 优先级 | 状态 | 说明 |
|------|------|--------|------|------|
| A19 | pre-commit 钩子 | P0 | ✅ 已完成 | ruff / ruff-format / mypy / pytest smoke |
| A20 | CI 修复 | P0 | ✅ 已完成 | Python 3.12、ruff、mypy、pytest、覆盖率门槛、前端 lint/test/build |
| A16 | Docker 支持 | P2 | ⬜ 未开始 | 容器化部署 |

---

## 七、策略研发工具增强（S5）

| 编号 | 行动 | 优先级 | 说明 |
|------|------|--------|------|
| A22 | 结构诊断报告字段 | P1 | 展示严格失败边界、盈利上界、价格/账户原始盈亏比、账户风险预算、止损放宽、MAE / MFE 和 exit reason |
| A23 | 回测结果对比/diff 工具 | P1 | 对比严格失败退出、主动止盈、时间退出、有限止损放宽 + 同步降仓的指标变化 |
| A24 | 策略归因分析 | P1 | 按共识价格区间、接受 / 拒绝质量、失败边界、退出原因、成本和市场状态分解盈亏来源 |
| A25 | 蒙特卡洛模拟 | P1 | 交易随机重排 / bootstrap 权益曲线，评估亏损簇和账户生存能力 |
| A26 | Jupyter 探索环境 | P2 | 支持交互式数据分析 |
| A27 | 清理未使用依赖 | P2 | plotly/matplotlib 等依赖决定集成或移除 |

---

## 八、已知缺陷

| 编号 | 严重度 | 问题 | 位置 | 状态 |
|------|--------|------|------|------|
| DEF-06 | 🔴 | 优化器可选退化解（零交易 → 最优） | `backtest/optimizer.py` + `ma_strategy.py` | 🟡 待修复 |
| DEF-S05 | 🟡 | 信号优先级由 if/elif 顺序隐式定义 | `ma_strategy.py` | 🟡 待修复 |
| DEF-07 | 🟡 | TqSdk 路径 `total_return` 存金额而非百分比、逐笔 `commission` 硬编码为 0 | `cli/workflows/backtests_run.py` (`_persist_tq_backtest_result`) | ⬜ 已记录，归入「四.7 统一 TqSdk 生命周期」一并处理 |
| DEF-08 | 🟢 | 数据库旧回测数据未迁移 | — | ⬜ 需重新跑回测后自动修正 |
| DEF-09 | 🟡 | test 与 paper trading 语义未显式建模：test 应只做信号观察，paper 应维护模拟订单/成交/持仓/账户状态 | `cli/commands/test.py`、`cli/commands/live.py`、`cli/workflows/realtime.py` | ⬜ 长期规划，归入「S2-D 上线前验证流程」 |

---

## 九、风险评估

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 策略无法稳定盈利 | 🔴 已确认 | 高 | 指标型主触发已降级；0.5 聚焦结构型 Alpha 验证，先检查共识区间、账户风险预算和成本后期望 |
| 参数优化过拟合 | 高 | 高 | 参数搜索后置，只在结构初步成立、参数邻域稳定、样本量足够后启用 Walk-Forward |
| 优化器选退化解 | 🔴 已确认 | 高 | 在结构诊断通过前不启用优化器；继续保留交易次数/活跃度约束 |
| 数据窗口过短 | 中 | 中 | 短期先验证结构定义、风险预算和成本空间；结构成立后再做多窗口验证 |
| 实盘链路风险 | 中 | 高 | test/live 分离、paper trading、小仓位试运行、风控熔断 |
