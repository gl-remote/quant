# 项目改进计划 v0.0.6 归档

## 变更概述

M2（工程化）阶段深度规划：行动项重新编号 A1-A18、增加交付物与验收标准、M1-M4 拆分为详细子任务表格。

## plan.md v0.0.6 完整快照

### 已完成项 (M1 稳定基座)

| 编号 | 内容 |
|------|------|
| A1 | 建立测试框架：pytest + conftest + 86 用例覆盖 4 个核心模块 |
| A2 | 锁定 requirements.txt 依赖版本 (tqsdk==3.0.0, vnpy==3.8.0) |
| — | 中危以上问题清零 (C1-C3, H1-H5, M1-M6 共 14 个) |
| — | 规划行为模式写入 AI_BEHAVIOR_RULES.md |

### 待解决问题

| ID | 问题 | 位置 | 计划 |
|----|------|------|------|
| L1 | 未使用的导入 | backtest_engine.py | M2 阶段清理 |
| L2 | datetime 处理不一致 | 全项目 | M2 阶段统一 |
| L3 | 中英文混用 | 全项目 | 渐进式改善 |

### 待完成行动项

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A3 | 配置 pytest-cov，测量并提升覆盖率至 60%+ | 高 | .coveragerc + 覆盖率报告 |
| A4 | 创建 pyproject.toml：pytest/flake8/mypy 配置 | 高 | pyproject.toml |
| A5 | 添加 .flake8 和 .pylintrc 配置文件 | 高 | .flake8 + .pylintrc |
| A6 | 添加 GitHub Actions CI：lint + test + coverage | 高 | .github/workflows/ci.yml |
| A7 | 清理 L1（未使用导入），统一 L2（datetime 处理） | 中 | 代码清理 PR |
| A8 | 添加 pyproject.toml 项目元数据（打包就绪） | 中 | 可在 PyPI 安装 |
| A9 | 添加 LICENSE 文件 | 中 | LICENSE |
| A10 | 创建 .editorconfig | 低 | .editorconfig |
| A11 | 添加内置参数优化模块（网格搜索） | 中 | optimizer/ 模块 |
| A12 | 回测结果本地可视化（matplotlib） | 中 | visualizer/ 模块 |
| A13 | 支持多品种并发回测 | 中 | 并发引擎改造 |
| A14 | 添加第二个策略示例（RSI/布林带） | 中 | strategies/core/rsi_strategy.py |
| A15 | 实盘风控熔断（日亏损限额、最大回撤限制） | 中 | 风控模块 |
| A16 | 添加 Dockerfile 与 docker-compose | 低 | Dockerfile + docker-compose.yml |
| A17 | 添加异常通知机制 | 低 | 通知模块 (微信/邮件) |
| A18 | 多数据源支持（除天勤外） | 低 | 数据源抽象层 |

### M2 验收标准

- 测试覆盖率 ≥ 60%（含覆盖率报告）
- CI 流水线通过（lint + test + coverage）
- pyproject.toml 包含 pytest/flake8/mypy 配置
- 代码质量工具可正常运行
- L1-L3 全部解决

### 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| vn.py API 变更 | 中 | 高 | 锁定版本；CI 中增加依赖一致性检查 |
| 天勤 SDK 升级不兼容 | 中 | 高 | 锁定版本；数据接口抽象 |
| 回测结果与实盘偏差 | 中 | 高 | 模拟交易验证；完善手续费模型 |
| 无自动化测试 | 已缓解 | — | 86 用例覆盖核心路径；M2 增加 CI 质量门禁 |
| 敏感信息泄露 | 低 | 严重 | .gitignore 排除 conf.local.yaml |
| 策略过拟合 | 中 | 高 | 过拟合评估评分 < 20；样本外测试 |

### 衡量指标

| 指标 | 当前值 | M2 目标 | M3 目标 |
|------|--------|---------|---------|
| 测试用例数 | 86 | 86+ | 100+ |
| 测试覆盖率 | 待测量 | ≥ 60% | ≥ 80% |
| 类型注解覆盖率 | ~70% | ≥ 90% | 100% |
| CI 构建状态 | 无 CI | 通过 | 通过 |
| 代码质量门禁 | 无 | flake8 + pylint 通过 | 持续通过 |
| 支持的策略类型 | 1 | 1 | 2+ |

## 项目状态快照

- 测试：86 用例全部通过 (0.65s)
- 依赖：tqsdk==3.0.0, vnpy==3.8.0, vnpy_ctastrategy==1.2.0
- AI_BEHAVIOR_RULES.md: v0.0.5
- plan.md: v0.0.6
- 下一里程碑: M2 工程化 (覆盖率 60%+ CI/CD)