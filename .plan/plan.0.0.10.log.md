# 项目改进计划 v0.0.10 归档

## 变更概述

多品种并发回测功能实现（A13）。plan.md 从 v0.0.9 归档后重写为 v0.0.10。

## A13: 多品种并发回测

### 新增功能

1. **多文件扫描** (`backtest/data_loader.py`)
   - `scan_csv_files(data_dir, pattern=None)` — 扫描数据目录，支持正则表达式匹配
   - 自动去重 `{symbol}.csv` / `{symbol}_qlib.csv` 变体

2. **批量回测引擎** (`backtest/backtest_engine.py`)
   - `VnpyBacktestEngine.run_multi_backtest(pattern, max_workers)` — 批量回测入口
   - 支持 `ThreadPoolExecutor` 多线程并发回测 (--parallel N)
   - 单个品种失败不影响其他品种

3. **合并报告** (`backtest/comparison.py`)
   - `generate_merged_report(all_results)` — 合并所有品种的对比分析
   - `format_merged_report(merged)` — 控制台合并报告格式化
   - 包含：品种排名、聚合统计、过拟合汇总

4. **CLI 更新** (`main.py`)
   - `--pattern` 参数：正则表达式匹配品种代码
   - `--parallel` 参数：并行线程数（默认 1 = 顺序）
   - 无 `--symbol` 时自动进入批量模式（全量回测）

### 使用示例

```bash
python main.py backtest --pattern "DCE\.m"              # 匹配 DCE 所有 m 品种
python main.py backtest --pattern "DCE\.m" --parallel 4  # 4 线程并行
python main.py backtest                                  # 回测全部品种
python main.py backtest --symbol DCE.m2509               # 传统单品种
```

### 修改清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backtest/data_loader.py` | 修改 | 新增 `scan_csv_files()` |
| `backtest/comparison.py` | 修改 | 新增 `generate_merged_report()` 等 4 个函数 |
| `backtest/backtest_engine.py` | 修改 | 新增 `run_multi_backtest()` 方法 |
| `main.py` | 修改 | 新增 `--pattern`/`--parallel`，重构 `cmd_backtest` |
| `tests/test_data_loader.py` | 修改 | 新增 8 个 scan_csv_files 测试 |
| `tests/test_report_comparison.py` | 修改 | 新增 9 个合并报告测试 |

### 测试结果

- 测试用例：127 → 146（+19）
- 覆盖率：85%
- 全部通过

## 项目状态快照

- 测试: 146 用例全部通过 (3.72s), 覆盖率 85%
- AI_BEHAVIOR_RULES.md: v0.0.6
- plan.md: v0.0.9 → v0.0.10
- 当前阶段: M3 功能增强（A13 完成，A11/A12/A14/A15 待完成）