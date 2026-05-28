# K线图表重构完成

## 任务概述
将 K 线图表组件重构为内部获取数据模式，支持按需加载最多 100 条数据。

## 完成的修改

### 1. KlineChart.tsx 重构
- **Props 接口变更**：从 `data, loading` 改为 `symbol, runId`
- **内部数据获取**：通过 `useFetchJson` 内部获取 K 线数据
- **按需加载**：使用 `useMemo` 截取最多 100 条数据（`MAX_VISIBLE_POINTS = 100`）
- **时序问题修复**：通过 `initTriggerRef` 协调容器挂载和图表初始化

### 2. RunPage.tsx 简化
- 移除原有的 kline 数据获取逻辑
- 简化为传递 `symbol={selectedSymbol}` 和 `runId={runId}`

## 技术细节

### 时序协调方案
使用 `initTriggerRef` 替代 `containerReady` state：
1. 第一个 `useEffect`（空依赖）：挂载时递增 ref
2. 第二个 `useEffect`（依赖 ref）：容器挂载后初始化图表

### ESLint 警告
存在 `react-hooks/exhaustive-deps` 警告，但这是正确的用法，因为我们需要 ref 的当前值而非引用本身。

## 验证结果
- 构建成功，无错误
- 类型检查通过
- 保留所有原有功能（切换日线/分钟线、SMA 均线）