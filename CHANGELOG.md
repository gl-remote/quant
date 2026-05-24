# Changelog

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.2.0-dev] - 2026-05-24

### 修复

- **backtest 模块审计与修复 (9 项 Bug)**:
  - BT01: 修复 `tq_backtest_engine` 卖出资金双重计算
  - BT02: Walk-Forward 增加 train 集 IS 回测和 IS-OOS 过拟合差距检测
  - BT03: `data_loader` 中 `_qlib` 后缀替换改为 `endswith` 精确匹配末尾
  - BT04: `data_loader` 中 exchange 类型统一为字符串
  - BT05: `profit_factor` 公式修正为行业标准 `gross_profit / abs(gross_loss)`
  - BT06: `stability_score` 增加 `[0,1]` 范围裁剪
  - BT07: `interval_map` 改用 `getattr` 动态获取 vnpy Interval 细分常量
  - BT08: Equity curve 计算优先使用 vnpy 的 `balance` 字段
  - BT09: `BarData` 的 Interval 从硬编码改为参数化传入

### 变更

- plan.md 移除已修复 Bug 列表，仅保留未解决的 15 项缺陷

### 新增

- 策略开发指南 (`doc/strategy-guide.md`)
- 贡献指南 (`CONTRIBUTING.md`)
- API 文档更新：补充 Bridge 接口和信号优先级说明

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