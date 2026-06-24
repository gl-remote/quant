# 报告模块 React 重构 — 分阶段技术方案

> 类型：Design / 已实现设计记录  
> 状态：主体已实现，Phase D 待全链路验证  
> 完成日期：2026-05-27  
> Git 参考：`6dacbde feat: 报告模块 React 重构 + file:// 预加载方案`

> **目标**: 将 Jinja2 模板方案替换为 React + Vite 单页应用（SPA），Python 负责数据层 JSON 导出，React 负责渲染。
> **原则**: 一次 run = 一次统一构建，不生成独立单报告 HTML。SPA 使用 HashRouter 路由，单入口 HTML。

> **状态**: ✅ Phase A/B/C 已完成 (2026-05-27), Phase D 待全链路验证

---

## 📋 实施进度

| 阶段 | 状态 | 完成时间 |
|------|------|---------|
| **Phase A** Python 数据层 | ✅ 完成 | 2026-05-27 |
| **Phase B** React 前端 | ✅ 完成 | 2026-05-27 |
| **Phase C** 集成清理 | ✅ 完成 | 2026-05-27 |
| **Phase D** 验证 | ⏳ 待执行 | — |

---

## 🔧 实施调整记录

### 与原始方案的差异

1. **Plotly 外部化方式**: 原方案用 `<script>` 标签加载 plotly.min.js，实际改用 `createPlotlyComponent((window as any).Plotly)` 工厂模式 (`src/components/PlotlyWrapper.tsx`)，彻底避免打包 Plotly（bundle 从 5MB → 188KB）。
2. **无 plotly.min.js 本地文件**: 暂未下载到 `resources/`，当前由 `write_entry_html()` 中的 `<script>` 标签引用 `assets/vendor/plotly.min.js`。后续需下载到 `public/vendor/` 或设为可选。
3. **简化了 Optuna 路由**: Optuna 内容直接在 RunPage 内通过 `showOptuna` 状态 + Link 切换，同时保留独立的 OptunaPage.tsx 路由。
4. **GenericChart 组件**: 新增通用 Plotly spec 图表组件，Optuna 的四张图 (优化历史/参数重要性/平行坐标/等高线) 共用同一组件。

---

## 目录

1. [架构设计](#架构设计)
2. [K 线数据缓存机制](#k-线数据缓存机制)
3. [Phase A: Python 数据层改造](#phase-a-python-数据层改造)
4. [Phase B: React 前端工程](#phase-b-react-前端工程)
5. [Phase C: 集成清理](#phase-c-集成清理)
6. [Phase D: 验证](#phase-d-验证)
7. [附录](#附录)

---

## 架构设计

### 整体数据流

```
┌──────────────────────────────────────────────────────────────────┐
│  optimizer → DB (backtests / backtest_daily / backtest_trades)   │
│       ↓                                                          │
│  finish_run(run_id)                                              │
│       ↓                                                          │
│  build_all(db_path, output_dir, run_id)                         │
│       │                                                          │
│       ├─ export_run_json()       → output/rN/data/run.json       │
│       ├─ export_summary_json()   → output/rN/data/summary.json   │
│       ├─ export_backtests_json() → output/rN/data/backtests.json │
│       ├─ export_equity_json()    → output/rN/data/equity.json    │
│       ├─ export_kline_json()     → output/rN/data/kline_{s}.json │
│       │     ├─ KlineCache 命中 → 直接复制缓存文件                │
│       │     └─ KlineCache 未命中 → CSV→JSON 转换 → 写入缓存      │
│       ├─ export_optuna_json()    → output/rN/data/optuna.json    │
│       └─ write_nav_json()        → output/data/nav.json          │
│                                                                   │
│  build_frontend(output_dir)  ← 增量构建（源码 hash 检测）        │
│       ↓                                                          │
│  write_entry_html(output_dir) → output/index.html                │
│                                                                   │
│  浏览器打开 output/index.html                                     │
│       ↓ HashRouter                                               │
│  #/         → NavPage   (读取 data/nav.json)                     │
│  #/run/1    → RunPage   (读取 r1/data/*.json)                    │
│  #/run/1/optuna → OptunaPage                                     │
└──────────────────────────────────────────────────────────────────┘
```

### SPA 单页架构说明

不同于原方案"多个 entry HTML"，这里采用 **单入口 + HashRouter** 架构：

- **output/index.html** 是唯一的 HTML 文件
- 所有页面通过 hash 路由切换：`#/` → NavPage, `#/run/:id` → RunPage
- React bundle 和 Plotly vendor 放在 `output/assets/`
- JSON 数据文件放在 `output/rN/data/` 和 `output/data/`
- 所有 fetch 路径相对于 `output/index.html`，兼容 `file://` 协议

```
output/
├── index.html              # 唯一入口（Vite 构建产物 + 哈希引入 assets）
├── assets/                 # Vite 构建的 JS/CSS bundle
│   ├── index-abc123.js
│   ├── index-abc123.css
│   └── vendor/
│       └── plotly.min.js   # 预置 Plotly（不参与 Vite bundle）
├── data/
│   └── nav.json            # 全局导航数据
├── r1/
│   ├── data/
│   │   ├── run.json
│   │   ├── summary.json
│   │   ├── backtests.json
│   │   ├── equity.json
│   │   ├── kline_DCE.m2601.json
│   │   └── optuna.json
│   └── (不再生成 r1/index.html)
├── r2/
│   └── data/...
└── .kline_cache/           # K 线全局缓存
    └── {md5_hash}.json
```

---

## K 线数据缓存机制

### 问题分析

当前代码存在以下 K 线数据转换瓶颈：

1. **[queries/backtest.py:79-128](file:///Users/REDACTED_API_KEY/Documents/src/quant/report/queries/backtest.py#L79-L128)** `get_kline_data()`: 每次调用都 `pd.read_csv(data_src)` 然后遍历 DataFrame → list[dict]，CSV 可能有 50w+ 行
2. **[__init__.py:117-191](file:///Users/REDACTED_API_KEY/Documents/src/quant/report/__init__.py#L117-L191)** `_build_kline_chart()`: 读 CSV → resample 到日线 → 构建 Plotly candlestick，整个链路在每次生成报告时都重新计算

SQLite 中 `backtests.data_src` 字段已存储了 CSV 文件路径（由 [CLI backtest.py:355](file:///Users/REDACTED_API_KEY/Documents/src/quant/cli/commands/backtest.py#L355) 传入），多个 run 可能共用同一个 CSV 源文件。每次都重新读取和转换是对 I/O 和 CPU 的巨大浪费。

### 缓存设计

```
┌─────────────────────────────────────────────────────────────┐
│                   KlineCache (单例)                         │
│                                                             │
│  cache_dir = "output/.kline_cache/"                         │
│                                                             │
│  get(symbol, data_src, interval) → dict | None              │
│      1. 计算 cache_key = md5(symbol + csv_path + csv_mtime) │
│      2. 检查 output/.kline_cache/{cache_key}.json 是否存在  │
│      3. 存在且 csv_mtime 未变 → 返回缓存 JSON               │
│      4. 不存在或过期 → 返回 None                            │
│                                                             │
│  put(symbol, data_src, interval, kline_dict) → None         │
│      1. 计算 cache_key                                      │
│      2. 写入 output/.kline_cache/{cache_key}.json           │
│      3. 写入 sidecar .meta 文件（symbol/interval/mtime）    │
│                                                             │
│  缓存失效条件:                                               │
│      源 CSV 修改时间变化                                     │
│      缓存目录 .kline_cache/ 不存在                           │
└─────────────────────────────────────────────────────────────┘
```

### 关键实现细节

```python
# report/kline_cache.py (新增)

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class KlineCache:
    """K 线数据转换缓存

    以 (symbol, csv_path, csv_mtime) 的 md5 为 key，
    将 pandas CSV → JSON dict 的转换结果持久化缓存。

    多个 run 共用相同 CSV 源时，转换只发生一次。
    """

    def __init__(self, output_dir: str = "output"):
        self._cache_dir = Path(output_dir) / ".kline_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, symbol: str, csv_path: str, interval: str) -> str:
        mtime = str(os.path.getmtime(csv_path)) if os.path.exists(csv_path) else "0"
        raw = f"{symbol}|{csv_path}|{interval}|{mtime}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, symbol: str, csv_path: str, interval: str = "1m") -> dict | None:
        key = self._cache_key(symbol, csv_path, interval)
        cache_file = self._cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def put(self, symbol: str, csv_path: str, interval: str, data: dict) -> None:
        key = self._cache_key(symbol, csv_path, interval)
        cache_file = self._cache_dir / f"{key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)

    def copy_to(self, symbol: str, csv_path: str, interval: str, dest: Path) -> bool:
        """将缓存文件复制到目标路径，成功返回 True"""
        import shutil
        data = self.get(symbol, csv_path, interval)
        if data is None:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
        return True
```

### 数据格式与降采样

K 线 JSON 同时包含日线 resampled 数据和原始分钟线数据，前端按需选取：

```json
{
  "symbol": "DCE.m2601",
  "interval": "1m",
  "csv_source": "/path/to/DCE.m2601.tqsdk.1m.csv",
  "downsampled": true,
  "daily": [
    {"datetime": "2024-01-02", "open": 3412.0, "high": 3450.0, "low": 3400.0, "close": 3430.0, "volume": 125000},
    ...
  ],
  "raw": [
    {"datetime": "2024-01-02 09:01:00", "open": 3412.0, "high": 3415.0, "low": 3410.0, "close": 3414.0, "volume": 1200},
    ...
  ],
  "raw_count": 52480,
  "raw_downsampled": true,
  "raw_sample_max": 5000
}
```

**降采样规则**：

- `daily`：始终通过 `df.resample("1d").agg(...)` 生成，数据量可控
- `raw`：
  - 当原始行数 ≤ 5000 时，保留全部分钟线
  - 当原始行数 > 5000 时，步长 `skip = ceil(total / 5000)` 抽样
- 前端 KlineChart 默认展示 `daily` 数据，提供切换按钮查看 `raw` 精细图

### 缓存生命周期

```
首次 run (symbol=DCE.m2601, csv=/data/DCE.m2601.tqsdk.1m.csv):
  → KlineCache.get() → None (缓存未命中)
  → pd.read_csv → resample → 构建 JSON
  → KlineCache.put() → 写入 .kline_cache/{md5}.json
  → 复制到 output/r1/data/kline_DCE.m2601.json

后续 run (同一 symbol, 同一 csv):
  → KlineCache.get() → dict (缓存命中!)
  → 直接复制到 output/r2/data/kline_DCE.m2601.json
  → 跳过 CSV 读取和 resample，O(1) 操作

CSV 文件更新后:
  → csv_mtime 变化 → cache_key 变化 → 缓存失效
  → 重新触发 CSV→JSON 转换

手动清理:
  rm -rf output/.kline_cache/
```

---

## Phase A: Python 数据层改造

### A.1 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `report/kline_cache.py` | **新建** | K 线数据转换缓存 |
| `report/builder.py` | **重写** | 删除 Jinja2 渲染，改为 `export_*_json()` + `build_frontend()` + `write_entry_html()` |
| `report/charts.py` | **微调** | 已完成大部分改造（返回 Plotly spec dict），补充 Optuna 图表支持 |
| `report/optimizer_report.py` | **重写** | 从 Jinja2 模板 → 返回 `{"study_name", "charts": {...}, "best_params": {...}}` dict |
| `report/__init__.py` | **精简** | 删除 `build_report`, `_build_info`, `_build_kline_chart`；保留对外的 re-export |
| `report/queries/backtest.py` | **微调** | 新增 `get_all_backtests_for_run()` 方法；补充 data_src 查询 |
| `cli/commands/backtest.py` | **微调** | 删除 `_build_optimization_report`；`build_all` 调用改为新接口 |
| `cli/commands/report.py` | **微调** | 适配新接口 |

### A.2 删除清单

```bash
rm -rf report/templates/              # 6 个 Jinja2 文件
```

`report/__init__.py` 中删除以下函数：
- `build_report()` (L21-90) — 替换为 `build_all()`
- `_build_info()` (L93-115) — 逻辑合并到 `export_run_json()`
- `_build_kline_chart()` (L117-191) — 替代为 `export_kline_json()` + KlineCache

`cli/commands/backtest.py` 中删除：
- `_build_optimization_report()` (L674-706) — 合并到 `build_all()` 内

### A.3 `report/builder.py` 详细设计

```python
# -*- coding: utf-8 -*-
"""报告生成编排 — export JSON → 数据写入 → 前端构建"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sqlite3
from pathlib import Path

import pandas as pd

from .charts import build_kline_spec, build_equity_spec
from .kline_cache import KlineCache
from .optimizer_report import build_optuna_spec

logger = logging.getLogger(__name__)

KLINE_DOWNSAMPLE_THRESHOLD = 5000  # 分钟线超过此阈值进行降采样


# ── Public API ──────────────────────────────────────────────────


def build_all(db_path: str, output_dir: str, run_id: int) -> None:
    """回测完成后统一入口"""
    export_run_json(db_path, output_dir, run_id)
    export_summary_json(db_path, output_dir, run_id)
    export_backtests_json(db_path, output_dir, run_id)
    export_equity_json(db_path, output_dir, run_id)
    export_kline_json(db_path, output_dir, run_id)
    export_optuna_json(db_path, output_dir, run_id)
    write_nav_json(db_path, output_dir)
    build_frontend(output_dir)
    write_entry_html(output_dir)
    logger.info(f"报告构建完成: output/r{run_id}/")


# ── JSON 导出函数 ────────────────────────────────────────────────


def export_run_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出单次 run 的元信息"""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT id, strategy, engine, symbols, status, created_at "
        "FROM runs WHERE id=?",
        (run_id,),
    ).fetchone()
    conn.close()

    if not row:
        logger.warning(f"run_id={run_id} 不存在")
        return

    data = {
        "id": row[0],
        "strategy": row[1],
        "engine": row[2],
        "symbols": row[3],
        "status": row[4],
        "created_at": row[5],
    }
    _write_json(output_dir, f"r{run_id}/data/run.json", data)


def export_summary_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出品种汇总表"""
    from .queries.backtest import get_run_summary
    data = get_run_summary(db_path, run_id)
    _write_json(output_dir, f"r{run_id}/data/summary.json", data)


def export_backtests_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出所有回测记录的完整信息（含 equity_spec、params 等）"""
    conn = sqlite3.connect(db_path)
    backtests = conn.execute(
        "SELECT id, symbol, strategy, status, start_date, end_date, "
        "initial_capital, end_balance, total_return, sharpe_ratio, "
        "max_drawdown, win_rate, total_trades, data_src, kline_interval, "
        "strategy_version, git_hash "
        "FROM backtests WHERE run_id=? AND status='success'",
        (run_id,),
    ).fetchall()

    result = []
    for bt in backtests:
        bt_id = bt[0]
        params = conn.execute(
            "SELECT param_name, param_value FROM backtest_params "
            "WHERE backtest_id=? ORDER BY param_name",
            (bt_id,),
        ).fetchall()

        daily = conn.execute(
            "SELECT date, equity, daily_return, drawdown "
            "FROM backtest_daily WHERE backtest_id=? ORDER BY date",
            (bt_id,),
        ).fetchall()

        # 构建每日数据供前端 equity 图表
        daily_data = [
            {"date": d[0], "equity": d[1], "daily_return": d[2], "drawdown": d[3]}
            for d in daily
        ]

        result.append({
            "id": bt_id,
            "symbol": bt[1],
            "strategy": bt[2],
            "status": bt[3],
            "start_date": bt[4],
            "end_date": bt[5],
            "initial_capital": bt[6],
            "end_balance": bt[7],
            "total_return": bt[8],
            "sharpe_ratio": bt[9],
            "max_drawdown": bt[10],
            "win_rate": bt[11],
            "total_trades": bt[12],
            "data_src": bt[13],
            "kline_interval": bt[14],
            "strategy_version": bt[15],
            "git_hash": bt[16],
            "params": [{"name": p[0], "value": p[1]} for p in params],
            "daily": daily_data,
        })
    conn.close()

    _write_json(output_dir, f"r{run_id}/data/backtests.json", result)


def export_equity_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出资金曲线数据（每品种最优回测 + 日线数据）"""
    from .queries.backtest import get_equity_data, get_run_summary

    summary = get_run_summary(db_path, run_id)
    result = {}
    for s in summary:
        equity = get_equity_data(db_path, s["symbol"], run_id)
        if equity:
            result[s["symbol"]] = equity
    _write_json(output_dir, f"r{run_id}/data/equity.json", result)


def export_kline_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出 K 线数据 JSON（使用 KlineCache 避免重复转换）

    从 backtests 表获取各品种的 CSV 路径和日期范围，
    按品种独立生成 kline_{symbol}.json。
    """
    cache = KlineCache(output_dir)

    conn = sqlite3.connect(db_path)
    # 按品种取第一条成功回测记录（同品种多回测用同一 CSV 源）
    rows = conn.execute("""
        SELECT DISTINCT symbol,
               FIRST_VALUE(data_src) OVER w AS data_src,
               FIRST_VALUE(start_date) OVER w AS start_date,
               FIRST_VALUE(end_date) OVER w AS end_date,
               FIRST_VALUE(kline_interval) OVER w AS kline_interval
        FROM backtests
        WHERE run_id=? AND status='success' AND data_src IS NOT NULL
        WINDOW w AS (PARTITION BY symbol ORDER BY id)
    """, (run_id,)).fetchall()
    conn.close()

    for row in rows:
        symbol, data_src, start_date, end_date, interval = row[0], row[1], row[2], row[3], row[4] or "1m"
        dest = Path(output_dir) / f"r{run_id}/data" / f"kline_{symbol}.json"

        # 1. 尝试从缓存复制
        if cache.copy_to(symbol, data_src, interval, dest):
            logger.info(f"K线缓存命中: {symbol}")
            continue

        # 2. 缓存未命中，从 CSV 构建
        if not data_src or not Path(data_src).exists():
            logger.warning(f"K线数据源不存在: {symbol} → {data_src}")
            continue

        kline_dict = _build_kline_dict(data_src, symbol, interval, start_date, end_date)
        if kline_dict:
            cache.put(symbol, data_src, interval, kline_dict)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(kline_dict, f, ensure_ascii=False, default=str)
            logger.info(f"K线已导出: {symbol} → {dest.name}")


def export_optuna_json(db_path: str, output_dir: str, run_id: int) -> None:
    """导出 Optuna 优化数据 JSON（含 Plotly chart specs）"""
    from .queries.optuna import get_optuna_data

    optuna_data = get_optuna_data(db_path, run_id)
    if not optuna_data:
        return

    # 如果有 Optuna study，生成图表 spec
    conn = sqlite3.connect(db_path)
    study_rows = conn.execute(
        "SELECT study_name FROM run_studies WHERE run_id=?", (run_id,)
    ).fetchall()
    conn.close()

    charts_spec = {}
    if study_rows:
        try:
            study_db_url = f"sqlite:///{os.path.abspath(db_path)}"
            charts_spec = build_optuna_spec(study_db_url, study_rows[0][0])
        except Exception as e:
            logger.warning(f"Optuna chart spec 生成失败: {e}")

    result = {
        "study_name": optuna_data.get("study_name"),
        "trial_count": optuna_data.get("trial_count"),
        "trial_nums": optuna_data.get("trial_nums"),
        "trial_values": optuna_data.get("trial_values"),
        "best_params": optuna_data.get("best_params"),
        "param_scatter": optuna_data.get("param_scatter"),
        "charts": charts_spec,
    }
    _write_json(output_dir, f"r{run_id}/data/optuna.json", result)


def write_nav_json(db_path: str, output_dir: str) -> None:
    """导出全局导航数据 JSON"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, strategy, engine, symbols, status, created_at "
        "FROM runs ORDER BY id DESC"
    ).fetchall()
    conn.close()

    runs = [
        {
            "id": r[0], "strategy": r[1], "engine": r[2],
            "symbols": r[3], "status": r[4], "created": r[5],
        }
        for r in rows
    ]
    _write_json(output_dir, "data/nav.json", runs)


# ── 前端构建 ──────────────────────────────────────────────────


def build_frontend(output_dir: str) -> None:
    """检查 React 源码 hash，必要时触发 npm run build"""
    web_dir = Path(__file__).parent / "web"
    assets_dir = Path(output_dir) / "assets"

    if not (web_dir / "package.json").exists():
        logger.info("前端工程未初始化，跳过构建")
        return

    src_hash = _compute_dir_hash(web_dir / "src")
    hash_file = assets_dir / ".build_hash"

    if hash_file.exists() and hash_file.read_text().strip() == src_hash:
        logger.info("前端源码未变更，跳过构建")
        return

    logger.info("开始前端构建...")
    subprocess.run(
        ["npm", "run", "build"],
        cwd=str(web_dir), check=True,
        env={
            **os.environ,
            "VITE_OUT_DIR": str(assets_dir.absolute()),
        },
    )
    assets_dir.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(src_hash)
    logger.info("前端构建完成")


def write_entry_html(output_dir: str) -> None:
    """生成 output/index.html 单入口文件

    引用 Vite 构建的 JS bundle 和 plotly vendor，
    客户端通过 HashRouter 加载对应数据。
    """
    assets_dir = Path(output_dir) / "assets"

    # 查找 Vite 构建产物的实际文件名（含 hash）
    js_file = _find_built_file(assets_dir, "index-*.js")
    css_file = _find_built_file(assets_dir, "index-*.css")

    if not js_file:
        logger.warning("未找到 Vite 构建产物，生成降级入口")
        _write_fallback_html(output_dir)
        return

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>量化回测监控</title>
<link rel="stylesheet" href="assets/{css_file}">
<script src="assets/vendor/plotly.min.js"></script>
</head>
<body>
<div id="root"></div>
<script src="assets/{js_file}"></script>
</body>
</html>"""

    out_path = Path(output_dir) / "index.html"
    out_path.write_text(html, encoding="utf-8")
    logger.info(f"入口 HTML 已生成: {out_path}")


# ── 内部辅助 ──────────────────────────────────────────────────


def _build_kline_dict(
    csv_path: str,
    symbol: str,
    interval: str,
    start_date: str | None,
    end_date: str | None,
) -> dict | None:
    """从 CSV 构建 K 线 JSON dict (daily resampled + raw 降采样)

    返回格式见 K 线缓存机制章节。
    """
    try:
        df = pd.read_csv(csv_path)
        if "datetime" not in df.columns:
            if "date" in df.columns:
                df["datetime"] = df["date"]
            else:
                return None

        df["datetime"] = pd.to_datetime(df["datetime"])

        if start_date:
            df = df[df["datetime"] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df["datetime"] <= pd.Timestamp(end_date)]

        if df.empty:
            return None

        # 构建日线 resampled 数据
        df_daily = df.set_index("datetime")
        daily_ohlc = df_daily.resample("1d").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        ).dropna()

        daily_data = [
            {
                "datetime": str(idx.date()),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": int(row.volume),
            }
            for idx, row in daily_ohlc.iterrows()
        ]

        # 构建原始分钟线数据（降采样）
        raw_data = []
        total = len(df)
        skip = max(1, total // KLINE_DOWNSAMPLE_THRESHOLD) if total > KLINE_DOWNSAMPLE_THRESHOLD else 1

        for i in range(0, total, skip):
            row = df.iloc[i]
            raw_data.append({
                "datetime": str(row["datetime"]),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0)),
            })

        return {
            "symbol": symbol,
            "interval": interval,
            "csv_source": csv_path,
            "daily": daily_data,
            "raw": raw_data,
            "raw_count": total,
            "raw_downsampled": total > KLINE_DOWNSAMPLE_THRESHOLD,
            "raw_sample_max": KLINE_DOWNSAMPLE_THRESHOLD,
        }

    except Exception as e:
        logger.error(f"K线数据构建失败 [{symbol}]: {e}")
        return None


def _write_json(output_dir: str, rel_path: str, data: object) -> None:
    """写入 JSON 文件（自动创建目录）"""
    full_path = Path(output_dir) / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


def _compute_dir_hash(directory: Path) -> str:
    """计算目录下所有文件的内容 hash"""
    if not directory.exists():
        return ""
    hasher = hashlib.md5()
    for f in sorted(directory.rglob("*")):
        if f.is_file():
            hasher.update(f.read_bytes())
    return hasher.hexdigest()


def _find_built_file(directory: Path, glob_pattern: str) -> str | None:
    """查找构建产物文件，返回 basename"""
    import glob as _glob
    matches = _glob.glob(str(directory / glob_pattern))
    if matches:
        return Path(matches[0]).name
    return None


def _write_fallback_html(output_dir: str) -> None:
    """降级 HTML: 不依赖前端构建，纯文本导航"""
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>量化回测监控</title></head>
<body>
<h1>量化回测监控</h1>
<p>前端资源未构建。请先执行 <code>cd report/web && npm run build</code></p>
</body>
</html>"""
    (Path(output_dir) / "index.html").write_text(html, encoding="utf-8")
```

### A.4 `report/optimizer_report.py` 重写

```python
# -*- coding: utf-8 -*-
"""Optuna 优化报告 spec 生成

返回 Plotly JSON spec dict，不再生成 HTML。
"""

from __future__ import annotations

import logging
from typing import Any

import optuna
from optuna.visualization import (
    plot_optimization_history,
    plot_param_importances,
    plot_parallel_coordinate,
    plot_contour,
)

logger = logging.getLogger(__name__)


def build_optuna_spec(
    study_db_url: str,
    study_name: str,
) -> dict[str, Any]:
    """生成 Optuna 图表 Plotly JSON spec 字典

    Returns:
        {
            "optimization_history": {"data": [...], "layout": {...}},
            "param_importances": {"data": [...], "layout": {...}},
            "parallel_coordinate": {"data": [...], "layout": {...}},
            "contour": {"data": [...], "layout": {...}},
            "study_name": "...",
            "best_params": [...],
        }
    """
    study = optuna.load_study(study_name=study_name, storage=study_db_url)

    charts: dict[str, dict | None] = {}
    for plot_func, key in [
        (plot_optimization_history, "optimization_history"),
        (plot_param_importances, "param_importances"),
        (plot_parallel_coordinate, "parallel_coordinate"),
        (plot_contour, "contour"),
    ]:
        try:
            fig = plot_func(study)
            fig.update_layout(
                title=key,
                margin=dict(l=40, r=40, t=50, b=40),
                height=400,
            )
            charts[key] = fig.to_plotly_json()
        except Exception as e:
            logger.warning(f"Optuna 图表 [{key}] 生成失败: {e}")
            charts[key] = None

    best_params = []
    try:
        best = study.best_params
        best_params = [{"name": k, "value": v} for k, v in best.items()]
    except Exception:
        pass

    return {
        "study_name": study_name,
        "best_params": best_params,
        **charts,
    }
```

### A.5 `report/__init__.py` 精简后

```python
# -*- coding: utf-8 -*-
"""报告生成模块 — 数据导出 + 前端构建"""

from .builder import build_all, write_nav_json
from .reports import format_single_report, format_summary_report

__all__ = [
    "format_single_report",
    "format_summary_report",
    "build_all",
    "write_nav_json",
]
```

### A.6 `cli/commands/backtest.py` 变更

删除 `_build_optimization_report()` 函数（L674-L706），Optuna 报告生成合并到 `build_all()` 中（通过 `export_optuna_json()` 导出数据，前端 OptunaPage 渲染）。

原来的 `build_dashboard` import 和调用保持不变，只需确认新的 `build_all` 接口兼容：

```python
# 原来的 import（第53行）
from report import build_all as build_dashboard

# 调用处（第407-411行）：接口不变
build_dashboard(
    db_path=dm.store.db_path,
    output_dir="output",
    run_id=run_id,
)
```

### A.7 `report/queries/backtest.py` 补充

无需新增方法。现有的 `get_run_summary`, `get_equity_data`, `get_kline_data`, `get_trade_markers` 已足够。`builder.py` 中直接从 backtests 表查询完整数据，不再依赖 `get_kline_data`（改用 KlineCache 方案）。

保留 `queries/backtest.py` 的所有方法作为向后兼容（保留文件，标记部分方法为 deprecated）。

---

## Phase B: React 前端工程

### B.1 技术栈

- **React 18** + **TypeScript 5**
- **Vite 5** 构建工具
- **react-router-dom v6** (HashRouter)
- **react-plotly.js** Plotly React 封装
- **plotly.js** 本地化（从 CDN 下载到 `public/vendor/`）

### B.2 目录结构

```
report/web/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html                  # Vite 开发入口
├── public/
│   └── vendor/
│       └── plotly.min.js       # 本地化 Plotly (3.5MB)
└── src/
    ├── main.tsx                # 应用入口（挂载 HashRouter）
    ├── App.tsx                 # 路由配置
    ├── pages/
    │   ├── NavPage.tsx         # #/ 全局导航
    │   ├── RunPage.tsx         # #/run/:id 回测看板
    │   └── OptunaPage.tsx      # #/run/:id/optuna 优化详细
    ├── components/
    │   ├── KlineChart.tsx      # K 线图（日线/分钟线切换）
    │   ├── EquityChart.tsx     # 资金曲线 + 回撤双轴
    │   ├── ConvergenceChart.tsx # Optuna 收敛曲线
    │   ├── ParamImportanceChart.tsx  # 参数重要性
    │   ├── ParallelCoordChart.tsx    # 平行坐标
    │   ├── ContourChart.tsx          # 等高线
    │   ├── SymbolTable.tsx     # 品种汇总表（支持排序）
    │   ├── BacktestDetail.tsx  # 单回测详情面板
    │   ├── MetricCards.tsx     # 指标卡片组件
    │   └── Layout.tsx          # 通用布局（含导航面包屑）
    ├── data/
    │   └── loader.ts           # fetch JSON + 内存缓存
    ├── hooks/
    │   └── useFetchJson.ts     # 通用 fetch hook（loading/error/data）
    └── types/
        └── index.ts            # TypeScript 类型定义
```

### B.3 Vite 配置

```ts
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  base: "./",  // 相对路径，兼容 file:// 协议
  build: {
    outDir: process.env.VITE_OUT_DIR || "dist",
    rollupOptions: {
      output: {
        entryFileNames: "index-[hash].js",
        chunkFileNames: "chunk-[hash].js",
        assetFileNames: "index-[hash][extname]",
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
```

### B.4 依赖

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6.28",
    "react-plotly.js": "^2.6"
  },
  "devDependencies": {
    "@types/react": "^18.3",
    "@types/react-dom": "^18.3",
    "@types/react-plotly.js": "^2.6",
    "@vitejs/plugin-react": "^4.3",
    "typescript": "^5.6",
    "vite": "^5.4"
  }
}
```

### B.5 TypeScript 类型定义

```ts
// src/types/index.ts

export interface RunInfo {
  id: number;
  strategy: string;
  engine: string;
  symbols: number;
  status: string;
  created_at: string;
}

export interface NavData {
  id: number;
  strategy: string;
  engine: string;
  symbols: number;
  status: string;
  created: string;
}

export interface SummaryItem {
  symbol: string;
  total_return: number;     // 小数
  total_trades: number;
  win_rate: number;         // 百分比(0-100)
  max_drawdown: number;     // 百分比(0-100)
  sharpe: number;
  end_balance: number;
}

export interface KlinePoint {
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface KlineData {
  symbol: string;
  interval: string;
  csv_source: string;
  daily: KlinePoint[];
  raw: KlinePoint[];
  raw_count: number;
  raw_downsampled: boolean;
  raw_sample_max: number;
}

export interface DailyPoint {
  date: string;
  equity: number;
  daily_return: number;
  drawdown: number;
}

export interface EquityData {
  symbol: string;
  dates: string[];
  equity: number[];
  drawdown: number[];
}

export interface BacktestRecord {
  id: number;
  symbol: string;
  strategy: string;
  status: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  end_balance: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  data_src: string;
  kline_interval: string;
  strategy_version: string;
  git_hash: string;
  params: { name: string; value: number }[];
  daily: DailyPoint[];
}

export interface BestParam {
  name: string;
  value: number;
}

export interface ParamScatter {
  x_label: string;
  y_label: string;
  x_vals: number[];
  y_vals: number[];
  scores: number[];
}

export interface PlotlySpec {
  data: object[];
  layout: object;
}

export interface OptunaData {
  study_name: string;
  trial_count: number;
  trial_nums: number[];
  trial_values: number[];
  best_params: BestParam[];
  param_scatter: ParamScatter | null;
  charts: {
    optimization_history: PlotlySpec | null;
    param_importances: PlotlySpec | null;
    parallel_coordinate: PlotlySpec | null;
    contour: PlotlySpec | null;
  };
}
```

### B.6 路由与页面

```tsx
// src/App.tsx
import { HashRouter, Routes, Route } from "react-router-dom";
import NavPage from "./pages/NavPage";
import RunPage from "./pages/RunPage";
import OptunaPage from "./pages/OptunaPage";
import Layout from "./components/Layout";

export default function App() {
  return (
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<NavPage />} />
          <Route path="/run/:id" element={<RunPage />} />
          <Route path="/run/:id/optuna" element={<OptunaPage />} />
        </Routes>
      </Layout>
    </HashRouter>
  );
}
```

### B.7 数据加载器

```ts
// src/data/loader.ts
const CACHE = new Map<string, unknown>();

function getDataBase(runId?: number): string {
  if (runId !== undefined) {
    return `r${runId}/data`;
  }
  return "data";
}

export async function fetchJson<T>(relPath: string, runId?: number): Promise<T> {
  const base = getDataBase(runId);
  const url = `${base}/${relPath}`;
  
  if (CACHE.has(url)) {
    return CACHE.get(url) as T;
  }

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load ${url}: ${res.status}`);
  }

  const data: T = await res.json();
  CACHE.set(url, data);
  return data;
}

export function clearCache(): void {
  CACHE.clear();
}
```

### B.8 KlineChart 组件（含日线/分钟线切换）

```tsx
// src/components/KlineChart.tsx
import { useState } from "react";
import Plot from "react-plotly.js";
import type { KlineData, KlinePoint } from "@/types";

type ViewMode = "daily" | "raw";

function toCandlestick(data: KlinePoint[], name: string) {
  return {
    x: data.map((d) => d.datetime),
    open: data.map((d) => d.open),
    high: data.map((d) => d.high),
    low: data.map((d) => d.low),
    close: data.map((d) => d.close),
    type: "candlestick" as const,
    name,
    increasing: { line: { color: "#26A69A" } },
    decreasing: { line: { color: "#EF5350" } },
  };
}

function toVolume(data: KlinePoint[]) {
  const colors = data.map((d) =>
    d.close >= d.open ? "#26A69A" : "#EF5350"
  );
  return {
    x: data.map((d) => d.datetime),
    y: data.map((d) => d.volume),
    type: "bar" as const,
    name: "成交量",
    marker: { color: colors },
  };
}

export default function KlineChart({ data }: { data: KlineData }) {
  const [mode, setMode] = useState<ViewMode>("daily");
  const klineData = mode === "daily" ? data.daily : data.raw;

  if (!klineData || klineData.length === 0) {
    return <div className="empty-chart">无 K 线数据</div>;
  }

  const traces = [toCandlestick(klineData, "K线"), toVolume(klineData)];

  return (
    <div className="kline-chart">
      <div className="chart-toolbar">
        <span>{data.symbol}</span>
        <div className="view-toggle">
          <button
            className={mode === "daily" ? "active" : ""}
            onClick={() => setMode("daily")}
          >
            日线
          </button>
          <button
            className={mode === "raw" ? "active" : ""}
            onClick={() => setMode("raw")}
          >
            分钟线
            {data.raw_downsampled && (
              <span className="downsample-badge">(抽样)</span>
            )}
          </button>
        </div>
      </div>
      <Plot
        data={traces}
        layout={{
          height: 600,
          margin: { l: 60, r: 60, t: 40, b: 40 },
          hovermode: "x unified",
          showlegend: false,
          paper_bgcolor: "white",
          plot_bgcolor: "white",
          xaxis: { showgrid: true, gridcolor: "#eee" },
          yaxis: { showgrid: true, gridcolor: "#eee", title: "价格" },
        }}
        config={{ responsive: true, displaylogo: false }}
        useResizeHandler
        style={{ width: "100%" }}
      />
    </div>
  );
}
```

### B.9 构建流程

```bash
# 1. 安装依赖（首次或更新 package.json 后）
cd report/web && npm install

# 2. 下载 Plotly（首次初始化）
curl -L -o report/web/public/vendor/plotly.min.js \
  https://cdn.plot.ly/plotly-2.35.0.min.js

# 3. 开发模式
cd report/web && npm run dev
# → http://localhost:5173 预览（需 mock JSON 数据）

# 4. 生产构建（npm run build）
# → 产物写入 VITE_OUT_DIR 指定的目录（由 Python build_frontend 调用）
```

### B.10 RunPage 数据加载流程

```tsx
// src/pages/RunPage.tsx (核心结构)

function RunPage() {
  const { id } = useParams<{ id: string }>();
  const runId = Number(id);

  const { data: run } = useFetchJson<RunInfo>("run.json", runId);
  const { data: summary } = useFetchJson<SummaryItem[]>("summary.json", runId);
  const { data: backtests } = useFetchJson<BacktestRecord[]>("backtests.json", runId);
  const { data: equity } = useFetchJson<Record<string, EquityData>>("equity.json", runId);
  const { data: optuna } = useFetchJson<OptunaData | null>("optuna.json", runId);

  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [showOptuna, setShowOptuna] = useState(false);

  // 自动选第一个品种
  useEffect(() => {
    if (summary && summary.length > 0) {
      setSelectedSymbol(summary[0].symbol);
    }
  }, [summary]);

  // 加载 KlineData
  const { data: kline } = useFetchJson<KlineData>(
    `kline_${selectedSymbol}.json`, runId
  );

  return (
    <div className="run-page">
      <h1>r{runId} — {run?.strategy}</h1>
      <MetricCards run={run} backtests={backtests} />

      <section className="tab-bar">
        <button onClick={() => setShowOptuna(false)}>回测结果</button>
        {optuna && (
          <button onClick={() => setShowOptuna(true)}>参数优化</button>
        )}
      </section>

      {!showOptuna ? (
        <>
          <SymbolTable data={summary} onSelect={setSelectedSymbol} />
          {kline && <KlineChart data={kline} />}
          {equity?.[selectedSymbol] && (
            <EquityChart data={equity[selectedSymbol]} />
          )}
          <BacktestDetail
            backtests={backtests}
            selectedSymbol={selectedSymbol}
          />
        </>
      ) : (
        optuna && <OptunaCharts data={optuna} />
      )}
    </div>
  );
}
```

---

## Phase C: 集成清理

### C.1 变更要点

| 操作 | 文件 |
|------|------|
| 删除 | `report/templates/` (6 个 Jinja2 文件) |
| 删除 | `report/__init__.py` 中的 `build_report`, `_build_info`, `_build_kline_chart` |
| 删除 | `cli/commands/backtest.py` 中的 `_build_optimization_report` |
| 新建 | `report/kline_cache.py` |
| 新建 | `report/web/` 全部 React 前端工程 |
| 不变 | `report/queries/` SQL 查询层 |
| 不变 | `report/reports.py` 控制台文本报告 |
| 不变 | `data/manager.py` / `data/store.py` / `data/models.py` |

### C.2 执行步骤

```bash
# Step 1: 删除 Jinja2 模板
rm -rf report/templates/

# Step 2: 创建前端工程目录
mkdir -p report/web/public/vendor report/web/src/{pages,components,data,hooks,types}

# Step 3: 编写 package.json / tsconfig.json / vite.config.ts

# Step 4: 安装依赖 + 下载 Plotly
cd report/web && npm install
curl -L -o public/vendor/plotly.min.js \
  https://cdn.plot.ly/plotly-2.35.0.min.js

# Step 5: 修改 Python 代码（按照 Phase A 设计）

# Step 6: 验证前端可构建
npm run build
```

### C.3 保留文件说明

| 文件 | 说明 |
|------|------|
| `report/queries/backtest.py` | SQL 查询函数，builder.py 直接调用 + `export_backtests_json` 内联使用 |
| `report/queries/optuna.py` | `get_optuna_data()` 导出 Optuna trial 数据 |
| `report/reports.py` | `format_single_report` / `format_summary_report` 控制台文本报告，不受影响 |
| `report/charts.py` | 保留但不再直接生成 HTML；作为 Plotly spec 生成工具函数供引用 |
| `report/optimizer_report.py` | 重写为 `build_optuna_spec()` 返回 dict，删除 Jinja2 模板字符串 |

---

## Phase D: 验证

### D.1 全链路测试

```bash
# 1. 初始化前端依赖（首次）
cd report/web && npm install

# 2. 手动构建验证前端
npm run build
ls -la output/assets/

# 3. 全链路回测测试
bash tools/test-ma.sh

# 4. 打开报告
open output/index.html
```

### D.2 验证清单

| 验证项 | 检查方法 | 预期结果 |
|--------|---------|---------|
| K 线图渲染 | RunPage → 选择品种 → 查看 KlineChart | 蜡烛图 + 成交量柱状图正确，颜色红涨绿跌 |
| 日线/分钟线切换 | 点击"分钟线"按钮 | 切换到 1m 原始数据视图（降采样后 ≤5000 点） |
| 资金曲线 | RunPage 下半部 EquityChart | 权益双轴 + 回撤曲线正确 |
| 品种汇总表排序 | 点击表头 | 各列可排序 |
| HashRouter 导航 | NavPage → 点击 rN → RunPage | URL hash 变化正确，无刷新 |
| file:// 协议 fetch | 直接双击 `output/index.html` | Chrome/Firefox/Safari fetch JSON 正常 |
| 二次回测跳过前端构建 | 连续执行两次 `build_all()` | 第二次日志显示"跳过构建" |
| K 线缓存命中 | 二次构建同品种 | 日志显示"K 线缓存命中"，无 pd.read_csv |
| 缓存失效 | 修改 CSV → 再次构建 | 日志显示重新构建 K 线 JSON |
| Optuna 图表 | 含 optimizer 的 run → 切换到优化 Tab | 收敛曲线、参数重要性等 4 张图正常 |
| 降级 HTML | 删除 `output/assets/` → 构建 | 生成不含前端 bundle 的纯文本导航 |
| 控制台报告 | `python main.py report --id N` | `format_single_report` 正常输出 |
| 无 Jinja2 残留 | grep -r "jinja2\|Jinja2" report/ | 无输出 |
| 无独立 backtest HTML | ls output/rN/backtest_*.html | 文件不存在 |

---

## 附录

### A. 错误处理策略

| 场景 | 处理方式 |
|------|---------|
| K 线 CSV 不存在 | logger.warning + 跳过该品种，不阻塞其他品种导出 |
| K 线日期范围过滤后为空 | 同上 |
| Optuna study 加载失败 | logger.warning + export_optuna_json 返回空 |
| Plotly chart spec 生成失败 | charts dict 对应 key 设为 null，前端显示"图表不可用"占位 |
| Vite 构建失败 | logger.warning + 生成降级 HTML，不影响 JSON 导出 |
| 前端源码未变更 | hash 检测跳过 npm build |
| JSON 序列化 NaN/Infinity | `json.dump(data, ..., default=str)` 兜底 |
| fetch JSON 404（前端） | useFetchJson hook 返回 `{ error: "..." }`，页面显示错误提示 |

### B. 性能对比

| 操作 | 当前 Jinja2 方案 | 新方案 |
|------|-----------------|--------|
| K 线 CSV 读取 (50w 行) | 每次构建都 pd.read_csv → resample | 首次构建后缓存命中 → O(1) 复制 |
| Plotly HTML 内嵌 | 每个回测 800KB+ HTML | JSON 按需加载，React bundle ~200KB |
| 前端增量构建 | N/A | hash 检测，源码不变跳过 |
| 浏览器加载 | 独立 HTML 全部内联 | SPA + plotly vendor ~3.5MB (304 缓存) |
| 多品种报告 | 每个品种独立 800KB HTML | 单页按需加载品种 JSON |

### C. `data_src` 数据完整性

当前代码中 `data_src` 存入 backtests 表的路径如下：

```
CLI backtest.py:
  → dm.load_kline(sym, ..., return_path=True) → (df, filepath)
  → datasets.append((sym, df, filepath))
  → _persist_results → data_src=r.get('_data_src')
  → insert_backtest(..., data_src=data_src)
```

确保 `_persist_results` 中 `r['_data_src']` 不为空。对于 grid search 和 optuna search 模式，`_data_src` 由 `_run_grid_search` / `_run_optuna_search` 在 results 列表中注入。

### D. 需要关注的风险点

| 风险 | 影响 | 缓解 |
|------|------|------|
| `data_src` 为空的后测记录 | K 线 JSON 无法生成 | `export_kline_json` 中检查 `data_src IS NOT NULL` |
| Plotly vendor 未下载 | 前端图表白屏 | 构建脚本检查 `public/vendor/plotly.min.js` 存在 |
| Python 中 pd.read_csv 仍被调用（缓存未命中时） | 首次构建耗时长 | 仅首次发生，后续缓存命中 |
| Vite 构建环境依赖 Node.js | 部署环境需安装 Node 18+ | Phase C 文档说明依赖要求 |
| `file://` 协议下 CORS 限制 | fetch 跨域失败 | 使用相对路径 `./r1/data/...`；实测 Chrome/Safari/Firefox 均支持 |
| plotly.min.js 3.5MB 首次加载 | 首次打开报告慢 | 浏览器强缓存 + CDN 本地化 |

### E. Plotly 版本选择

当前模板引用 `plotly-latest.min.js`（CDN），新方案锁定版本 `plotly-2.35.0.min.js` 本地化。版本选择理由：
- react-plotly.js 2.6.x 兼容 plotly.js 2.x
- 使用 `createPlotlyComponent` 通过 `window.Plotly` 而非 ES import（避免 bundle 体积爆炸）
- 在 `index.html` 中 `<script src="assets/vendor/plotly.min.js"></script>` 全局加载