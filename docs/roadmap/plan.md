# 项目改进计划

> 版本: 0.5.0-dev | 最后更新: 2026-06-26 | 主线: 新策略探索与多窗口验证
>
> 本文档定位：**总体规划指南 + 重要事件记录档案**，集中保留需持续关注的事项（路线图、待办、已知缺陷、风险）。

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
| **S2-B** MA 基线验证 | 多品种、多窗口、Walk-Forward 验证 MA 是否可用 | 🟡 延续至 0.5 |
| **S2-C** 新策略探索 | 通道突破 / RSI / 布林带 / 波动率过滤等候选策略 | 🟡 0.5 主线 |
| **S2-D** 上线前验证流程 | paper trading、dry-run、最小仓位试运行流程 | ⬜ S3 前置 |
| **S3** 生产加固 | 风控熔断 + 通知 | ⬜ 未开始 |
| **S4** 基础设施 | Docker + CI 增强 | 🟡 0.4 已推进，Docker 未做 |
| **S5** 策略研发工具增强 | 参数热力图、结果 diff、归因、蒙特卡洛 | ⬜ 未开始 |

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

### S2-B: MA 基线验证（0.5 延续）

> ⚠️ 2026-05-28：早期双均线策略已证实无效。优化器最优点 `sma_short=35, sma_long=35` 为零交易退化解。
>
> 2026-06-06 更新：MA 策略在个别品种窗口中表现较好，但跨品种泛化差，交易成本高。MA 现在作为 baseline 保留，用于验证工具链和对比新策略。
>
> 2026-06-26 更新：0.4 实际主要用于基础设施、报告、契约、质量门禁等非策略工作；0.5 重新聚焦策略有效性验证。

**核心目标**: 至少 1 个策略在**多品种多时段**验证下满足夏普 ≥ 0.5、最大回撤 < 20%。

| 工作项 | 说明 | 状态 |
|--------|------|------|
| MA 正期望优化复盘 | MA baseline 主线阶段性退出，作为后续策略对照基准保留 | ✅ 已归档，见 [ma-positive-expectancy.md](../archive/strategy-research/ma-positive-expectancy.md) |
| MA 多品种验证 | 同一参数组在多个合约上跑通，排查单品种偶然性 | 🟡 进行中 |
| MA 多窗口验证 | 按时间窗口滚动验证，排除窗口过拟合 | 🟡 进行中 |
| 交易成本敏感性 | 评估手续费、滑点对策略收益的侵蚀 | 🟡 进行中 |
| 参数鲁棒性 | 检查参数邻域是否稳定，避免尖峰最优 | ⬜ 待做 |

### S2-C: 新策略探索（0.5 主线）

| 方向 | 说明 | 状态 |
|------|------|------|
| 通道突破 | Donchian / N 日高低点突破，作为趋势跟随候选 | ⬜ 待做 |
| 布林带 | 波动率通道突破或均值回归候选 | ⬜ 待做 |
| RSI/KDJ 反转 | 超买超卖反转策略，重点评估震荡品种 | ⬜ 待做 |
| 趋势过滤 | 用大周期趋势过滤小周期信号，减少逆势交易 | ⬜ 待做 |
| 波动率过滤 | 过滤低波动/异常波动区间，降低噪声交易 | ⬜ 待做 |

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
| 当前主线 | 新策略探索 + MA baseline 多窗口验证；非策略工程项只保留必要维护 |

---

## 四、策略架构改进

> 围绕策略声明式 DSL（装饰器）与参数体系的开发体验改进。0.5 中这些工作不是主线，只在直接阻碍策略验证时处理。

### 0.5 可选项

#### 1. ~~data_requirements 空壳问题~~ ✅ 已完成
**现状**：装饰器已自动注册数据需求，但 `data_requirements()` 还需返回空 `DataRequirements()`
**目标**：框架自动合并装饰器注册的需求，策略无需实现 `data_requirements` 或返回 None 即可
**方案**：`Strategy.data_requirements` 基类默认返回空 `DataRequirements`，装饰器在此基础上 merge；策略无需覆写

#### 2. 分级止盈装饰器
**现状**：只有固定比例止盈（`with_stop_take_profit`）和 ATR 止盈（`with_atr_stop_take_profit`），缺少"持仓越久止盈越宽松"的能力
**目标**：新增 `with_tiered_take_profit` 拦截型装饰器
**方案**：
```python
@with_tiered_take_profit({0: 0.08, 30: 0.04, 60: 0.02, 120: 0.01})
# 持仓 0 分钟盈利 8% 止盈，30 分钟后降到 4%，以此类推
```

#### 3. 装饰器分组可读性
**现状**：10+ 个装饰器堆叠在类上方，视觉密集
**目标**：支持列表式声明，减少堆叠层数
**方案**：
```python
# 方案 A：列表式声明（建议型）
long_conditions = [
    trend_long_when_compare(at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "15m")),
    confirm_long_when(at(MACD, "1m"), ">", 0),
    confirm_long_when(at(MACD, "5m"), ">", 0),
    confirm_long_when(at(KDJ, "1m"), "<", "kdj_oversold"),
    confirm_long_when(at(KDJ, "5m"), "<", "kdj_oversold"),
]
```
需要改造装饰器注册机制，支持非 `@` 语法也能注册 `__direction_keys__`

### 后续周期

#### 4. 参数优化空间声明（Hyperopt 集成）
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

#### 5. IDE 友好性提升
**现状**：`__direction_keys__` 动态注册，IDE 无法跳转和补全
**目标**：提升开发体验
**方案**：
- 生成 `__init__.pyi` 类型存根
- 或在装饰器内用 `__class_getitem__` 提供类型提示
- 声明式 DSL 的通病，优先级低

#### 6. 策略模板 / 脚手架
**现状**：新建策略需手动复制装饰器组合
**目标**：CLI 一键生成策略骨架
**方案**：`quant create-strategy --name rsi --indicators RSI,MACD --stops atr_stop,take_profit`

#### 7. 统一 TqSdk 单标的与 vn.py 批量回测生命周期（自 backtest-refactor-plan 阶段 10 移入）
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
| A22 | 参数敏感性热力图 | P1 | 展示参数鲁棒性区域 vs 过拟合悬崖 |
| A23 | 回测结果对比/diff 工具 | P1 | 逐指标差异对比，支持迭代回归检测 |
| A24 | 策略归因分析 | P1 | 按时段/品种/信号类型分解盈亏来源 |
| A25 | 蒙特卡洛模拟 | P1 | 交易随机重排 / bootstrap 权益曲线 |
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
| 策略无法稳定盈利 | 🔴 已确认 | 高 | MA 仅作为 baseline；0.5 聚焦新策略研发和多窗口验证 |
| 参数优化过拟合 | 高 | 高 | Walk-Forward + 参数鲁棒性分析 |
| 优化器选退化解 | 🔴 已确认 | 高 | 增加交易次数/活跃度约束 |
| 数据窗口过短 | 中 | 中 | 补充多周期、多窗口验证 |
| 实盘链路风险 | 中 | 高 | test/live 分离、paper trading、小仓位试运行、风控熔断 |
