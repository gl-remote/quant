# report/web 前端开发指南

> 版本: 0.2.0 | 最后更新: 2026-05-28

---

## 一、架构概览

```
web/
├── vite.config.ts          # Vite 构建配置（单文件输出 + file:// 支持）
├── tsconfig.json            # TypeScript 配置
├── package.json             # 依赖: React 18 + ECharts 6 + lightweight-charts 5
├── index.html               # Vite 入口 HTML（含 <div id="root">）
├── public/vendor/           # 手动管理的静态资源
└── src/
    ├── main.tsx             # 入口：注入全局 CSS，挂载 <App>
    ├── App.tsx              # 根组件：HashRouter + 路由 / 与 /run/:id
    ├── types/index.ts       # 所有 TypeScript 类型定义
    ├── data/
    │   ├── loader.ts        # window.__DATA__ 数据读取
    │   └── qlIdMapping.ts   # 页面板块 ID 映射（用于自动化测试定位）
    ├── hooks/
    │   └── useFetchJson.ts  # React Hook：数据加载 + loading/error 状态
    ├── pages/
    │   ├── NavPage.tsx      # 导航页（所有 run 列表）
    │   └── RunPage.tsx      # 回测详情页（双 Tab：回测 + 参数优化）
    ├── components/
    │   ├── Layout.tsx       # 页面布局外壳
    │   ├── MetricCards.tsx  # 指标卡片（总收益率/夏普/最大回撤…）
    │   ├── SymbolTable.tsx  # 品种汇总表（可点击选择品种）
    │   ├── QlPanel.tsx      # 统一面板容器（含 qlId 定位属性）
    │   ├── KlineChart.tsx   # K 线图（lightweight-charts，含 SMA 均线）
    │   ├── EquityChart.tsx  # 资金曲线（ECharts）
    │   ├── EChartsChart.tsx # ECharts 通用图表组件
    │   ├── BacktestDetail.tsx # 单回测详情（指标 + 交易记录 + 日权益）
    │   └── OptunaCharts.tsx # 优化面板（最优参数 + 4 张 ECharts 图表）
    ├── test/setup.ts        # vitest 测试环境配置
    └── components/*.test.*  # 组件单元测试
```

---

## 二、核心设计决策

### 2.1 单文件打包 + 数据预加载

**原因**：报告需支持 `file://` 协议直接打开，不能依赖 HTTP 服务器。

- Vite 配置 `manualChunks: undefined` 禁用代码分割，所有 JS/CSS 打包为单个 `index.js`
- Python 后端 (`builder.py`) 将所有 JSON 数据文件读取并序列化，注入到 HTML 的 `<script>window.__DATA__ = {...};</script>`
- 前端通过 `loader.ts` 的 `fetchJson()` 从 `window.__DATA__` 读取，**绝对不允许**使用 `fetch()` 或任何网络请求

### 2.2 HashRouter

使用 `HashRouter` 而非 `BrowserRouter`，因为 `file://` 协议不支持 HTML5 History API。所有路由通过 `#/` 前缀工作。

### 2.3 UTC 时间戳全链路

| 层 | 存储格式 | 说明 |
|---|---------|------|
| CSV | `"2025-07-02 09:06:00"` | 北京时间字符串 |
| JSON | `1751418360` | UTC Unix timestamp (秒) |
| 前端 `KlinePoint.datetime` | `number` | 同上 |
| 图表显示 | `2025/07/02 09:06` | `new Date()` 转本地时区 |

**关键规则**：
- 数据层始终保持 UTC timestamp，不做任何时区偏移
- 显示层统一用 `new Date(timestamp * 1000)` 转本地时间
- lightweight-charts 的 `tickMarkFormatter` 和 `timeFormatter` 都使用 `new Date()` 处理

### 2.4 QlId 定位体系

每个页面板块标注 `data-ql-id` 属性，值从 `qlIdMapping.ts` 获取，用于自动化测试定位元素。格式：`RUN-KLINE-CONTAINER`、`RUN-OPT-HISTORY` 等。

---

## 三、数据流

```
Python report build
  │
  ├── export_*_json()         生成各 JSON 文件到 project_data/reports/runs/r{id}/data/
  │
  ├── build_frontend()        cd web && npm run build → project_data/reports/assets/index.js
  │
  └── write_entry_html()      读取 index.js + 所有 JSON → 注入到 project_data/reports/index.html
                                ┌─────────────────────────────────┐
                                │ <script>window.__DATA__ = {     │
                                │   "data/nav.json": {...},       │
                                │   "r1/data/run.json": {...},    │
                                │   "r1/data/optuna.json": {...}, │
                                │   ...                           │
                                │ };</script>                     │
                                │ <script src="assets/index.js">  │
                                └─────────────────────────────────┘

前端运行时:
  useFetchJson("optuna.json", runId)
    → fetchJson("optuna.json", runId)
    → 查找 key = "r{runId}/data/optuna.json"
    → 返回 window.__DATA__[key]
```

---

## 四、图表库使用注意事项

### 4.1 lightweight-charts (K 线图)

**文件**: `KlineChart.tsx`

- 版本 5.2.0，类型 `Time = UTCTimestamp | BusinessDay | string`
- **时间轴格式化**：用 `timeScale.tickMarkFormatter` 而非直接改数据。库将 UTCTimestamp 显示为 UTC，需在 formatter 中用 `new Date()` 转本地时间
- **十字线格式化**：`localization.timeFormatter` 只影响十字线标签，不影响时间轴
- **`timeFormatter` 设置后 `dateFormat` 失效**：这是库的设计
- **图表初始化**：useEffect 依赖 `klineData`（非 `[]`），确保数据到达后再创建图表
- **SMA 均线**：前端独立计算（`calculateSMA`），与后端策略无关，仅为可视化

### 4.2 ECharts (资金曲线 + Optuna 图表)

**文件**: `EChartsChart.tsx`

- 版本 6.1.0，按需注册组件（CanvasRenderer + Bar/Line/Scatter/Parallel + 交互组件）
- 图表 option 由 Python `report/reporter/optimizer.py` 生成，前端直接传给 `setOption(option, true)`
- **不要**在前端修改 ECharts option 结构——格式约定由 Python 端控制

---

## 五、新增页面/组件规范

1. **数据加载**：一律使用 `useFetchJson<T>(jsonFileName, runId?)`，禁止手写 fetch
2. **类型定义**：新增数据类型必须在 `types/index.ts` 中定义 `interface`，与 Python 输出的 JSON 结构严格一致
3. **QlId**：每个可交互/可验证的 UI 板块标注 `data-ql-id`，值添加到 `qlIdMapping.ts`
4. **面板容器**：使用 `QlPanel` 包裹，统一外观和定位
5. **Loading/Empty 状态**：参考 `KlineChart.tsx` 的处理模式——loading 时显示 spinner，无数据时显示提示文字
6. **构建验证**：修改后运行 `npm run build`，确保单文件打包成功且无 TypeScript 错误

---

## 六、构建命令

| 命令 | 说明 |
|------|------|
| `npm run dev` | 开发模式，Vite HMR |
| `npm run build` | 生产构建（lint → tsc → vite build） |
| `npm run test` | 运行 vitest 单元测试 |
| `npm run lint` | ESLint 检查 |

Python 端通过 `builder.py` 中的 `build_frontend()` 调用 `npm run build`，输出目录由 `VITE_OUT_DIR` 环境变量控制。

---

## 七、已知问题

1. **lightweight-charts 5.2.0 时区行为**：UTCTimestamp 在时间轴和十字线上均显示为 UTC，不自动转本地时区。已在 `tickMarkFormatter` 和 `timeFormatter` 中手动处理。
2. **单文件体积**：echarts (~1MB) + lightweight-charts + 业务代码使打包后 JS 约 1MB，已将 `chunkSizeWarningLimit` 调至 2000。如后续更大，可考虑 external 引入或 CDN 方案（但会被坏 file:// 支持）。
3. **Optuna param_importances**：当 trial 数量不足或目标值无差异时，`optuna.importance.get_param_importances` 返回空，前端显示降级提示。

---

## 八、AI 协作开发指南（提示词工程）

以下是为后续开发与 AI 高效协作的约定。在与 AI 对话时，应将本节内容作为上下文提供。

### 8.1 项目背景（一句话版）

> 这是一个量化交易回测报告系统。前端是 React 18 + TypeScript + Vite 构建的单文件 SPA，所有 JSON 数据在构建时内联到 `window.__DATA__`，支持 `file://` 离线打开。后端是 Python，通过 `builder.py` 编排 JSON 导出 + 前端构建 + HTML 注入。

### 8.2 讨论新需求时，先给 AI 看这些文件

```
report/web/DEVELOPMENT.md    ← 本文档（架构 + 约定）
report/web/src/types/index.ts ← 所有类型定义
plan.md                       ← 项目路线图 + 已知缺陷
```

然后描述需求时附上相关的 Python 端 JSON 生成代码（如 `report/writer/json_writer.py` 中的 `export_*` 函数），让 AI 理解前后端数据的完整链路。

### 8.3 需求描述范式

对 AI 描述任务时，按以下结构：

```
**Task**: 一句话描述要做什么

**Data Source**: JSON 文件是 xx.json，由 Python 的 export_xx_json() 生成
**Expected Behavior**: 用户应该看到什么 / 交互应该怎样
**Constraint**:
  - 不能使用 fetch()（数据在 window.__DATA__ 里）
  - 不能引入新的 npm 依赖（除非明确允许）
  - 必须支持 file:// 协议
```

### 8.4 Spec-Driven Development 流程（强制）

重大功能开发（跨多个文件的改动）必须走 SDD 流程：

```
1. doc.md    — 分析需求 + 技术方案 + 涉及文件 + 数据流
2. tasks.md  — 拆解为可独立执行的子任务
3. 逐任务执行 — 完成一个标记一个
4. summary.md — 总结改动和验证结果
```

产物放 `.comate/specs/{feature_name}/` 目录。**严禁**跳过此流程直接写代码。

### 8.5 AI 容易犯的错误（提前告知，避免走弯路）

| 陷阱 | 正确做法 |
|------|---------|
| 用 `fetch()` 加载数据 | 用 `useFetchJson`，从 `window.__DATA__` 读 |
| 给 lightweight-charts 的 UTCTimestamp 加时区偏移 | 保持原始 UTC timestamp，在 `tickMarkFormatter` / `timeFormatter` 中用 `new Date()` 转换 |
| 改 `types/index.ts` 但忘记同步 Python JSON 输出 | Python 和 TypeScript 类型必须一一对应，改之前先看 `json_writer.py` |
| 引入新 npm 包破坏 `file://` 支持 | 新增依赖需确认不依赖 HTTP 请求 |
| 修改 Vite 配置为多 chunk 输出 | 必须保持单文件 `index.js`，否则 `builder.py` 的 HTML 内联会失败 |
| 只改 `json_writer.py` 忘了 `builder.py` 也有同名函数 | 两者曾重复，已合并到 `json_writer.py`，`builder.py` 通过 import 调用 |
| 在 `KlineChart.tsx` 的 `useEffect` 中用空依赖 `[]` | 图表初始化依赖 `klineData`，否则第一次渲染时 container 未挂载 |

### 8.6 修改前端后必做

```bash
cd workspace/report/web && npm run build    # 确保无 TS 错误 + 打包成功
cd ../../.. && uv run python main.py report --build  # 全链路验证
```

打开 `project_data/reports/index.html` 验证功能正常。