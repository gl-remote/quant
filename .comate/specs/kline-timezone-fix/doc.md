# K线时间数据一致性修复

## 需求场景

CSV 源数据的时间是北京时间（Asia/Shanghai），但 JSON 输出中的 Unix 时间戳转换到北京时间后显示为当日早晨 8:00（如 daily 数据首个时间戳 1745452800 → 北京 2025-04-24 08:00），而非正确的市场开盘时间。根因是 pandas `resample("1d")` 按 UTC 零点切分日线，以及 raw 数据的时区转换偏差。需要修正整个数据流。

## 数据流分析

```
tqsdk → CSV (北京时间字符串) → json_writer.py → JSON (Unix timestamp) → KlineChart.tsx → lightweight-charts
```

### 当前错误状态

| 环节 | 值 | 说明 |
|------|-----|------|
| CSV | `2025-04-24 11:06:00` | 北京时间，正确 |
| JSON raw | `1745492760` | 错误！当作 UTC 11:06 存的，+8h |
| 图表显示 | 日期错误（错一天），时间也偏移 | lightweight-charts UTC→本地时区显示，因 JSON timestamp 错误导致 X 轴整体偏移 |

### 目标状态

| 环节 | 值 | 说明 |
|------|-----|------|
| CSV | `2025-04-24 11:06:00` | 北京时间，不变 |
| JSON raw | `1745463960` | 正确 UTC timestamp |
| 图表显示 | `11:06` (北京) | lightweight-charts UTC→本地正确显示 |

## 独立验证结果

使用实际 CSV 文件验证 json_writer.py 的转换逻辑：

| 项目 | 值 |
|------|-----|
| CSV 第一条 | `"2025-04-24 11:06:00"` (北京时间) |
| 正确转换后 (UTC ts) | `1745463960` → UTC 03:06 / 北京 11:06 ✓ |
| JSON 当前值 | `1745492760` → UTC 11:06 / 北京 19:06 ✗ (旧缓存) |
| Raw 数据量 | 10000 条，与 CSV 一致 ✓ |
| Daily 条数 | 49 条 (横跨 48 个自然日) |
| Daily 第一条 | `1745452800` → UTC 00:00 / 北京 08:00 (日线 UTC 零点) |

## 根因分析（三层 8h = 24h 偏移）

用户观察到图表显示“错了一天”，正好 `3 × 8h = 24h`。三层偏差来源：

```
TQSDK timestamp (UTC)
  ↓ datetime.fromtimestamp()  → +8h  【Layer 1: tqsdk_source.py】
CSV "2025-04-24 11:06:00" (naive string)
  ↓ pd.to_datetime → internal UTC → .timestamp() → +8h  【Layer 2: json_writer.py】  
JSON 1745492760 (UTC 11:06, 应为 UTC 03:06)
  ↓ lightweight-charts UTC→本地显示 → +8h  【Layer 3: 前端】
图表显示: 4月25日 11:06 (北京)  ← 错误！应为 4月24日 11:06
```

| 层级 | 位置 | 机制 | 偏移 |
|------|------|------|------|
| Layer 1 | `report/builder.py:569-572` | `pd.to_datetime()` 产出 naive Timestamp，`.timestamp()` 以 UTC 基准计算 | +8h |
| Layer 2 | `lightweight-charts` 库 | 接收 UTC timestamp，在浏览器本地时区显示 | +8h |
| Layer 3 | 待定位 | 第三层偏移来源 | +8h |
| **合计** | | | **+24h** |

**重要发现**：`builder.py:500` 和 `json_writer.py:215` 各有一个 `_build_kline_dict`。实际构建流程中，增量构建路径 `_export_kline_with_incremental` 调用的是 **builder.py 的版本**（第 251 行），我之前的 json_writer.py 修改从未生效。

## 正确修复方案

### 修改 json_writer.py

文件：`report/writer/json_writer.py:_build_kline_dict`

**正确做法**：解析 CSV datetime 时附加 Asia/Shanghai 时区标记，全程使用带时区的 Timestamp，仅在最终输出时转为 UTC Unix timestamp。

```python
# 步骤 1：解析 CSV datetime 为带时区的 Timestamp（Asia/Shanghai）
df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize("Asia/Shanghai")

# 步骤 2：日期筛选（使用带时区的 Timestamp 比较）
if start_date:
    tz_start = pd.Timestamp(start_date, tz="Asia/Shanghai")
    df = df[df["datetime"] >= tz_start]
if end_date:
    tz_end = pd.Timestamp(end_date, tz="Asia/Shanghai") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    df = df[df["datetime"] <= tz_end]

# 步骤 3：日线重采样 → 转 UTC 后 resample
df_daily = df.copy()
df_daily["datetime"] = df_daily["datetime"].dt.tz_convert("UTC")
df_daily = df_daily.set_index("datetime")
daily_ohlc = df_daily.resample("1D").agg(
    open=("open", "first"), high=("high", "max"),
    low=("low", "min"), close=("close", "last"), volume=("volume", "sum"),
)
daily_data = daily_ohlc.reset_index()
# 日线 datetime 转为 UTC Unix timestamp
daily_data["datetime"] = daily_data["datetime"].apply(lambda x: int(x.timestamp()))

# 步骤 4：raw 数据 → 转 UTC timestamp
raw_rows = []
for _, row in df.iterrows():
    ts = int(row["datetime"].tz_convert("UTC").timestamp())
    raw_rows.append({
        "datetime": ts,
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "volume": row["volume"] if pd.notna(row["volume"]) else 0,
    })
```

转换验证：
- 输入: `"2025-04-24 11:06:00"` (CSV)
- `pd.to_datetime().tz_localize("Asia/Shanghai")` → `2025-04-24 11:06:00+08:00`
- `.tz_convert("UTC").timestamp()` → `1745463960` ✓
- 图表显示：lightweight-charts 自动转本地时区 → 北京 `11:06` ✓

### 清除 KlineCache 缓存

缓存目录：`output/.kline_cache/`，缓存 key 基于 CSV mtime，CSV 未变则一直命中旧数据。

### 前端无需修改

`KlineChart.tsx:24-42` 的 `toChartTime` 直接返回 Unix timestamp：
```typescript
if (typeof dt === "number") { return dt as Time; }
```
lightweight-charts 库自动将 UTC timestamp 转为浏览器本地时区显示。

## 涉及文件

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `report/writer/json_writer.py` | 修改 | `_build_kline_dict` 完整重写时间处理逻辑 |
| `output/.kline_cache/` | 清除 | 清空旧缓存文件 |

## 验证检查项

1. `json_writer.py` 修复后 raw 第一条 timestamp = `1745463960`
2. JSON raw_count = 10000
3. Daily 条数 = 49
4. 前端图表 X 轴显示北京时间与 CSV 一致