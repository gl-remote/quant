---
name: datafeed-parquet-cache
overview: 在 DataFeed 类中增加 to_parquet / from_parquet 方法，实现指标预计算结果的整体读写缓存。Bridge 的 on_init 中优先从 Parquet 加载，避免重复计算指标。
todos:
  - id: add-pyarrow-dep
    content: 在 pyproject.toml 的 dependencies 中新增 pyarrow>=14 依赖
    status: pending
  - id: add-period-load-parquet
    content: 在 PeriodData 类新增 load_df_parquet 方法，支持从 parquet 加载 DataFrame 并标记已计算指标列
    status: pending
  - id: add-to-parquet
    content: 使用 [skill:quant-dev] 在 DataFeed 类实现 to_parquet(cache_dir) 方法，遍历各周期写 parquet 和 _meta.json
    status: pending
    dependencies:
      - add-period-load-parquet
  - id: add-from-parquet
    content: 在 DataFeed 类实现 from_parquet(cache_dir) classmethod，从 parquet 恢复完整 DataFeed 实例
    status: pending
    dependencies:
      - add-period-load-parquet
  - id: modify-bridge-on-init
    content: 修改 VnpyBacktestBridge.on_init 加入缓存分支：优先 from_parquet，未命中则走完整流程后 to_parquet
    status: pending
    dependencies:
      - add-to-parquet
      - add-from-parquet
---

## 用户需求

回测时将 DataFeed 中已计算好指标的数据保存为 Parquet 文件，下次回测直接从缓存加载，跳过 `calculate_all()`。

## 核心功能

- **保存**：`DataFeed.to_parquet(cache_dir)` 将每个周期的完整 DataFrame（含 OHLCV 和所有指标列）写为一个 parquet 文件，同时写一份 `_meta.json` 记录元数据
- **加载**：`DataFeed.from_parquet(cache_dir)` 从 parquet 文件恢复完整的 DataFeed 实例，包括周期数据、指标配置和已计算标记
- **桥接器集成**：`VnpyBacktestBridge.on_init()` 中先尝试从缓存加载，命中则直接 build ctx_cache；未命中走现有完整流程并在最后存入缓存

## 缓存目录结构

```
output/cache/
├── DCE.m2509/
│   ├── _meta.json          # {"symbol": "...", "source": "...", "periods": ["1m"], "indicators": {...}}
│   ├── 1m.parquet          # index=datetime, columns=open/high/low/close/volume/sma_5/sma_20/...
│   └── 5m.parquet
```

## 技术栈

- Python 3.10+
- pandas（已有）
- pyarrow（新增依赖，Parquet 读写引擎）

## 实现方案

### 整体思路

在 `DataFeed` 类中新增两个方法 `to_parquet(cache_dir)` 和 `from_parquet(cache_dir)`，实现完整的序列化/反序列化。Bridge 负责决定缓存目录路径并调用这两个方法。

### 核心设计决策

1. **每个周期一个 parquet 文件**：每个 parquet 文件就是 `PeriodData._df` 的完整快照，已包含 OHLCV 列和所有指标列。`pd.read_parquet()` 直接从文件反序列化进内存，无需任何行级拼接。

2. **元数据用 JSON**：`_meta.json` 记录 symbol、source、注册了哪些周期、每个周期注册了哪些指标（name + params）。用于恢复 `_registered_indicators` 和指标计算标记。

3. **`from_parquet` 为 classmethod**：需要先创建 DataFeed 实例再填充数据，因此设计为 `@classmethod`。

4. **指标计算状态恢复**：加载 parquet 后，需调用 `period_data.mark_indicator_calculated(col, len(df)-1)` 恢复每个指标列的已计算标记，确保后续 `is_indicator_calculated()` 返回 True，`calculate_all()` 自动跳过。

5. **`PeriodData` 暴露新方法**：当前 `mark_indicator_calculated` 和 `load_df` 已有，但 `from_parquet` 需要知道 DataFrame 中有哪些指标列（非 OHLCV 的列）。新增 `PeriodData.load_df_parquet(df, indicator_columns)` 方法，一行完成数据加载 + 指标标记。

### 性能分析

- 写入：`df.to_parquet()` 对万行级数据耗时 ~20-50ms，在回测结束时执行一次，对总耗时影响可忽略
- 读取：`pd.read_parquet()` 耗时 ~10-20ms，比 `calculate_all()`（遍历所有周期重算 SMA 等指标）快数十到数百倍
- 缓存命中时完全跳过 `_load_all_periods()` 中的 DataManager CSV 加载和 `calculate_all()` 的指标计算

### 实现要点

**DataFeed.to_parquet(cache_dir)**

```python
def to_parquet(self, cache_dir: str) -> None:
    # 1. 创建目录
    # 2. 构建 _meta.json（symbol/source/periods/indicators 信息）
    # 3. 写 _meta.json
    # 4. 遍历 self._periods，每个 period 写 {period}.parquet
```

**DataFeed.from_parquet(cache_dir: str) -> DataFeed**

```python
@classmethod
def from_parquet(cls, cache_dir: str) -> DataFeed:
    # 1. 读 _meta.json
    # 2. 创建 DataFeed 实例
    # 3. 遍历 periods，每个读 {period}.parquet
    # 4. 调用 period_data.load_df_parquet(df, indicator_cols)
    # 5. 恢复 _registered_indicators
    # 6. 返回 DataFeed 实例
```

**VnpyBacktestBridge.on_init 改动**

```python
cache_dir = f"output/cache/{self._state.symbol}"
try:
    data_feed = DataFeed.from_parquet(cache_dir)
    # 缓存命中，跳过 _load_all_periods 和 calculate_all
except (FileNotFoundError, KeyError):
    # 未命中，走完整流程
    data_feed = DataFeed(...)
    # register periods/indicators
    self._load_all_periods(data_feed)
    data_feed.calculate_all()
    data_feed.to_parquet(cache_dir)

self._data_feed = data_feed
# 继续 build ctx_cache ...
```

## Agent Extensions

### Skill

- **quant-dev**
- 目的：确保实现符合 quant 项目的架构约定、symbol 格式规范和 DataFeed/PeriodData 内部 API 使用方式
- 预期结果：生成的代码与现有 `vnpy_bridge.py` 中访问 `period_data._df` 的模式一致，遵循项目代码风格

### SubAgent

- **code-explorer**
- 目的：全面检查 `PeriodData` 类中所有指标计算状态相关方法签名（`mark_indicator_calculated`、`is_indicator_calculated`、`clear_indicator_calculation`、`load_df`），确保 `from_parquet` 恢复逻辑正确
- 预期结果：确认所有需要调用的 PeriodData API 及其参数格式，避免运行时错误