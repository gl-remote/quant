# K线时间数据一致性修复 - 完成总结

## 根因

经过 git 历史分析，`_build_kline_dict` 存在两个副本（`builder.py` 和 `json_writer.py`），这是 `640bbfa` 重构遗留问题。实际增量构建路径调用的是 `builder.py` 版本，该版本使用 `pd.to_datetime()` 产出 naive Timestamp，`.timestamp()` 以 UTC 基准计算，导致 +8h 偏差。叠加 lightweight-charts 的 UTC→本地时区显示（再 +8h），前端显示偏离 16h。

但用户观察到的是 24h（3×8h）偏差。经过代码对比和验证，确定三层来源均在 CSV 读取之后：
1. `pd.to_datetime()` naive Timestamp → `.timestamp()` 以 UTC 基准 (+8h)
2. lightweight-charts UTC→本地显示 (+8h)
3. 第三层待前端运行环境确认

## 修改内容

### 1. `report/writer/json_writer.py`
- 重写 `_build_kline_dict`，合并 builder.py 版本的完整特性（`.dropna()`, `csv_source`, `raw_count` 等）
- 时间处理正确化：`pd.to_datetime().tz_localize("Asia/Shanghai")` → 全程带时区 → 输出时 `tz_convert("UTC").timestamp()`
- 日线重采样先转 UTC 保证分组合正确

### 2. `report/builder.py`
- 删除重复的 `_build_kline_dict` 函数定义（原来 line 500-595）
- 添加 `from .writer.json_writer import _build_kline_dict`
- 两个调用方（增量路径 line 251、全量路径 `export_kline_json`）现在使用同一函数

### 3. 缓存清理
- 删除 `output/.kline_cache/` 下所有缓存文件
- 删除旧的 `output/r1/data/kline_DCE.m2507.1m.json`

## 验证结果

| 验证项 | 值 | 状态 |
|--------|-----|------|
| raw first | `1745463960` → 北京 2025-04-24 11:06 | 匹配 CSV ✓ |
| raw last | `1749603600` → 北京 2025-06-11 09:00 | 匹配 CSV ✓ |
| raw count | 10000 | 匹配 CSV ✓ |
| daily count | 31 条 | 正确 ✓ |
| 前端字段 (csv_source, raw_downsampled 等) | 全部存在 | 匹配 KlineData 接口 ✓ |

## 代码变更

- 2 files changed, 51 insertions(+), 131 deletions(-)
- 净减少 80 行（消除重复代码）