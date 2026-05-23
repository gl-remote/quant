# 项目改进计划 v0.0.11 归档

## 变更概述

export 命令增强：支持 `--force` 强制覆盖 + database.py Schema 注释完善。plan.md 从 v0.0.10 归档后重写为 v0.0.11。

## export --force 覆盖模式

### 修改内容

| 文件 | 变更 |
|------|------|
| `data/exporter.py` | `export_csv()` 新增 `force: bool = False` 参数，`force=True` 时跳过已有 CSV 合并，直接覆盖写入并更新元数据 |
| `main.py` | export 子命令新增 `--force` flag 参数，传递给 `export_csv()` |
| `data/database.py` | `_SCHEMA` 两表添加表级注释和字段级注释 |

### 使用方式

```bash
python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2025-06-30 --force
```

`--force` 模式下：
- 跳过 `get_metadata()` → `pd.read_csv()` 合并流程
- 直接以新数据覆盖 CSV 文件
- 元数据表 `export_metadata` 使用 `upsert_metadata()` 覆盖更新

### Schema 注释

- `export_metadata`: 表注释 + 10 个字段注释
- `operation_logs`: 表注释 + 5 个字段注释

## 项目状态快照

- 测试: 146 用例，覆盖率 85%
- AI_BEHAVIOR_RULES.md: v0.0.6
- plan.md: v0.0.10 → v0.0.11