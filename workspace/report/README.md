# report 模块 — 权责划分与模块关系

> 版本: 0.4.0 | 最后更新: 2026-06-10

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
        backtest/       ...
        执行回测 + 参数搜索
        (含 optimizer 逻辑，
         调用自身作为评估器)
```

| 模块 | report 如何与之交互 | 方向 |
|------|-------------------|------|
| `data/` | 通过 `DataManager` 读取 runs/backtests/equity/optuna 数据；通过 CSV 文件读取 K 线原始数据 | 读 |
| `backtest/` | 不直接交互。回测和参数优化结果写入 `data/`，report 从中读取 | 无 |
| `strategies/` | 完全不交互 | 无 |
| `common/` | 可能复用纯函数工具，但不依赖 | 可选 |
| `config/` | 不直接交互 | 无 |
| `cli/main.py` | `build_all()` 由 CLI 的 `report` 子命令调用 | 被调用 |

**关键原则**：report 是只读消费者。参数优化逻辑在 `backtest/optimizer.py` 内部调用回测引擎，每次 trial 写入 `data/`，report 从 `data/` 读取结果生成报告。

---

## 三、内部结构

```
report/
├── builder.py               # thin 编排层 — build_all()
│   ├── 顶层创建 DataManager，通过依赖注入传递给 writer 层
│   ├── _run_data_exports() 调度 writer/json_writer.py 的 export_*_json
│   ├── _collect_*_fingerprint() 收集数据指纹用于增量决策
│   ├── build_frontend() 触发前端构建 (npm run build)
│   └── write_entry_html() 写入入口 HTML（JS + CSS + JSON 全内联）
├── writer/
│   └── json_writer.py       # 唯一负责：读 DB/CSV → 格式化 → 写 JSON
│       ├── export_*_json(output_dir, run_id, dm=None)  # 接受 dm 依赖注入
│       └── build_kline_dict()  # CSV→dict 转换（唯一实现，公开导出）
├── cache/
│   ├── build.py             # BuildCache — 数据指纹增量决策
│   └── kline.py             # KlineCache — K 线 CSV→JSON 转换结果复用
├── reporter/
│   ├── optimizer.py         # build_optuna_spec() — Optuna 图表 ECharts option 生成
│   └── text.py              # 文本报告生成（如有）
├── web/                     # React 18 + TypeScript + Tailwind v4 + AntD 前端
│   ├── src/
│   │   ├── App.tsx          # HashRouter + AntD ConfigProvider（CSS 变量主题统一）
│   │   ├── index.css         # :root 主题变量 + Tailwind @theme 扩展（语义色体系）
│   │   ├── config/           # chartConfig、qlIdMapping 等
│   │   ├── hooks/            # useKlineChart、useFetchJson
│   │   ├── types/            # 按领域拆分的类型文件（run/kline/backtest/equity/optuna）
│   │   ├── utils/            # 指标计算、交易标记、时间解析
│   │   ├── components/
│   │   │   ├── layout/       # Layout, QlPanel
│   │   │   ├── charts/       # KlineChart, EquityChart, OptunaCharts, EChartsChart
│   │   │   └── data/         # SymbolTable, MetricCards, RunLogs
│   │   └── pages/
│   │       ├── NavPage.tsx   # 回测记录导航页
│   │       └── run/          # 回测详情页（useRunData, RunHeader, index）
│   ├── package.json
│   └── vite.config.ts
└── __init__.py              # 公开 build_all
```

### 权责划分

| 子模块 | 职责 | 不负责 |
|--------|------|--------|
| `builder.py` | thin 编排层：统一创建 DataManager 并依赖注入、增量决策、调度前端构建、HTML 生成 | 具体数据格式化、写 JSON 文件 |
| `writer/json_writer.py` | 唯一负责：CSV/DB → JSON dict 转换 + 文件写入，export_* 接受 dm 参数依赖注入 | 构建流程决策、缓存管理 |
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
| `kline_{symbol}.{interval}.json` | `export_kline_json` | CSV 文件 → `build_kline_dict()` |
| `optuna.json` | `export_optuna_json` | `DataManager.get_optuna_data()` + `build_optuna_spec()` |
| `nav.json` | `write_nav_json` | `DataManager.get_all_runs()` |

---

## 六、开发约定

### 6.1 添加新数据类型

1. 在 `writer/json_writer.py` 中新增 `export_xxx_json(output_dir, run_id, dm=None)` 函数
2. 在 `writer/__init__.py` 中导出
3. 在 `builder.py` 的 `_run_data_exports()` 的 `export_tasks` 列表中追加一条（类型名 + 指纹收集函数 + 导出函数）
4. 如需要自定义增量逻辑（非通用指纹比对），在 `builder.py` 中添加 `_export_xxx_with_incremental(cache, dm, output_dir, run_id)` 并在 `_run_data_exports` 的分支中调用
5. 前端如需消费，在 `types/index.ts` 添加对应 interface

### 6.2 修改 JSON 输出结构

**必须同步检查**：
- `writer/json_writer.py` — 修改输出 dict
- `web/src/types/index.ts` — 同步 TypeScript 类型
- 前端消费组件 — 可能需适配新字段

### 6.3 缓存失效

以下情况需手动清除缓存（`rm -rf output/.build_cache output/.kline_cache`）：
- 修改了 `build_kline_dict` 或任何 JSON 导出逻辑
- 前端构建工具链升级
- 缓存与实际数据不一致时

### 6.4 主题与组件库

**单一事实来源**：所有颜色、圆角、间距定义在 `web/src/index.css` 的 `:root` 中，Tailwind 通过 `@theme` 引用同一组 CSS 变量，AntD 通过 `ConfigProvider` 在运行时读取 CSS 变量。

**语义色优先**：优先使用 `bg-surface`、`text-text-secondary`、`border-border` 等语义类名，避免直接使用 `bg-white`、`text-slate-600` 等色阶类名。如需修改主题色，只改 `:root` 一处。

**AntD 替换规则**：
- 通用展示组件（Table、Breadcrumb、Segmented、Input.Search 等）优先使用 AntD
- 业务强相关或有多色视觉需求的组件（KlineChart、EquityChart、指标按钮）保持自建
- AntD 的 token 自动从 CSS 变量读取，视觉风格与 Tailwind 保持一致

### 6.5 调试

```python
from loguru import logger
# report 模块的日志通过全局 loguru logger 控制
logger.remove()
logger.add(sys.stderr, level="DEBUG")
```

---

## 七、AI 协作提示

与 AI 讨论 report 模块时，提供以下上下文：

> report 是报告生成模块。它从 `data/` 模块读取数据（通过 DataManager），导出为 JSON 文件，然后构建 React 前端（`web/`），最后将所有 JSON + JS 内联到单个 HTML 文件中。前端通过 `window.__DATA__` 读取数据，不使用 fetch()。时区处理：全程 UTC timestamp，显示层用 `new Date()` 转本地时区。`builder.py` 是 thin 编排层，统一创建 DataManager 实例并通过依赖注入传递给 writer 层。`build_kline_dict` 的唯一实现在 `writer/json_writer.py`，公开导出，builder 通过 import 调用。
>
> 前端技术栈：React 18 + TypeScript + Tailwind v4 + AntD。语义色定义在 `index.css` 的 `:root` 中，Tailwind 通过 `@theme` 引用，AntD 通过 `ConfigProvider` 读取。组件目录按职责分组（layout/charts/data），类型按领域拆分（run/kline/backtest/equity/optuna）。通用展示组件优先使用 AntD（Table、Segmented、Breadcrumb、Input.Search），业务强相关的图表组件保持自建。CSS 使用语义类名（`bg-surface`、`text-text`、`border-border`），避免色阶硬编码。

---

## 八、改造为实时 Web 交互的任务列表（给未来 AI 的改造建议）

> **当前架构**：静态报告模式 — Python 把 DB 数据导出为 JSON 文件 → 内联到单个 HTML → 前端从 `window.__DATA__` 读数据 → 纯静态浏览
> **目标架构**：实时 Web 模式 — Python 启动 HTTP/WebSocket 服务 → 前端通过 API 直连数据库 → 数据变更实时推送到前端 → 动态交互

以下是分阶段实施的任务清单，按依赖关系排序。

### 阶段 1：后端 API 层（最小改动，先跑起来）

| # | 任务 | 涉及文件 | 说明 |
|---|------|---------|------|
| 1.1 | 创建 `report/server.py` | 新建 | 用 FastAPI（推荐）或 Flask 启动 HTTP 服务，路由 `/api` |
| 1.2 | 把 `writer/json_writer.py` 的 `export_*_json` 拆分为"数据获取函数"和"文件写入函数" | `report/writer/json_writer.py` | 当前函数是"读 DB → 格式化 → 写文件"三合一。拆出纯数据函数 `get_*_data(run_id, dm)`，返回 dict/list，不写文件 |
| 1.3 | 为每个 JSON 输出创建对应 API 路由 | `report/server.py` | `/api/runs` → `get_all_runs()`；`/api/runs/{id}` → `get_run_info()`；`/api/runs/{id}/summary` → `get_run_summary()`；`/api/runs/{id}/backtests` → `get_backtests_for_run()`；`/api/runs/{id}/equity` → `get_equity_data()`；`/api/runs/{id}/kline?symbol=X&interval=1m` → `build_kline_dict()`；`/api/runs/{id}/trades` → trade 数据；`/api/runs/{id}/optuna` → optuna 数据 |
| 1.4 | 复用 `DataManager`（从 `data/` 模块导入）作为 API 层的数据访问入口 | `report/server.py` | 不要写新的 SQL 查询，所有数据库访问走 `DataManager` |
| 1.5 | 添加 `/api/health` 健康检查端点 | `report/server.py` | 返回 `{"status": "ok", "db_size": "..."}` |

### 阶段 2：前端改造（数据来源切换）

| # | 任务 | 涉及文件 | 说明 |
|---|------|---------|------|
| 2.1 | 改造 `web/src/data/loader.ts` 的 `fetchJson()` | `report/web/src/data/loader.ts` | 当前 `fetchJson()` 只从 `window.__DATA__` 读。改为：如果 `window.__DATA__` 存在（静态报告模式，保留兼容）→ 走内联；否则 → `fetch(\`/api/...\`)` |
| 2.2 | 把 `useFetchJson` 从"加载一次就不变"改为"可刷新"的 hook | `report/web/src/hooks/useFetchJson.ts` | 添加 `refresh()` 方法和手动触发刷新的能力 |
| 2.3 | NavPage 和 RunPage 改为从 API 动态加载 | `report/web/src/pages/NavPage.tsx`, `report/web/src/pages/RunPage.tsx` | 不需要改动太大，`useFetchJson` 的接口保持稳定即可 |
| 2.4 | **保留静态模式的兼容性** | `report/web/src/data/loader.ts` | 必须保证 `window.__DATA__` 存在时仍能工作 —— 这是当前的发布产物，不能破坏 |
| 2.5 | 添加 API base URL 配置（支持 dev/prod） | `report/web/src` 新建 `config.ts` | 开发模式 `http://localhost:8000`，生产模式同域 `/api` |

### 阶段 3：实时同步（数据库变更 → 前端自动刷新）

| # | 任务 | 涉及文件 | 说明 |
|---|------|---------|------|
| 3.1 | 设计数据库变更通知机制 | `report/server.py` | 方案 A（简单）：轮询 `/api/runs/{id}` 对比版本号/时间戳；方案 B（实时）：WebSocket `ws://.../ws/runs/{id}` 推送变更 |
| 3.2 | 如果选 WebSocket 方案：在 API 层添加 `/ws` 端点 | `report/server.py` | 客户端订阅特定 run_id，服务端推送 "数据已变更" 事件 |
| 3.3 | 前端添加 WebSocket hook `useRunSubscription(runId)` | `report/web/src/hooks/` | 连接后自动刷新对应页面的数据 |
| 3.4 | **关键决策点**：数据库变更由谁触发通知？ | `data/` 模块 vs `backtest/` 模块 | 方案 1：`DataManager` 写入数据后主动触发 WebSocket 广播；方案 2：`backtest/` 在完成一次回测后调用 `report.notify_run_updated(run_id)`；**推荐方案 2** —— 职责边界更清晰：data 只管读写数据，report 作为发布者接收通知后推送到前端 |
| 3.5 | 在 `report/__init__.py` 添加 `notify_run_updated(run_id)` 公开函数 | `report/__init__.py`, `report/server.py` | backtest 完成后调用它来触发前端刷新 |

### 阶段 4：去除对文件系统的依赖（真正" Web 化"）

| # | 任务 | 涉及文件 | 说明 |
|---|------|---------|------|
| 4.1 | 废弃 `builder.py` 中 `_build_preload_script()` 的内联逻辑 | `report/builder.py` | 动态模式下不再需要把 JSON 打包到 HTML |
| 4.2 | `write_entry_html()` 改为输出标准 Vite 的 index.html（不内联数据） | `report/builder.py` | 或直接让 Vite 负责生产构建，Python 不参与 HTML 生成 |
| 4.3 | **保留回退路径**：`build_all()` 仍应支持"静态报告"模式（离线场景仍有用） | `report/builder.py` | 在 `incremental=True/False` 之外加一个 `mode` 参数，取值 `"static"` 或 `"dynamic"` |

### 阶段 5：部署与运维

| # | 任务 | 说明 |
|---|------|------|
| 5.1 | CLI 添加 `quant serve` 命令 | 启动 FastAPI + 前端构建产物的静态服务 |
| 5.2 | 添加 `requirements.txt` 或 `pyproject.toml` 新增 `fastapi`, `uvicorn` 依赖 | |
| 5.3 | 添加开发模式启动脚本 | `python -m report.server`（自动热重载前端 + 后端） |
| 5.4 | 考虑 HTTPS / 认证 | 若未来多用户使用，需添加登录与权限隔离 |

### 不要做的事（反模式提醒）

1. ❌ 不要在前端写 SQL 或直接连接数据库 — 必须走 API 层
2. ❌ 不要在 API 层做业务计算（如权益曲线拟合、Optuna 分析） — 这些逻辑在 `data/` 或独立模块里
3. ❌ 不要把 `write_entry_html()` 的内联方案和动态 API 方案混在同一代码路径太久 — 尽早分叉或加明确的 `mode` 参数
4. ❌ 不要忽略静态模式 — 离线/邮件发送/快速分享仍是静态报告的优势场景

### 关键点提醒

- **当前 `writer/json_writer.py` 的 `export_*_json` 函数已经是"读 DB → 格式化"的独立单元，拆出纯数据函数代价很小** —— 这是本次重构为未来改造埋下的伏笔
- **`DataManager` + peewee models 已经抽象了数据库访问**，API 层不需要关心 SQLite 细节
- **前端组件（KlineChart、EquityChart、MetricCards 等）已经是纯数据驱动**，只要 `useFetchJson` 返回的数据结构不变，组件无需改动