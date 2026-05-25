# Changelog

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.2.0-dev] - 2026-05-25

### 新增

- **统一回测命令**: `backtest` 命令自动选择引擎，单标的用 TqSdk（支持 GUI），批量用 vn.py
- **common/constants.py**: 全局常量字典，消除所有硬编码字符和魔术数字
- **common/formulas.py**: 统一量化计算公式库，20+ 行业标准公式
- **TradingContext.build()**: 交易上下文工厂方法，简化上下文创建
- **快捷运行脚本**: `run.sh` 支持命令验证和详细帮助信息

### 重构

- **CLI 架构重构**: 将 `main.py` 拆分为 `cli/` 子包
  - `cli/main.py`: 参数解析与命令分发
  - `cli/commands/`: 各命令独立模块
  - 删除 `cli/utils.py`，功能迁移到对应核心模块
- **工具函数迁移**:
  - `calculate_fifo_profit` → `common/formulas.py`
  - `load_strategy`, `apply_strategy_config` → `strategies/core/__init__.py`
  - `build_context` → `TradingContext.build()`
  - `setup_db_logging` → `data/database.py`
- **整合回测命令**: 删除 `tq_backtest.py`，功能整合到 `backtest.py`

### 修复

- **backtest 模块第一轮审计与修复 (9 项 Bug)**:
  - BT01: 修复 `tq_backtest_engine` 卖出资金双重计算
  - BT02: Walk-Forward 增加 train 集 IS 回测和 IS-OOS 过拟合差距检测
  - BT03: `data_loader` 中 `_qlib` 后缀替换改为 `endswith` 精确匹配末尾
  - BT04: `data_loader` 中 exchange 类型统一为字符串
  - BT05: `profit_factor` 公式修正为行业标准 `gross_profit / abs(gross_loss)`
  - BT06: `stability_score` 增加 `[0,1]` 范围裁剪
  - BT07: `interval_map` 改用 `getattr` 动态获取 vnpy Interval 细分常量
  - BT08: Equity curve 计算优先使用 vnpy 的 `balance` 字段
  - BT09: `BarData` 的 Interval 从硬编码改为参数化传入
- **backtest 模块第二轮审计与修复 (6 项缺陷)**:
  - DEF-BT16: `np.std` 改用 `ddof=1` 样本标准差；零波动正收益返回 999.0
  - DEF-BT17: 回撤守卫 `peak != 0` → `peak > 0`，修复负权益场景
  - DEF-BT18: `walk_forward_split_by_ratio` 中 `test_size` 兜底消除 int 截断丢行
  - DEF-BT19: `_run_backtest` 中 `self.context` 赋值改为局部变量，消除副作用
  - DEF-BT20: 多次买入时 `entry_price` 改为加权平均成本价
  - DEF-BT21: `comparison.py` max_drawdown 格式化归一化 `>1` 时 `/100`
- **第三次全量审计修复 (8 项)**:
  - BUG-01: 修复 tq-backtest 盈亏计算笛卡尔积配对错误 (`3ea2d3e`)
  - BUG-02: TQBacktestEngine 新增手续费率/滑点扣减 (`7ce71cb`)
  - BUG-03: 移除 `format_pct` 启发式归一化，在 DB 层统一处理 (`d1589b9`)
  - BUG-04: `_run_backtest` 增加逐窗口 try/except 保护 (`d1589b9`)
  - BUG-05: 引入方向/开平常量消除买卖统计混淆 (`f889e16`)
  - BUG-06: Walk-Forward 窗口数公式替换为迭代验证算法 (`500312b`)
  - BUG-07: `annual_return_abs` 重命名为 `annual_return_ratio` 消除命名误导 (`fc4ca15`)
  - BUG-08: 修复 `config_manager` 合并表达式静默修改源字典 (`3d505cf`)

### 变更

- plan.md 移除已修复 Bug 列表，仅保留未解决的缺陷
- **移除 `.plan/*.log.md` 归档**，重要改动统一记录在 CHANGELOG.md
- AI_BEHAVIOR_RULES.md: 更新行为规范，CHANGELOG.md 替代 .plan/ 归档
- **回测执行与报告解耦**: 回测结果写入 SQLite 数据库，报告通过独立 `report` 命令生成
- **提取 common/ 通用纯函数模块**: `metrics.py` + `stats.py` + `formatting.py`，消除 backtest/report 间的代码重复
- README.md: 更新项目结构和命令行参考
- 测试数量从 131 增加到 163 个

---

## [0.1.0] - 2026-05-24

### 新增

- **回测引擎**: vn.py 三阶段回测流水线（训练/验证/测试集划分、独立回测、对比分析）
- **过拟合评估**: 收益递减、风险递增、稳定性分析、综合评分（0-100）
- **多品种并发回测**: `--pattern` 正则匹配 + `--parallel` 多线程并行 + 合并报告
- **数据导出**: 天勤 SDK → Qlib CSV，支持增量合并和 `--force` 强制覆盖
- **CLI 系统**: `export` / `test` / `backtest` / `tq-backtest` / `live` 五个子命令
- **配置管理**: YAML 分层合并（conf.yaml + conf.local.yaml），支持本地密钥覆盖
- **操作日志**: SQLite 持久化操作日志（export_metadata + operation_logs）
- **CI/CD**: GitHub Actions 自动化 lint + test + coverage
- **开发体验**: .editorconfig、统一 pyproject.toml（pytest/flake8/pylint/mypy/coverage）
- **项目治理**: plan.md 行动指南 + .plan/ 归档体系 + AI_BEHAVIOR_RULES.md

### 变更

- pyproject.toml 统一所有工具配置，删除冗余 pytest.ini / .flake8 / .pylintrc / .coveragerc
- conf.yaml / conf.example.yaml / conf.local.yaml 归入 config/ 目录
- 根目录从 17 个文件瘦身至 9 个

### 修复

- datetime 处理统一使用 `.strftime()` 显式格式化，替换不稳定的 `str()`

---

## [0.0.1] - 2026-05-24

### 新增

- 项目初始化：天勤均线交叉策略交易系统
- 策略核心：MovingAverageStrategy（SMA 金叉/死叉 + 止损止盈）
- vn.py 桥接器、天勤 SDK 桥接器
- 基础回测跟踪器（BacktestEngine + TradeRecord + BacktestResult）
- 初始审计：17 个问题 + 8 个缺失项 + 路线图