# 项目改进计划

> 版本: 0.2.0 | 最后更新: 2026-05-28 | 主线: 稳定盈利策略研发

---

## 一、项目现状

### 模块架构

```
main.py
├── cli/                    命令接口
├── strategies/             策略核心 (框架无关)
│   ├── core/               ABC + 类型定义
│   ├── bridges/            vnpy / 天勤 桥接
│   └── ma_strategy.py      双均线策略 (已证实无效)
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
| Strategy + Bridge 分离 | 策略核心不依赖任何框架 |
| 复用 vnpy 回测引擎 | 订单撮合/滑点/手续费/逐日盯市 |
| React SPA + 数据预加载 | `window.__DATA__` 内联，支持 `file://` 离线访问 |
| 增量构建缓存 | KlineCache + BuildCache，避免重复计算 |
| UTC 时间戳全链路 | CSV→JSON→前端 Unix timestamp，显示层 `new Date()` 转本地时区 |

---

## 二、版本路线图

| 阶段 | 目标 | 状态 |
|------|------|------|
| **S2** 策略研发 | 多策略迭代至稳定盈利 | ⬜ 未开始 |
| **S3** 生产加固 | 风控熔断 + 通知 | ⬜ 未开始 |
| **S4** 基础设施 | Docker + CI 增强 | ⬜ 未开始 |

### S2: 策略研发（主线）

> ⚠️ 2026-05-28：双均线策略已证实无效。优化器最优点 `sma_short=35, sma_long=35`
> 为零交易退化解——策略不做任何买卖，在对比中被选为最优。

| 编号 | 行动 | 说明 |
|------|------|------|
| A14 | 新策略研发 | RSI / 布林带 / 通道突破，至少 2 个 |
| S2-CONS | 策略约束 | 防止优化器选退化解（如强制 sma_short ≠ sma_long） |
| S2-COMP | 策略横向对比 | 多策略并发回测对比 |
| S2-WF | Walk-Forward 验证 | 对抗参数过拟合 |

**验收标准**: 至少 1 个策略满足夏普 ≥ 0.5、最大回撤 < 20%

### S3: 生产加固

| 编号 | 行动 |
|------|------|
| A15 | 实盘风控熔断 |
| A17 | 异常通知 (微信/邮件) |

### S4: 基础设施

| 编号 | 行动 |
|------|------|
| A16 | Docker 支持 |

---

## 三、已知缺陷

| 编号 | 严重度 | 问题 | 位置 |
|------|--------|------|------|
| DEF-06 | 🔴 | 优化器可选退化解 (零交易 → 最优) | backtest/optimizer.py + `ma_strategy.py` |
| DEF-S04 | 🟡 | 止损/止盈使用固定比例而非 ATR | `ma_strategy.py` |
| DEF-S05 | 🟡 | 信号优先级由 if/elif 顺序隐式定义 | `ma_strategy.py` |

### mypy 类型检查预存问题 (已全部修复 ✅)

| 编号 | 文件 | 行号 | 错误码 | 修复方式 | 状态 |
|------|------|------|--------|----------|------|
| MP-01 | `common/typing.py` | 9 | no-untyped-def | 添加 `f: Any) -> Any:` + `# type: ignore` | ✅ |
| MP-02 | `common/symbol_utils.py` | 42 | no-any-return | `# type: ignore` 移至 return 语句行 | ✅ |
| MP-03 | `common/tqsdk_imports.py` | 22 | no-untyped-def | 添加 `-> None` | ✅ |
| MP-04 | `common/schemas.py` | 66 | misc | `# type: ignore[misc]` 从装饰器移至 def 行 | ✅ |
| MP-05 | `common/schemas.py` | 72 | misc | 同上 | ✅ |
| MP-06 | `common/schemas.py` | 78 | misc | 同上 | ✅ |
| MP-07 | `data/store.py` | 292 | arg-type | `call-overload` → `arg-type`（修正错误码） | ✅ |
| MP-08 | `data/manager.py` | 53 | no-untyped-def | 添加 `-> DataManager` | ✅ |
| MP-09 | `data/manager.py` | 58 | has-type | 添加类属性 `_initialized: bool = False` | ✅ |
| MP-10 | `data/manager.py` | 67 | has-type | 同上 | ✅ |
| MP-11 | `backtest/optimizer.py` | 248 | assignment | 添加 `# type: ignore[assignment]` | ✅ |
| MP-12 | `strategies/utils/loader.py` | 15 | no-untyped-def | 添加 `**strategy_kwargs: Any` + 导入 Any | ✅ |
| MP-13 | `strategies/bridges/__init__.py` | 4 | misc | `# type: ignore[assignment, misc]` | ✅ |
| MP-14 | `strategies/bridges/__init__.py` | 4 | assignment | 同上 | ✅ |
| MP-15 | `strategies/bridges/__init__.py` | 9 | misc | `# type: ignore[assignment, misc]` | ✅ |
| MP-16 | `strategies/bridges/__init__.py` | 9 | assignment | 同上 | ✅ |
| MP-17 | `strategies/__init__.py` | 236 | misc | `# type: ignore[assignment, misc]` | ✅ |
| MP-18 | `strategies/__init__.py` | 236 | assignment | 同上 | ✅ |
| MP-19 | `strategies/__init__.py` | 241 | misc | `# type: ignore[assignment, misc]` | ✅ |
| MP-20 | `strategies/__init__.py` | 241 | assignment | 同上 | ✅ |

---

## 四、风险评估

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 策略无法稳定盈利 | 🔴 已确认 | 高 | MA 已证无效；转向新策略研发 |
| 参数优化过拟合 | 高 | 高 | Walk-Forward 验证 |
| 优化器选退化解 | 🔴 已确认 | 高 | S2-CONS：策略参数约束 |
| 数据窗口过短 | 中 | 中 | 5m/15m 周期补充 |