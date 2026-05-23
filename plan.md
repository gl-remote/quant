# 项目改进计划

> 版本: 2.0.0 | 生成日期: 2026-05-24 | 基于对代码库的全面审计

---

## 一、缺失项目元素

### 1.1 工程基础设施（缺失）

| 元素 | 现状 | 影响 | 优先级 |
|------|------|------|--------|
| 测试框架与用例 | 无 `tests/` 目录，零测试覆盖 | 重构风险高，回归验证无保障 | 紧急 |
| CI/CD 流水线 | 无 `.github/workflows`、无 Jenkinsfile | 自动化检查缺失，合并不受控 | 高 |
| 代码质量工具配置 | `pytest/flake8/pylint` 在 requirements.txt 中但无对应配置文件 | 工具无法生效 | 高 |
| 项目打包配置 | 无 `pyproject.toml` 或 `setup.py` | 无法 `pip install`，分发困难 | 中 |
| 版本锁定 | requirements.txt 使用 `>=` 宽松约束 | 依赖升级可能引入不兼容变更 | 高 |
| 许可证文件 | 无 `LICENSE` | 开源合规风险 | 中 |
| 编辑器配置 | 无 `.editorconfig` | 团队协作格式不一致 | 低 |
| Docker 支持 | 无 `Dockerfile` | 环境复现依赖手动操作 | 低 |

### 1.2 文档缺失

| 元素 | 说明 |
|------|------|
| 变更日志 (CHANGELOG.md) | 无版本变更记录 |
| 贡献指南 (CONTRIBUTING.md) | 无代码贡献规范 |
| 策略开发指南 | 仅 FAQ 中简要提及，无完整接入流程 |

### 1.3 功能缺失

| 功能 | 说明 |
|------|------|
| 多品种并发回测 | 当前仅支持单品种逐一执行 |
| 回测结果可视化 | 依赖天勤 GUI（需联网），无本地 matplotlib 图表生成 |
| 参数优化/网格搜索 | 需用户自行编写循环脚本，无内置超参搜索 |
| 实时风控监控 | 实盘模式无最大回撤熔断、日亏损限额等保护 |
| 多策略支持 | 仅实现均线交叉，架构支持扩展但无第二个策略示例 |
| 通知/告警 | 无异常通知机制（邮件、微信等） |
| 多数据源 | 仅支持天勤，无本地文件增量更新或第三方源 |

---

## 二、现有问题清单

### 2.1 严重 (Critical)

| ID | 问题 | 位置 | 说明 |
|----|------|------|------|
| C1 | 脚本中硬编码绝对路径 | [run.sh](file:///Users/REDACTED_API_KEY/Documents/src/quant/run.sh), [activate_env.sh](file:///Users/REDACTED_API_KEY/Documents/src/quant/activate_env.sh) | Python 路径 `/usr/local/Caskroom/miniconda/base/envs/quant_trading/bin/python` 仅 Mac 有效，conda 路径依赖机器 |
| C2 | 脚本引用过时 CLI 格式 | [activate_env.sh](file:///Users/REDACTED_API_KEY/Documents/src/quant/activate_env.sh) | 提示信息使用 `--mode backtest`（已废弃），应为子命令 `backtest` |
| C3 | 降级引擎重复实现 SMA 逻辑 | [backtest_engine.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/backtest_engine.py) `_run_fallback_backtest` | 手动计算 SMA 而非使用 `MaStrategyCore.calculate_sma()`，与核心算法不一致 |

### 2.2 高危 (High)

| ID | 问题 | 位置 | 说明 |
|----|------|------|------|
| H1 | 配置文件验证不完整 | [config_manager.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/config/config_manager.py) `validate_config` | 仅校验策略参数，未校验回测参数（手续费率、滑点、合约乘数合法性） |
| H2 | 引擎构造函数无输入校验 | [backtest_engine.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/backtest_engine.py) `VnpyBacktestEngine.__init__` | commission_rate 可为负数，contract_size 可为 0，无保护 |
| H3 | 异常处理不一致 | [main.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/main.py) 多处 | 混用 `import traceback; traceback.print_exc()` 和 `logger.error()`，无统一异常处理策略 |
| H4 | Tqsdk 网关向后兼容接口脆弱 | [tqsdk_gateway.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/gateways/tqsdk_gateway.py) | `calculate_sma`/`execute_buy`/`execute_sell` 等方法命名暗示已废弃但 main.py 仍调用 |
| H5 | 交易所代码解析依赖字符串操作 | [data_loader.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/data_loader.py), [backtest_engine.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/backtest_engine.py) | `symbol.split('.')` 假设品种代码格式为 `EXCHANGE.product`，非标准品种可能解析错误 |

### 2.3 中危 (Medium)

| ID | 问题 | 位置 | 说明 |
|----|------|------|------|
| M1 | 对比分析模块不安全取值 | [comparison.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/comparison.py) `_safe_name` | 嵌套 `.get()` 链在极端情况下可产生无意义名 "unknown" |
| M2 | 报告模块静默处理缺失统计 | [report.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/report.py) | `_extract_performance_metrics` 用 `.get()` 兜底 0，可能掩盖真实统计缺失 |
| M3 | 模块级可变全局状态 | [tqsdk_gateway.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/gateways/tqsdk_gateway.py) | `_tq_imports` 字典作为模块级可变状态，多线程下不安全 |
| M4 | 类型注解不完整 | 全项目 | 多数公开方法参数无类型注解，依赖文档字符串描述 |
| M5 | `.gitignore` 重复条目 | [.gitignore](file:///Users/REDACTED_API_KEY/Documents/src/quant/.gitignore) | 末尾 `.quant_shared_data` 和 `.quant_shared_data` 重复 |
| M6 | 日志格式硬编码 | [main.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/main.py) | `logging.basicConfig` 格式写死在代码中，conf.yaml 中的 `system.logging.format` 未生效 |

### 2.4 低危 (Low)

| ID | 问题 | 位置 | 说明 |
|----|------|------|------|
| L1 | 未使用的导入 | [backtest_engine.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/backtest_engine.py) | `Tuple` 从 typing 导入但未使用 |
| L2 | datetime 处理不一致 | 全项目 | 有时用 `pd.to_datetime`，有时用 `.strftime()`，有时直接用字符串比较 |
| L3 | 中英文混用 | 全项目 | 代码注释、日志消息、docstring 中英文混用，风格不统一 |

---

## 三、行动项与优先级

### 3.1 第一阶段：稳定性加固（预计 2-4 周）

| 编号 | 行动 | 涉及文件 | 优先级 | 关联问题 |
|------|------|---------|--------|---------|
| A1 | 建立测试框架，为核心模块编写单元测试 | 新建 `tests/` | 紧急 | 缺失项 |
| A2 | 修复降级引擎，复用 `MaStrategyCore` 替代手写 SMA | `backtest_engine.py` | 严重 | C3 |
| A3 | 修复脚本硬编码路径为相对路径或环境变量 | `run.sh`, `activate_env.sh` | 严重 | C1 |
| A4 | 更新脚本中的过时 CLI 提示 | `activate_env.sh` | 严重 | C2 |
| A5 | 添加 `VnpyBacktestEngine` 构造函数参数校验 | `backtest_engine.py` | 高 | H2 |
| A6 | 扩展 `ConfigManager.validate_config` 覆盖回测参数 | `config_manager.py` | 高 | H1 |
| A7 | 统一异常处理策略，建立自定义异常类 | `main.py`, 新建 | 高 | H3 |

### 3.2 第二阶段：工程质量提升（预计 4-6 周）

| 编号 | 行动 | 涉及文件 | 优先级 | 关联问题 |
|------|------|---------|--------|---------|
| A8 | 添加 `pyproject.toml`，配置 pytest/flake8/mypy | 新建 | 高 | 缺失项 |
| A9 | 锁定 requirements.txt 依赖版本（使用 `==` 或 `~=`） | `requirements.txt` | 高 | 缺失项 |
| A10 | 添加 GitHub Actions CI（lint + test） | 新建 `.github/` | 高 | 缺失项 |
| A11 | 为所有公开方法补充类型注解 | 全项目 | 中 | M4 |
| A12 | 重构交易所代码解析为独立工具函数 | `data_loader.py`, `backtest_engine.py` | 高 | H5 |
| A13 | 清理 Tqsdk 网关向后兼容方法 | `tqsdk_gateway.py`, `main.py` | 高 | H4 |
| A14 | 让日志格式通过 conf.yaml 可配置 | `main.py`, `conf.yaml` | 中 | M6 |
| A15 | 修复 `.gitignore` 重复条目 | `.gitignore` | 低 | M5 |

### 3.3 第三阶段：功能扩展（预计 6-12 周）

| 编号 | 行动 | 说明 | 优先级 |
|------|------|------|--------|
| A16 | 添加内置参数优化模块（网格搜索） | 减少用户手动编写循环脚本的成本 | 中 |
| A17 | 实现回测结果本地可视化（matplotlib） | K线叠加信号、资金曲线图、回撤热力图 | 中 |
| A18 | 支持多品种并发回测 | 批量执行并聚合对比结果 | 中 |
| A19 | 添加第二个策略示例（如 RSI 或布林带） | 验证网关适配器架构的可扩展性 | 中 |
| A20 | 实盘添加风控熔断（日亏损限额、最大回撤限制） | 保护实盘资金安全 | 中 |
| A21 | 添加 Dockerfile 与 docker-compose | 标准化运行环境 | 低 |
| A22 | 添加异常通知机制（日志文件 + Webhook） | 关键事件主动推送 | 低 |

---

## 四、开发路线图

### Milestone 1: 稳定基座（目标：2026-06 中旬）

- ✅ 核心模块测试覆盖率达到 60%+
- ✅ 降级引擎与核心策略逻辑统一
- ✅ 所有脚本可移植、无硬编码路径
- ✅ 输入参数校验覆盖所有公开 API

### Milestone 2: 工程化（目标：2026-07 下旬）

- ✅ CI 流水线运行（lint + test + type check）
- ✅ 完整的类型注解
- ✅ 依赖版本锁定
- ✅ pyproject.toml 标准化

### Milestone 3: 功能增强（目标：2026-09）

- ✅ 参数优化模块上线
- ✅ 本地可视化图表可用
- ✅ 至少两个策略类型可运行
- ✅ 实盘风控熔断就绪

### Milestone 4: 生产就绪（目标：2026-12）

- ✅ Docker 一键部署
- ✅ 异常通知机制
- ✅ 多品种并发回测
- ✅ 完整的监控与告警

---

## 五、风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| vn.py API 变更导致网关适配器失效 | 中 | 高 | 锁定 vnpy 版本；降级引擎作为后备 |
| 天勤 SDK 版本升级不兼容 | 中 | 高 | 锁定 tqsdk 版本；将数据获取抽象为独立接口层 |
| 回测结果与实盘偏差过大 | 中 | 高 | 在实盘前执行模拟交易验证；完善滑点和手续费模型 |
| 单品种硬编码导致扩展困难 | 低 | 中 | 当前架构已支持品种参数化，扩展成本低 |
| 无自动化测试导致回归问题 | 高 | 高 | Milestone 1 优先建立测试体系 |
| 敏感信息（API Key）泄露 | 低 | 严重 | 确认 .gitignore 排除 conf.local.yaml；添加 pre-commit hook 扫描 |
| 策略过拟合导致实盘亏损 | 中 | 高 | 系统已有过拟合评估（0-100 评分），建议实盘前评分 < 20 |

---

## 六、衡量指标

建议采用以下指标跟踪项目健康度：

| 指标 | 当前值 | 目标 (M1) | 目标 (M3) |
|------|--------|-----------|-----------|
| 测试覆盖率 | 0% | 60% | 80%+ |
| 类型注解覆盖率 | ~40% | 90% | 100% |
| CI 构建状态 | 无 CI | 通过 | 通过 |
| 支持的策略类型 | 1 | 1 | 2+ |
| 文档完整度 | 完善 ✅ | — | — |
| Pylint 评分 | 未测量 | 8.0+ | 9.0+ |

---

## 七、版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.0.0 | 2026-05-24 | 同步 [AI_BEHAVIOR_RULES.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/AI_BEHAVIOR_RULES.md) v2.0.0 更新：新增 A20 实盘风控熔断行动项；新增 M6 日志格式硬编码问题；添加版本号与变更日志章节；文档间交叉引用 |
| 1.0.0 | 2026-05-24 | 初始版本：完整审计 16 个源文件，识别 17 个问题及 8 类缺失元素，制定四阶段路线图 |