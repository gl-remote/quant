# Changelog

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
- vn.py 网关适配器、天勤 SDK 网关适配器
- 基础回测跟踪器（BacktestEngine + TradeRecord + BacktestResult）
- 初始审计：17 个问题 + 8 个缺失项 + 路线图