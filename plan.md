# 项目改进计划

> 版本: 0.0.9 | 生成日期: 2026-05-24 | 当前阶段: M3 功能增强

---

## 一、待完成行动项

### M3: 功能增强（当前阶段）

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A11 | 添加内置参数优化模块（网格搜索） | 中 | `optimizer/` 模块 |
| A12 | 回测结果本地可视化（matplotlib） | 中 | `visualizer/` 模块 |
| A13 | 支持多品种并发回测 | 中 | 并发引擎改造 |
| A14 | 添加第二个策略示例（RSI/布林带） | 中 | `strategies/core/rsi_strategy.py` |
| A15 | 实盘风控熔断（日亏损限额、最大回撤限制） | 中 | 风控模块 |

**M3 验收标准**：
- 支持 ≥2 种策略类型（当前 1 种）
- 支持多品种并发回测
- 具备本地可视化能力
- 具备实盘风控熔断

### M4: 生产就绪

| 编号 | 行动 | 优先级 | 交付物 |
|------|------|--------|--------|
| A16 | 添加 Dockerfile 与 docker-compose | 低 | `Dockerfile` + `docker-compose.yml` |
| A17 | 添加异常通知机制 | 低 | 通知模块 (微信/邮件) |
| A18 | 多数据源支持（除天勤外） | 低 | 数据源抽象层 |

---

## 二、当前缺失

### 2.1 工程基础设施

| 元素 | 现状 | 优先级 |
|------|------|--------|
| Docker 支持 | 无 `Dockerfile` | 低 |

### 2.2 文档缺失

| 元素 | 说明 |
|------|------|
| 变更日志 (CHANGELOG.md) | 无版本变更记录 |
| 贡献指南 (CONTRIBUTING.md) | 无代码贡献规范 |
| 策略开发指南 | 仅 FAQ 中简要提及 |

### 2.3 功能缺失

| 功能 | 说明 |
|------|------|
| 多品种并发回测 | 仅支持单品种 |
| 回测结果可视化 | 无本地 matplotlib 图表 |
| 参数优化/网格搜索 | 无内置超参搜索 |
| 实时风控监控 | 无回撤熔断、日亏损限额 |
| 多策略支持 | 仅均线交叉一个策略 |
| 通知/告警 | 无异常通知机制 |
| 多数据源 | 仅支持天勤 |

---

## 三、风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| vn.py API 变更 | 中 | 高 | 锁定版本 (3.8.0)；CI 中增加依赖一致性检查 |
| 天勤 SDK 升级不兼容 | 中 | 高 | 锁定版本 (3.0.0)；数据接口抽象 |
| 回测结果与实盘偏差 | 中 | 高 | 模拟交易验证；完善手续费模型 |
| 敏感信息泄露 | 低 | 严重 | .gitignore 排除 conf.local.yaml |
| 策略过拟合 | 中 | 高 | 过拟合评估评分 < 20；样本外测试 |

---

## 四、衡量指标

| 指标 | 当前值 | M3 目标 | M4 目标 |
|------|--------|---------|---------|
| 测试用例数 | 127 | 150+ | 150+ |
| 测试覆盖率 | 82% | ≥ 80% | ≥ 85% |
| 类型注解覆盖率 | ~70% | ≥ 90% | 100% |
| CI 构建状态 | 已配置 | 通过 | 通过 |
| 代码质量门禁 | flake8+pylint 已配置 | 通过 | 持续通过 |
| 支持的策略类型 | 1 | 2+ | 2+ |

---

## 五、版本记录

| 版本 | 日期 | 变更 | 归档 |
|------|------|------|------|
| 0.0.9 | 2026-05-24 | 根目录瘦身：删除 5 冗余文件 + conf*.yaml 归入 config/ | [plan.0.0.9.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.9.log.md) |
| 0.0.8 | 2026-05-24 | M2 工程化完成：L1-L3 解决，A3-A10 完成，覆盖率 82%，M3 启动 | [plan.0.0.8.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.8.log.md) |
| 0.0.7 | 2026-05-24 | 归档优先规范落地：重写为干净行动指南，移除所有已完成项 | [plan.0.0.7.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.7.log.md) |
| 0.0.6 | 2026-05-24 | M2 阶段细化：行动项重新编号、增加交付物与验收标准 | [plan.0.0.6.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.6.log.md) |
| 0.0.5 | 2026-05-24 | 规划行为模式建立；版本锁定完成；风险重新评估 | [plan.0.0.5.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.5.log.md) |
| 0.0.4 | 2026-05-24 | 建立测试框架：86 用例，4 核心模块，pytest.ini 配置 | [plan.0.0.4.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.4.log.md) |
| 0.0.3 | 2026-05-24 | 14 个中危以上问题全部修复 | [plan.0.0.3.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.3.log.md) |
| 0.0.2 | 2026-05-24 | AI_BEHAVIOR_RULES 同步与版本追踪 | [plan.0.0.2.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.2.log.md) |
| 0.0.1 | 2026-05-24 | 初始审计：17 问题 + 8 缺失 + 路线图 | [plan.0.0.1.log.md](file:///Users/REDACTED_API_KEY/Documents/src/quant/.plan/plan.0.0.1.log.md) |