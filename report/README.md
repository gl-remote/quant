# report 模块 — 权责划分与模块关系

> 版本: 0.2.0 | 最后更新: 2026-05-28

---

## 一、模块定位

`report` 是报告生成模块，负责将回测和优化结果转化为可离线浏览的静态 HTML 报告。它是整个系统的**出口层**——只读数据、不写业务数据、不执行回测。

**一句话**：report 是"把已有的结果变成可看的页面"。

---

## 二、与其他模块的关系

```
                    ┌──────────────┐
                    │   cli/main   │  CLI 入口: report 子命令
                    └──────┬───────┘
                           │ build_all()
                           ▼
                    ┌──────────────┐
                    │   report/    │  本模块（报告生成）
                    └──────┬───────┘
                           │ 读数据
                           ▼
                    ┌──────────────┐
                    │    data/     │  SQLite + peewee + CSV
                    └──────────────┘
                           ▲ 读写
                           │
              ┌────────────┼────────────┐
              │            │            │
        backtest/    optimizer/       ...
        执行回测      参数搜索
                      (调用 backtest
                       作为评估器)
```

| 模块 | report 如何与之交互 | 方向 |
|------|-------------------|------|
| `data/` | 通过 `DataManager` 读取 runs/backtests/equity/optuna 数据；通过 CSV 文件读取 K 线原始数据 | 读 |
| `backtest/` | 不直接交互。回测结果写入 `data/`，report 从中读取 | 无 |
| `optimizer/` | 不直接交互。optimizer 调用 backtest 评估每个 trial，结果写入 `data/`。report 通过 `data/` + `build_optuna_spec()` 生成图表 | 无 |
| `strategies/` | 完全不交互 | 无 |
| `common/` | 可能复用纯函数工具，但不依赖 | 可选 |
| `config/` | 不直接交互 | 无 |
| `cli/main.py` | `build_all()` 由 CLI 的 `report` 子命令调用 | 被调用 |

**关键原则**：report 是只读消费者。optimizer 在 backtest 命令内部被调用——optimizer 调用 backtest 作为子过程，每次 trial 写入 `data/`，report 从 `data/` 读取结果生成报告。

---

## 三、内部结构

```
report/
├── builder.py               # 编排入口 — build_all()
│   ├── 调用 writer 导出 JSON
│   ├── 调用 reporter 生成图表 spec
│   ├── 触发前端构建 (npm run build)
│   └── 写入入口 HTML（数据内联）
├── writer/
│   └── json_writer.py       # JSON 导出: run/summary/backtests/equity/kline/optuna/nav
│       └── _build_kline_dict()  # CSV→dict 转换（唯一实现，builder 通过 import 调用）
├── cache/
│   ├── build.py             # BuildCache — 数据指纹增量决策
│   └── kline.py             # KlineCache — K 线 CSV→JSON 转换结果复用
├── reporter/
│   ├── optimizer.py         # build_optuna_spec() — Optuna 图表 ECharts option 生成
│   └── text.py              # 文本报告生成（如有）
├── web/                     # React 前端（详见 web/DEVELOPMENT.md）
│   └── src/ ...
└── __init__.py              # 公开 build_all
```

### 权责划分

| 子模块 | 职责 | 不负责 |
|--------|------|--------|
| `builder.py` | 编排构建流程、增量决策、HTML 生成 | 具体数据格式转换 |
| `writer/json_writer.py` | CSV/DB → JSON dict 转换 + 文件写入 | 构建流程、缓存决策 |
| `cache/` | 数据指纹计算、K 线转换缓存 | 数据格式、构建流程 |
| `reporter/` | ECharts option 生成、文本报告 | 文件写入、数据读取 |
| `web/` | 前端渲染、用户交互 | 后端数据逻辑 |

---

## 四、构建流程

```
build_all(output_dir, run_id)
│
├── 增量模式 (incremental=True, 默认)
│   ├── 逐个比对数据指纹 → 仅导出变更的数据类型
│   ├── K 线使用 KlineCache 复用转换结果
│   └── 前端源码哈希比对 → 仅变更时 rebuild
│
├── 全量模式 (incremental=False)
│   └── 无条件导出全部 7 种数据类型 + 重建前端
│
├── build_frontend()         ← cd web && npm run build
│   └── 输出 output/assets/index.js
│
└── write_entry_html()       ← 仅数据变更时执行
    └── 读取所有 output/r*/data/*.json + index.js
        → 注入为 window.__DATA__ + <script src="...">
        → 写入 output/index.html
```

---

## 五、数据产出物

| JSON 文件 | 生成函数 | 数据来源 |
|-----------|---------|---------|
| `run.json` | `export_run_json` | `DataManager.get_run_info()` |
| `summary.json` | `export_summary_json` | `DataManager.get_run_summary()` |
| `backtests.json` | `export_backtests_json` | `DataManager.get_backtests_for_run()` |
| `equity.json` | `export_equity_json` | `DataManager.get_equity_data()` |
| `kline_{symbol}.{interval}.json` | `export_kline_json` | CSV 文件 → `_build_kline_dict()` |
| `optuna.json` | `export_optuna_json` | `DataManager.get_optuna_data()` + `build_optuna_spec()` |
| `nav.json` | `write_nav_json` | `DataManager.get_all_runs()` |

---

## 六、开发约定

### 6.1 添加新数据类型

1. 在 `writer/json_writer.py` 中新增 `export_xxx_json()` 函数
2. 在 `writer/__init__.py` 中导出
3. 在 `builder.py` 的 `build_all()` 中加入调用（增量和全量两个分支）
4. 在 `_dispatch_export()` 中添加分发 case
5. 前端如需消费，在 `types/index.ts` 添加对应 interface

### 6.2 修改 JSON 输出结构

**必须同步检查**：
- `writer/json_writer.py` — 修改输出 dict
- `web/src/types/index.ts` — 同步 TypeScript 类型
- 前端消费组件 — 可能需适配新字段

### 6.3 缓存失效

以下情况需手动清除缓存（`rm -rf output/.build_cache output/.kline_cache`）：
- 修改了 `_build_kline_dict` 或任何 JSON 导出逻辑
- 前端构建工具链升级
- 缓存与实际数据不一致时

### 6.4 调试

```python
import logging
logging.getLogger("report").setLevel(logging.DEBUG)
```

---

## 七、AI 协作提示

与 AI 讨论 report 模块时，提供以下上下文：

> report 是报告生成模块。它从 `data/` 模块读取数据（通过 DataManager），导出为 JSON 文件，然后构建 React 前端（`web/`），最后将所有 JSON + JS 内联到单个 HTML 文件中。前端通过 `window.__DATA__` 读取数据，不使用 fetch()。时区处理：全程 UTC timestamp，显示层用 `new Date()` 转本地时区。`builder.py` 是编排入口。`_build_kline_dict` 的唯一实现在 `writer/json_writer.py`，`builder.py` 通过 import 调用。