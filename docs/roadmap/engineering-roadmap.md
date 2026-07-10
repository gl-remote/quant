# 工程长期路线图（工程路线纲领）

> 类型：Engineering Roadmap / Charter
> 范围：**只关心工程能力**。策略研究方法论、结构塑形框架、短期研究计划见 [策略研究框架](./strategy-research-framework.md) 与对应文档。
> 当前分支：`dev/0.6` ｜ 工程版本基线：`0.4.0-dev`（`pyproject.toml`）｜ CHANGELOG 当前：`0.4.0-dev`（已回填 `0.3.0`）
> 最后更新：2026-07-10

本文档定位为**工程路线纲领**：以能力域组织工程长期方向、当前真实状态、待办、已知缺陷与风险。它不是逐条对齐策略研究的"计划（plan）"，而是工程侧的架构与演进纲领，集中保留需持续关注的工程路线图、已知缺陷和风险。策略研究进展不在此复述。

---

## 一、定位与范围边界

| 维度 | 本文档（工程） | 策略研究（另见 framework） |
|------|----------------|---------------------------|
| 关注对象 | 回测 / 实盘链路、数据、报告、质量门禁、CI、基础设施、生产加固、研发工具 | 结构塑形、共识区间、账户风险预算、正期望验证 |
| 产物 | 可运行、可验证、可部署的工程能力 | 策略假设、实验证据、研究结论 |
| 验收 | 质量门禁通过、链路可跑、缺陷收敛 | 成本后长期正期望、安全边际 |
| 不在此处 | 任何策略方向选择、接受/拒绝质量判定、盈亏比论证 | 任何工程实现细节、模块重构方案 |

> **版本叙事对齐（行动项）**：当前 `pyproject.toml` 为 `0.4.0-dev`，`CHANGELOG.md` 停留在 `0.2.1-dev`，而研究分支已推进到 `dev/0.5`（策略研究取得稳定盈利突破）/ `dev/0.6`（当前）。路线图此前误用 `0.5.0`/`0.6.0` 作为发布版本号，代码与 CHANGELOG 均无对应事实支撑。后续应在合并关键能力后同步 `pyproject` 版本号与 `CHANGELOG`，使工程版本叙事与代码一致（见第五节 A30）。

---

## 二、工程能力现状（已核实）

> 下列状态均基于真实代码与配置核查，非路线预期。过时描述已按代码修正。

### 2.1 模块架构（真实）

```
main.py                       # CLI 入口，转发至 cli.main
workspace/
├── cli/                      # 命令接口
│   ├── commands/             #   backtest / export / live / report / test
│   └── workflows/            #   backtests_run / backtests_lifecycle / realtime / report / clearing
├── strategies/               # 策略核心（框架无关）
│   ├── core/                 #   ABC + 类型定义 + 指标注册 + diagnostics/
│   ├── runtime/              #   DataFeed / PeriodData / 多周期视图 / events / aggregate
│   ├── bridges/              #   tqsdk_bridge / vnpy_backtest_bridge
│   ├── strategy_aspects/     #   止损/止盈/冷却等策略切面 + risk/
│   ├── classifiers/          #   分类器
│   └── ma_strategy.py        #   MA baseline 策略
├── backtest/                 # 回测与优化引擎
│   ├── vnpy_backtest_engine.py   # 批量回测（复用 vnpy 撮合）
│   ├── walk_forward.py           # Walk-Forward 时间窗口
│   ├── optimizer.py              # Optuna 参数优化（含退化解下限约束）
│   ├── parallel.py / persister.py / strategy_factory.py / optuna_study.py  # 批量回测编排
├── data/                     # 数据层（多数据源 + SQLite + peewee）
│   ├── datasource/           #   akshare_source / tqsdk_source / base
│   ├── store.py / models.py / manager.py / migrations.py  # 持久化 + 自动迁移
├── report/                   # 报告系统（Python 包 + React SPA 前端 web/）
│   ├── builder/              #   编排入口（包，非单文件 builder.py）
│   ├── cache/                #   增量构建缓存（KlineCache / BuildCache）
│   ├── reporter/             #   ECharts option 生成
│   ├── writer/               #   JSON 导出
│   └── web/                  #   Vite + TypeScript 前端（antd/echarts/lightweight-charts）
├── config/                   # Pydantic 配置（schemas.py / manager.py + TOML）
├── clearing/                 # 回测成交清算服务（非实盘风控）
├── common/                   # 纯函数工具层（constants / formulas / metrics / schemas / types）
├── packages/                 # 跨域共享契约
│   ├── contracts/            #   JSON schema
│   └── python-contracts/     #   带 validate.py 与测试
└── tests/                    # 横切验证层（按域子目录对齐源码）
scripts/                      # 仓库级脚本（根级，非 workspace/tools/）
├── test.sh                   #   统一验证（lint/format/type/unit/coverage）
└── tools/ analysis/ test/    #   操作脚本（拉数据/回测/清数据）
```

变更说明（相对旧版路线图）：
- `backtest/runners.py` **不存在**，实际为 `parallel.py` / `persister.py` / `strategy_factory.py` / `optuna_study.py`。
- `report/builder.py` 实际是 **`report/builder/` 包**。
- 运维脚本位于根级 **`scripts/`**，不是 `workspace/tools/`。

### 2.2 架构决策（已落地）

| 决策 | 状态 | 说明 |
|------|------|------|
| Strategy + Bridge 分离 | ✅ | 策略核心不依赖任何交易/回测框架 |
| DataFeed 统一指标路径 | ✅ | backtest/test/live 复用 PeriodData + 指标注册/计算逻辑 |
| test/live 命令分离 | ✅ | test 永不下单；live 才允许 TargetPosTask 下单 |
| 复用 vnpy 回测引擎 | ✅ | 订单撮合/滑点/手续费/逐日盯市 |
| React SPA + 数据预加载 | ✅ | `base: "./"` 单文件打包，`window.__DATA__` 内联，支持 `file://` 离线访问 |
| 增量构建缓存 | ✅ | KlineCache + BuildCache，避免重复计算 |
| UTC 时间戳全链路 | ⚠️ 未确证 | 前端有 Unix timestamp 处理，但无显式 UTC 全链路断言证据，需运行时验证 |

### 2.3 质量门禁与 CI（已落地）

| 能力 | 状态 | 说明 |
|------|------|------|
| ruff / ruff-format | ✅ | `pyproject.toml` 已配置（select E/W/F/I/N/UP/B/SIM） |
| mypy | ✅（部分覆盖） | 严格模式 `disallow_untyped_defs`；CI 仅覆盖 `common/data/backtest/strategies` 4 子包，未含 `cli/report/config` |
| pytest + 覆盖率 | ✅ | `scripts/test.sh` 统一验证；CI `--cov-fail-under=60`；README badge 显示 333 passed |
| pre-commit | ✅ | 9 个 `verify-*` 业务域 hook + `uncovered-changes` 兜底 |
| CI（GitHub Actions） | ✅ | 单 job `lint-and-test`：Python 3.12 + Node 20，覆盖 ruff / ruff-format / mypy(4 子包) / pytest+覆盖率 / 前端 lint+test+build |

偏差：CI 覆盖率门槛为 60%；mypy 在 CI 中未全量覆盖。两者需在 3.4 中收敛。

### 2.4 报告系统（已落地）

- React SPA 前端（React 18 + TS 5.6 + Vite 5.4 + antd + echarts）可构建，`dist/` 产物已存在。
- 前端含 `StructuralDiagnostics.tsx`、`OptunaCharts.tsx`、run 详情页等，能力已超出"基础"。
- 增量构建缓存（`cache/kline.py`、`cache/build.py`）真实可用。

### 2.5 策略研发工具（S5，部分落地）

| 编号 | 行动 | 优先级 | 状态 | 说明 |
|------|------|--------|------|------|
| A22 | 结构诊断报告字段 | P1 | ✅ 已落地 | `strategies/core/diagnostics/`（`alpha.py`/`risk.py`/`execution.py`）含严格失败边界、盈利上界、账户风险预算、MAE/MFE、exit reason；前端 `StructuralDiagnostics.tsx` 展示 |
| A23 | 回测结果对比/diff 工具 | P1 | ⬜ 未开始 | — |
| A24 | 策略归因分析 | P1 | ⬜ 未开始 | — |
| A25 | 蒙特卡洛模拟 | P1 | ⬜ 未开始 | — |
| A26 | Jupyter 探索环境 | P2 | ⬜ 未开始 | — |
| A27 | 清理未使用依赖 | P2 | 🟡 待做 | `plotly`/`matplotlib` 等依赖需决定集成或移除 |

---

## 三、工程路线纲领（按能力域）

> 每个能力域标注当前状态与下一步工程动作。策略研究突破（dev/0.5 稳定盈利）使工程主线从"基建"转向"验证与加固"。

### 3.1 研发基础设施（基线，已完成）

0.3/0.4 阶段已交付工程基线：回测 / test / live 链路、DataFeed、报告系统、质量门禁、CI。此域不再作为主线，仅维护性迭代。

| 模块 | 已完成内容 |
|------|------------|
| 回测链路 | vnpy 批量回测、参数优化、Walk-Forward、并行编排 |
| 实时链路 | tqsdk test/live 路径打通，test 使用实时行情但不下单，live 才下单 |
| DataFeed | 多周期 PeriodData、指标注册、初始化全量计算、实时单周期增量触发 |
| 指标一致性 | backtest/test/live 复用同一套指标计算机制 |
| 报告系统 | React SPA、图表/表格/主题、数据预加载与增量构建缓存 |
| 质量门禁 | ruff / ruff-format / mypy / pytest（pre-commit + CI） |
| 安全治理 | 敏感凭证清理，test/live 安全边界明确 |

### 3.2 上线前验证流程（近期主线）

策略研究已在 dev/0.5 取得稳定盈利突破，工程侧下一步是**验证策略在接近实盘条件下的稳定性**，再进入生产加固。

| 编号 | 工作项 | 状态 | 说明 |
|------|--------|------|------|
| A10 | test 实时信号观察 | ✅ 基础链路已完成 | 连接实时行情，仅记录信号，不下单 |
| A11 | test / paper trading 语义建模 | 🟡 待做 | DEF-09：test 与 paper 语义未显式建模；全 workspace 搜索 `paper` 零匹配，paper trading 缺失。需区分 test（信号观察）与 paper（维护模拟订单/成交/持仓/账户状态） |
| A12 | paper trading 长时模拟 | ⬜ 待做 | 长时间模拟盘运行，验证稳定性与信号质量 |
| A13 | 统一 TqSdk 单标的与 vn.py 批量回测生命周期 | 🟡 前置障碍待清 | 修 DEF-07：TqSdk 单标的路径缺账户净值序列、逐笔 `pnl`/`commission` 为占位（见第四节）。需先补 bridge 数据缺口，再接统一 run 生命周期 / 日志 / 前端 JSON |
| A14 | 小仓位试运行 | ⬜ 待做 | 满足策略验收后，最小仓位验证实盘链路 |
| A15 | 运行监控 | ⬜ 待做 | 异常通知、断线重连、订单状态监控（与 3.3 通知共用） |

### 3.3 生产加固（S3）

| 编号 | 行动 | 优先级 | 状态 | 说明 |
|------|------|--------|------|------|
| A16 | 实盘风控熔断 | P0 | ⬜ 未开始 | 单日亏损、连续亏损、最大持仓、异常价格保护。当前 `strategy_aspects/risk/` 为策略层止损，`clearing/` 为回测清算，均无生产级实盘熔断模块 |
| A17 | 异常通知 | P0 | ⬜ 未开始 | 微信/邮件/日志告警。全 workspace 无独立 notification 模块 |

### 3.4 基础设施（S4）

| 编号 | 行动 | 优先级 | 状态 | 说明 |
|------|------|--------|------|------|
| A18 | pre-commit 钩子 | P0 | ✅ 已完成 | ruff / ruff-format / mypy / pytest smoke（已升级为按业务域 9 hook） |
| A19 | CI 修复 | P0 | ✅ 已完成 | Python 3.12、ruff、mypy、pytest、覆盖率、前端 lint/test/build 全流程覆盖 |
| A20 | CI 增强：mypy 全量覆盖 | P1 | ✅ 已完成 | ruff（lint+format）已覆盖全仓库；mypy 原仅覆盖 `common/data/backtest/strategies` 4 子包，**经核查 `cli/config/report` 已满足 mypy 严格模式（0 错误）**，已将全部 7 业务域写入 CI（2026-07-10）。注：`workspace/tests/` 暂不纳入 mypy（见下方说明），避免测试注解负担混入源门禁 |
| A21 | CI 增强：覆盖率门槛对齐 | P1 | 🟡 待做 | 当前 CI 门槛 60%，需与 pre-commit 的按域 fail-under 体系对齐 |
| A22 | Docker 支持 | P2 | ⬜ 未开始 | 全仓库无 Dockerfile / docker-compose / Makefile docker 目标 |

### 3.5 策略研发工具增强（S5）

见 2.5。结构诊断字段（A22）已超前落地；diff / 归因 / 蒙特卡洛 / Jupyter（A23–A26）未开始；未使用依赖清理（A27）待做。

---

## 四、已知缺陷（已核实）

| 编号 | 严重度 | 问题 | 位置 | 状态 |
|------|--------|------|------|------|
| DEF-06 | 🟡 | 优化器退化解（零交易 → 最优） | `backtest/optimizer.py` | 🟢 已缓解：`MIN_TRADES_PER_RESULT=10`、`LOW_ACTIVITY_SCORE=-999.0`，`calculate_optimization_score` 对 `total_trades < 10` 直接惩罚。旧文档标"待修复"已过时 |
| DEF-S05 | 🟡 | 信号优先级由 if/elif 顺序隐式定义 | `strategies/ma_strategy.py`（硬止损→软止盈/反转/时间退出→入场的 elif 链） | 🟡 待修复 |
| DEF-07 | 🟡 | TqSdk 路径 `total_return` 存金额而非百分比、逐笔 `commission` 硬编码 0 | `cli/workflows/backtests_run.py`（`_persist_tq_backtest_result`） | 🟡 待修复，归入「3.2 A13 统一 TqSdk 生命周期」一并处理 |
| DEF-08 | 🟢 | 数据库旧回测数据未迁移 | `data/store.py` + `data/migrations.py` | 🟢 已自动迁移：`run_pending_migrations` + 逐版本 `ALTER TABLE` 自动加列，旧库启动即迁移。旧文档"需重跑"说法已过时 |
| DEF-09 | 🟡 | test 与 paper trading 语义未显式建模 | `cli/commands/test.py`、`cli/commands/live.py`、`cli/workflows/realtime.py` | 🟡 部分建模：test/live 已分离；paper trading 缺失，归入「3.2 A11」 |
| DEF-10 | ⚠️ | UTC 时间戳全链路未确证 | 前端时间处理链路 | ⚠️ 待运行时验证：前端有 Unix timestamp 处理，但无显式 UTC 全链路断言 |

---

## 五、工程风险评估

| 风险 | 可能性 | 影响 | 缓解（工程侧） |
|------|--------|------|----------------|
| 参数优化过拟合 | 高 | 高 | 优化器后置且带交易次数下限约束（DEF-06 已缓解）；Walk-Forward 仅在结构成立后启用 |
| 优化器选退化解 | 中 | 高 | `MIN_TRADES_PER_RESULT` 下限 + 低活跃惩罚已落地；继续保留活跃度约束 |
| 实盘链路风险 | 中 | 高 | test/live 分离、paper trading（待做）、小仓位试运行（待做）、风控熔断（待做） |
| 策略未经验证即上线 | 中 | 高 | paper trading 与试运行（3.2）作为近期主线，先于生产加固 |
| 版本叙事脱节 | 高 | 中 | A30：合并关键能力后同步 `pyproject` 版本号与 `CHANGELOG`（见 3.4 / 第一章） |
| TqSdk 数据缺口 | 中 | 中 | DEF-07/A13：先补 bridge 净值与逐笔盈亏，再接统一生命周期，避免接空壳 |
| 监控与告警缺失 | 中 | 高 | A15/A17：paper trading 阶段即应补运行监控与异常通知 |

---

## 六、待办汇总（行动项索引）

| 编号 | 行动 | 域 | 优先级 | 状态 |
|------|------|----|--------|------|
| A10 | test 实时信号观察 | 3.2 | — | ✅ 已完成 |
| A11 | test / paper 语义建模 | 3.2 | P1 | 🟡 待做 |
| A12 | paper trading 长时模拟 | 3.2 | P1 | ⬜ 待做 |
| A13 | 统一 TqSdk / vn.py 生命周期（修 DEF-07） | 3.2 | P1 | 🟡 前置障碍待清 |
| A14 | 小仓位试运行 | 3.2 | P1 | ⬜ 待做 |
| A15 | 运行监控 | 3.2 | P1 | ⬜ 待做 |
| A16 | 实盘风控熔断 | 3.3 | P0 | ⬜ 未开始 |
| A17 | 异常通知 | 3.3 | P0 | ⬜ 未开始 |
| A20 | CI mypy 全量覆盖 | 3.4 | P1 | 🟡 待做 |
| A21 | CI 覆盖率门槛对齐 | 3.4 | P1 | 🟡 待做 |
| A22 | Docker 支持 | 3.4 | P2 | ⬜ 未开始 |
| A23 | 回测结果 diff 工具 | 3.5 | P1 | ⬜ 未开始 |
| A24 | 策略归因分析 | 3.5 | P1 | ⬜ 未开始 |
| A25 | 蒙特卡洛模拟 | 3.5 | P1 | ⬜ 未开始 |
| A26 | Jupyter 探索环境 | 3.5 | P2 | ⬜ 未开始 |
| A27 | 清理未使用依赖 | 3.5 | P2 | 🟡 待做 |
| A30 | 对齐版本号与 CHANGELOG | 全局 | P1 | ✅ CHANGELOG 已回填（0.3.0 / 0.4.0-dev）；纪律：仅合并 main + 有 CHANGELOG 条目时 bump 版本，dev/* 分支不自动等于发布号 |
| DEF-S05 | 信号优先级显式化 | 缺陷 | P2 | 🟡 待修复 |
| DEF-07 | TqSdk 数据缺口修复 | 缺陷 | P1 | 🟡 待修复（并入 A13） |
| DEF-09 | paper trading 语义补建 | 缺陷 | P1 | 🟡 待做（并入 A11） |
| DEF-10 | UTC 全链路验证 | 缺陷 | P2 | ⚠️ 待验证 |
