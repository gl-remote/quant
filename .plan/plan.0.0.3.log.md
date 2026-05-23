# 项目改进计划 v0.0.3 归档

> 版本: 0.0.3 | 生成日期: 2026-05-24 | 状态: 当前版本

---

## 相对于 v0.0.2 的变更

### 已修复问题 (14 项)

#### 严重 (3) — ✅ 全部已修复

| ID | 修复方式 |
|----|---------|
| C1 | `run.sh` / `activate_env.sh`：硬编码路径 → `CONDA_PREFIX` 环境变量 + `python` 回退 |
| C2 | `activate_env.sh`：`--mode backtest` → 子命令格式 `backtest`, `export`, `live` |
| C3 | `backtest_engine.py`：降级引擎手动 SMA → 复用 `MaStrategyCore` 方法 |

#### 高危 (5) — ✅ 全部已修复

| ID | 修复方式 |
|----|---------|
| H1 | `config_manager.py`：`validate_config` 新增回测参数校验 |
| H2 | `backtest_engine.py`：`VnpyBacktestEngine.__init__` 新增 5 项 ValueError 校验 |
| H3 | `main.py`：3 处 `traceback.print_exc()` → `logger.error(..., exc_info=True)` |
| H4 | `tqsdk_gateway.py`：4 个向后兼容方法添加 `DeprecationWarning` |
| H5 | `data_loader.py`：提取 `parse_symbol_exchange()` 工具函数 |

#### 中危 (6) — ✅ 全部已修复

| ID | 修复方式 |
|----|---------|
| M1 | `comparison.py` `_safe_name`：增加 `isinstance` 类型防护 |
| M2 | `report.py` `_extract_performance_metrics`：空统计返回默认值 + warning |
| M3 | `tqsdk_gateway.py`：模块级 `_tq_imports` dict → `TqsdkImports` 类 |
| M4 | `database.py` / `vnpy_gateway.py` / `tqsdk_gateway.py`：关键公开 API 添加类型注解 |
| M5 | `.gitignore`：移除重复条目 |
| M6 | `main.py`：`logging.basicConfig` 从 `conf.yaml` 读取 |

---

## 仍在进行中

### 剩余低危问题 (3)

| ID | 问题 | 位置 |
|----|------|------|
| L1 | 未使用的导入 | backtest_engine.py |
| L2 | datetime 处理不一致 | 全项目 |
| L3 | 中英文混用 | 全项目 |

### 缺失项目元素 (8 类，未变更)

测试框架、CI/CD、代码质量配置、打包配置、版本锁定、许可证、编辑器配置、Docker

### 功能缺失 (7 项，未变更)

多品种回测、可视化、参数优化、风控、多策略、通知、多数据源

---

## AI_BEHAVIOR_RULES 同步

`AI_BEHAVIOR_RULES.md` 同步更新至 v0.0.3，新增规则：

- 4.2 — 核心策略复用（强制使用 `MaStrategyCore`）
- 4.6 — 构造函数输入校验
- 4.7 — 模块状态管理（禁止模块级可变状态）
- 4.8 — 工具函数抽象（`parse_symbol_exchange`）
- 第十章 — 规划文档归档规范（`.plan/` 目录结构）

---

## 四阶段路线图（进度）

| 阶段 | 目标 | 状态 |
|------|------|------|
| M1 稳定基座 | 降级引擎统一 ✅ / 脚本可移植 ✅ / 输入校验 ✅ / 测试覆盖率 | 测试待启动 |
| M2 工程化 | CI/CD / 类型注解 ~70% / 版本锁定 | 进行中 |
| M3 功能增强 | 参数优化、可视化、多策略 | 未开始 |
| M4 生产就绪 | Docker、监控告警 | 未开始 |