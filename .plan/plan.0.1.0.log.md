# 项目改进计划 v0.1.0 归档

## 0.1.0 里程碑

0.1.0 是项目从 Alpha 进入 Beta 的首个里程碑版本。自项目初始化以来，
核心功能已完备，工程化体系已建立。

### 0.1.0 版本变更

- pyproject.toml: 0.0.3 → 0.1.0, Alpha → Beta
- 新增 CHANGELOG.md 变更日志
- AI_BEHAVIOR_RULES.md: 0.0.6 → 0.1.0
- README.md: 添加版本徽章、更新功能描述
- plan.md: 大版本归档重写

### 0.1.0 交付清单

| 维度 | 内容 |
|------|------|
| 策略引擎 | 均线交叉 + vn.py 三阶段回测 + 过拟合评估 |
| 并发回测 | 多品种 regex 匹配 + ThreadPoolExecutor 并行 |
| 数据管道 | 天勤 SDK → Qlib CSV → 增量合并 / 强制覆盖 |
| 实盘交易 | 天勤实盘/模拟 + Web GUI |
| CLI | export / test / backtest / tq-backtest / live |
| 配置 | YAML 分层合并 (conf.yaml + conf.local.yaml) |
| 日志 | SQLite 操作日志 + 元数据 |
| 测试 | 146 用例, 85% 覆盖率 |
| CI/CD | GitHub Actions lint + test |
| 工程化 | pyproject.toml 统一配置, .editorconfig, LICENSE |
| 文档 | README + doc/ 体系 + CHANGELOG |
| 治理 | plan.md + .plan/ 归档 + AI_BEHAVIOR_RULES.md |

### 下一阶段 (M3)

- A11: 参数优化模块（网格搜索）
- A12: 回测结果可视化（matplotlib）
- A14: 第二个策略示例（RSI/布林带）
- A15: 实盘风控熔断

### 项目状态快照

- 测试: 146 用例, 85% 覆盖率
- AI_BEHAVIOR_RULES.md: 0.1.0
- pyproject.toml: 0.1.0
- 当前状态: v0.1.0 Beta