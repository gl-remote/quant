# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.4.0-dev] - 2026-07-10（开发周期，未发布）

> 当前包版本基线。`dev/0.5`、`dev/0.6` 为研究分支标签，不自动等于发布版本；本开发周期内的策略研究进展（如 dev/0.5 达成稳定盈利）合并至 main 时**不做版本号 bump**，仅在里程碑中记录。

### 新增
- `strategies/strategy_aspects` 提升为正式包，实现 advisory direction DSL，重构 MA 策略
- MA 策略加入交易冷却（trade cooldown）
- DataFeed 聚合：从 1m 聚合高周期 bar
- LoadHistory / 聚合 / 反序列化环节的防御性日志

### 改动
- DataFeed / PeriodData 重构：指标计算从 DataFeed 下沉到 PeriodData；移除全局指标注册表（直接传 func）；统一 `IndicatorSpec` 并优化窗口计算
- bridges 统一：backtest / live 桥接通过 DataFeed 公共 API 统一
- 指标库：以 `ta-lib` 替换 `pandas-ta`，消除指标计算对 pandas index 的依赖
- 测试目录重构为按源布局镜像（mirror source layout）
- 信号终结（signal finalization）上移到 `Strategy` 基类；`data_requirements` 默认实现移至基类
- 类型与可维护性：大量 mypy 类型标注修复、以 `Literal` 注解消除 `cast()`、抽取 `EventManager`、统一指标/聚合/反序列化路径
- 工程文档重组

### 修复
- 并行回测报告管线稳定性
- forming bar 指标缓存被清空后无法重新计算
- interceptor periods 注册与 `ZeroDivisionError`
- walk-forward 解包与类型标注问题

### 里程碑
- 2026-07-10：`dev/0.5`（策略研究：达成稳定盈利）合并至 main（commit `a7e1724`）；包版本维持在 `0.4.0-dev`，未做发布号 bump

---

## [0.3.0] - 2026-06-12

> 策略研发与实时验证基础设施完成（非"策略已完成"）。详见当时路线图 S2-A。

### 新增
- 回测链路：vnpy 批量回测、参数优化、Walk-Forward 工具链可用
- 实时链路：tqsdk test / live 路径打通（test 使用实时行情但不下单，live 才下单）
- DataFeed：多周期 PeriodData、指标注册、初始化全量计算、实时单周期增量触发
- 指标一致性：backtest / test / live 复用同一套指标计算机制，并补充覆盖测试
- 报告系统：React SPA 报告、图表 / 表格 / 主题体系、数据预加载与展示增强
- 质量门禁：ruff / ruff-format / mypy / pytest smoke（pre-commit 触发）
- 安全治理：清理敏感凭证历史，test / live 形成明确安全边界

---

## [0.2.1-dev] - 2026-06-06

### 新增
- **vnpy 全量统计字段**: backtests 表 +15 字段（`total_net_pnl`, `total_commission`, `total_slippage`, `profit_days`, `loss_days`, `ewm_sharpe`, `rgr_ratio` 等），backtest_daily 表 +4 字段（`turnover`, `commission`, `slippage`, `trade_count`）
- **前端展示扩展**: BacktestDetail 新增净盈亏/手续费/滑点/EWM夏普/盈利天数等指标卡片；SymbolTable 新增净盈亏/手续费/盈利天数 3 列；MetricCards 新增总净盈亏/总手续费汇总卡
- **文字报告**: 新增「盈亏汇总」「交易日统计」两个 section
- **一致性校验**: 新增 profit_days 匹配、commission 对账两项校验

### 修复
- **逐笔 PnL 从毛利改为净盈亏**: FIFO 配对逻辑补算 commission（`price × volume × size × rate`）和 slippage（`volume × size × slip`），pnl = 毛利 - commission - slippage
- **Commission 硬编码修复**: 逐笔交易 commission 从硬编码 `0.0` 改为真实值
- **win_trades / loss_trades 统计修正**: 排除 pnl=0 的开仓记录，只统计有实际盈亏的平仓交易（之前开仓被归入亏损导致胜率偏低）
- **vnpy 字段格式误用**: 前端/文字报告中 `total_return`（vnpy 已是百分比）不再错误乘以 100；`max_drawdown`（vnpy 是绝对金额）不再用百分比格式化
- **store 层 `_normalize_max_dd()`**: 移除了错误的 v/100 归一化逻辑，直接存储 vnpy 返回的金额原值
- **store 层 win_rate 不一致**: `get_backtests_for_run` 补上 `* 100`，与 `get_run_summary` 保持一致
- **text.py SyntaxError**: 列表 `]` 提前关闭导致文字报告不可用
- **store.py SELECT 缺列**: `get_run_summary` 补了 8 列新字段映射

### 改动
- **字段语义变更**: `pnl`（逐笔）含义从"毛利"变为"净盈亏"；`win_rate` 分母从"总成交笔数"变为"有盈亏笔数"
- **数据库自动迁移**: store._init_tables() 支持 ALTER TABLE 自动加列，旧库启动时无需手动 DDL

### 已知限制
- TqSdk 路径的 `total_return` 存的是绝对金额而非百分比（与 vnpy 路径语义不同），混库时需注意
- TqSdk 路径的逐笔 commission 仍为硬编码 0.0，后续单独处理

---

## [0.2.0-dev] - 2026-05-27

### 新增
- **Runs 追踪系统**: `runs`/`run_studies` 表，每次回测有 run_id，输出到 `project_data/reports/runs/r{id}/`
- **Jinja2 模板引擎**: `report/` 重构为 `builder.py` + `queries/` + `templates/` 三层分离
- **backtest_params 拆表**: 替代 `params_json` 列，参数可 SQL 查询按品种/按值筛选
- **全量单回测报告**: 回测时生成全部品种的 `backtest_N.html`，非仅一份
- **页面板块 ID**: `[NAV]` `[BT-SUM]` `[OPT-CONV]` 等统一前缀，精确定位
- **看板系统**: `project_data/reports/index.html` 导航页 + run 详情看板 (回测 + 优化)
- **单回测多板块**: `[BT-METRICS]` + `[BT-EQ]` + `[BT-TRADES]` 三板块
- **本地前端资源**: `project_data/reports/assets/`，零网络请求
- **多数据源抽象**: `data/datasource/` — tqsdk / akshare 切换

### 修复
- `clean_data.sh` 白名表单精确清理，保留 `export_metadata` + CSV
- `report --id` 自动归入 `project_data/reports/runs/r{run}/` 目录
- `test-ma.sh` PYTHON_PATH 路径嵌套 bug
- plotly CDN 不可用 → 本地文件

### 移除
- `report/dashboard.py` → `builder.py` + 模板
- `report/_html.py` → `templates/single_report.html`
- `backtests.params_json` 列 → `backtest_params` 表

### 改动
- `fetch_data.py` 默认跳过已有数据，`--force` 强制重拉
- `tools/` 目录集中存放 shell 脚本
- `[data].provider` 与 `[backtest].provider` 职责分离
- `serialize_strategy_params` 返回值 `str` → `dict`

---

## [0.1.0] - 2026-05-25

### 新增
- 项目初始化：vnpy 回测引擎 + 双均线策略
- CLI 命令系统：export / test / backtest / report / live
- Optuna 参数优化 (GridSampler + TPESampler)
- Plotly 可视化 + HTML 报告
- Pandera Schema 数据校验
- peewee ORM + SQLite 持久化
