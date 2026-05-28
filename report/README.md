# Report 模块 - 缓存与增量构建机制

## 概述

Report 模块负责生成量化回测报告，包含完整的缓存和增量构建机制，显著提升重复构建性能。

---

## 模块结构

```
report/
├── builder.py          # 报告构建编排入口
├── cache/              # 缓存模块
│   ├── __init__.py     # 统一导出接口
│   ├── build.py        # BuildCache - 增量构建缓存管理器
│   └── kline.py        # KlineCache - K线数据转换缓存
├── writer/             # JSON 数据写入模块
│   ├── __init__.py
│   └── json_writer.py
├── optimizer_report.py # Optuna 优化报告生成
└── web/                # React 前端应用
```

---

## 缓存机制

### 1. 统一缓存管理器 `BuildCache`

**功能定位**：统一管理所有数据类型的指纹，支持增量构建决策。

```python
from report.build_cache import BuildCache

cache = BuildCache(output_dir="output")

# 检查数据是否需要更新
if cache.needs_update("run", run_id=1, new_data=data):
    # 执行导出
    cache.update_fingerprint("run", run_id=1, data=data)

# 检查前端是否需要重建
if cache.needs_frontend_rebuild(web_dir):
    # 执行前端构建
    cache.set_frontend_hash(src_hash)
```

**缓存目录结构**：
```
output/.build_cache/
├── fingerprints/         # 数据指纹存储
│   ├── run_1.json
│   ├── summary_1.json
│   ├── backtests_1.json
│   ├── equity_1.json
│   ├── kline_1.json
│   ├── optuna_1.json
│   └── nav.json
└── frontend_hash         # 前端源码哈希
```

**API 接口**：

| 方法 | 功能 |
|------|------|
| `needs_update(data_type, run_id, new_data)` | 检查数据是否变更 |
| `update_fingerprint(data_type, run_id, data)` | 更新数据指纹 |
| `needs_frontend_rebuild(web_dir)` | 检查前端是否需要重建 |
| `set_frontend_hash(src_hash)` | 设置前端源码哈希 |
| `get_frontend_hash()` | 获取前端源码哈希 |
| `clear()` | 清空所有缓存 |

---

### 2. K线转换缓存 `KlineCache`

**功能定位**：复用 K线 CSV→JSON 转换结果，避免重复计算。

```python
from report.kline_cache import KlineCache

cache = KlineCache(output_dir="output")

# 尝试从缓存获取
data = cache.get(symbol, csv_path, interval)
if data is None:
    # 计算并缓存
    data = build_kline_dict(...)
    cache.put(symbol, csv_path, interval, data)

# 直接复制缓存到目标路径
cache.copy_to(symbol, csv_path, interval, dest_path)
```

**缓存键设计**：`md5(symbol|csv_path|interval|csv_mtime)`

---

## 增量构建机制

### `build_all` 函数

**签名**：`build_all(output_dir: str, run_id: int, incremental: bool = True)`

**增量构建流程**：

```
┌──────────────────────────────────────────────────────────────┐
│                    build_all 增量构建流程                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌───────────────────────┐                                  │
│  │ 检查 incremental 参数 │                                  │
│  └───────────┬───────────┘                                  │
│              │                                              │
│     ┌────────┴────────┐                                    │
│     │                 │                                    │
│   True             False                                    │
│     │                 │                                    │
│     ▼                 ▼                                    │
│  ┌─────────┐    全量导出所有数据                            │
│  │BuildCache│    └──────────────────────────────────┐       │
│  └────┬────┘                                       │       │
│       │                                            │       │
│       ▼                                            │       │
│  ┌─────────────────────────┐                       │       │
│  │ 逐个比对数据指纹:        │                       │       │
│  │ - run                   │                       │       │
│  │ - summary               │                       │       │
│  │ - backtests             │                       │       │
│  │ - equity                │                       │       │
│  │ - kline                 │                       │       │
│  │ - optuna                │                       │       │
│  │ - nav                   │                       │       │
│  └──────┬──────────────────┘                       │       │
│         │                                          │       │
│         ▼                                          │       │
│  ┌─────────────────────────┐                       │       │
│  │ 数据变更?              │                       │       │
│  └──────┬──────────────────┘                       │       │
│    Yes  │  No                                     │       │
│    ▼    │    ▼                                    │       │
│ 导出数据 更新指纹 跳过导出                           │       │
│         │                                          │       │
│         └─────────────┬────────────────────────────┘       │
│                       │                                   │
│                       ▼                                   │
│           ┌─────────────────────┐                         │
│           │ build_frontend()    │ ← 前端增量构建            │
│           └─────────┬───────────┘                         │
│                     │                                     │
│                     ▼                                     │
│           ┌─────────────────────┐                         │
│           │ 数据变更?          │                         │
│           └───────┬─────────────┘                         │
│             Yes   │   No                                 │
│              ▼    │    ▼                                 │
│       write_entry_html()  跳过                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**日志输出示例**：

```
# 首次构建
→ 导出 run（数据已变更）
→ 导出 summary（数据已变更）
→ 导出 backtests（数据已变更）
→ 导出 equity（数据已变更）
→ 导出 kline（数据已变更）
→ 导出 optuna（数据已变更）
→ 导出 nav（数据已变更）
✓ 构建前端完成
✓ 写入入口HTML完成
报告构建结束: 成功=8, 跳过=0, 失败=0, 耗时=35.20s

# 二次构建（无数据变更）
○ 跳过 run（数据未变更）
○ 跳过 summary（数据未变更）
○ 跳过 backtests（数据未变更）
○ 跳过 equity（数据未变更）
○ 跳过 kline（数据未变更）
○ 跳过 optuna（数据未变更）
○ 跳过 nav（数据未变更）
前端源码未变更，跳过构建
○ 数据未变更，跳过写入入口HTML
报告构建结束: 成功=0, 跳过=7, 失败=0, 耗时=0.85s
```

---

## 性能提升

| 场景 | 优化前 | 优化后 | 提升 |
|------|-------|-------|------|
| 首次构建 | ~35s | ~35s | - |
| 二次构建（无变化） | ~35s | ~1s | **35x** |
| 前端未变更 | ~35s | ~15s | **2.3x** |
| K线缓存命中 | ~35s | ~10s | **3.5x** |

---

## 核心设计原则

### 1. 数据指纹算法

采用 MD5 哈希算法，基于数据内容生成唯一指纹：

```python
def _compute_fingerprint(data):
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(content.encode()).hexdigest()
```

### 2. 缓存有效性保障

- **K线缓存**：包含 CSV 文件修改时间，文件变更自动失效
- **数据指纹**：每次构建前重新计算，确保准确性
- **前端哈希**：基于源码目录内容，文件变更自动检测

### 3. 容错设计

- 单个数据类型导出失败不影响其他类型
- 前端构建失败仍尝试写入入口HTML（降级处理）
- 详细的失败日志记录

---

## 使用示例

### 基本使用

```python
from report import build_all

# 默认启用增量构建
build_all(output_dir="output", run_id=1)

# 强制全量构建
build_all(output_dir="output", run_id=1, incremental=False)
```

### 缓存管理

```python
from report.build_cache import BuildCache

cache = BuildCache("output")

# 获取缓存统计
stats = cache.get_cache_stats()
print(stats)
# {
#     "cache_dir": "output/.build_cache",
#     "fingerprint_count": 7,
#     "total_size_bytes": 1536,
#     "run_ids": [1, 2, 3]
# }

# 清空指定 run 的缓存
cache.clear_fingerprints(run_id=1)

# 清空所有缓存
cache.clear()
```

---

## 开发注意事项

### 1. 添加新数据类型

如需添加新的数据导出类型，需：

1. 在 `_export_with_incremental` 调用中添加新类型
2. 在 `_dispatch_export` 函数中添加分发逻辑
3. 确保数据可被 JSON 序列化（用于指纹计算）

### 2. 缓存失效场景

以下情况会导致缓存失效：

- 数据库中回测记录发生变更
- CSV 源文件修改时间变化
- 前端源码目录内容变化
- 手动删除 `.build_cache` 目录

### 3. 调试模式

设置日志级别为 DEBUG 可查看详细的缓存命中信息：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 版本历史

| 版本 | 变更说明 |
|------|---------|
| v1.0 | 初始版本，无缓存机制 |
| v1.1 | 添加 KlineCache，复用 K线转换结果 |
| v1.2 | 添加前端源码哈希缓存 |
| v1.3 | 引入 BuildCache 统一管理所有数据指纹 |
| v1.4 | `build_all` 支持增量构建模式 |