# 项目改进计划 v0.0.4 归档

## 变更概述

建立测试框架，覆盖 4 个核心模块共 86 个测试用例，全部通过。

## 新增文件

| 文件 | 说明 |
|------|------|
| `pytest.ini` | pytest 配置：测试路径、命名规则、标记（core/config/loader/database/slow） |
| `tests/conftest.py` | 共享 fixtures：sample_closes, trading_config_dict, base_config_dict, sample_kline_df, temp_config_file, temp_db_path |
| `tests/test_ma_strategy.py` | 35 用例：SMA 计算、金叉死叉、止盈止损、on_bar_signal 集成、入场出场、仓位计算、绩效统计、默认配置 |
| `tests/test_config_manager.py` | 18 用例：配置加载、交易/回测/数据/导出/日志配置获取、validate_config 边界测试、账户信息 |
| `tests/test_data_loader.py` | 12 用例：数据集划分（比例/时间序/随机/可复现）、统计信息、符号解析 |
| `tests/test_database.py` | 14 用例：表初始化、操作日志 CRUD、元数据 upsert、DBLogHandler 日志写入 |

## 源码修改

| 文件 | 变更 |
|------|------|
| `backtest/backtest_engine.py` | `VnpyMaStrategy` 改延迟导入（避免测试环境无 vnpy 时 import 链断裂）；修复 `class VnpyBacktestEngine` 丢失的类名 |
| `strategies/__init__.py` | 网关导入加 try/except（测试隔离） |
| `strategies/gateways/__init__.py` | vnpy/tqsdk 网关导入加 try/except（测试隔离） |

## 测试结果

```
86 passed in 0.91s
```

| 模块 | 用例数 | 结果 |
|------|--------|------|
| ma_strategy (核心策略) | 35 | ✅ |
| config_manager (配置) | 18 | ✅ |
| data_loader (数据加载) | 12 | ✅ |
| database (数据库) | 14 | ✅ |
| conftest (fixtures) | 7 | ✅ (7 个 fixture 被 86 个用例使用) |

## 设计决策

1. **pytest 而非 unittest**：更简洁的断言语法，fixture 机制适合数据驱动测试
2. **临时文件隔离**：Database 和 ConfigManager 测试均使用 `tempfile.mkstemp` 创建独立文件，测试后自动清理
3. **种子可复现**：`split_datasets` 测试验证 `random_seed=42` 生成相同划分结果
4. **边界覆盖**：空数据、零周期、原数据不足、比例和不为 1、SMA 边界等异常路径均有覆盖