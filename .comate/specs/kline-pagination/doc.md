# K线图表按需加载重构方案

## 1. 问题背景

当前 K 线图表偶发不显示，原因是：
- `RunPage` 中 `selectedSymbol` 和 `runId` 的时序问题导致数据请求不稳定
- 大数据量一次性渲染导致性能问题

## 2. 解决思路

重构 `KlineChart` 组件，实现：
- KlineChart 接收完整数据，内部按需截取渲染
- 每次渲染最多 100 条数据
- 移除翻页按钮，保持简洁界面
- 稳定的内部状态管理

## 3. 架构设计

```
RunPage
    └── KlineChart (独立获取数据)
            ├── Props: { symbol: string, runId: number }
            ├── 内部：useFetchJson 获取数据
            ├── 按需截取：最多 100 条
            ├── 渲染：K线图表（无翻页控件）
            └── 视觉：与原设计完全一致
```

## 4. 数据流

| 层级 | 职责 | 数据类型 |
|------|------|----------|
| RunPage | 传递 symbol 和 runId | 无数据传递 |
| KlineChart | 内部调用 fetchJson 获取数据，按需截取渲染 | `KlinePoint[]` (≤100) |

## 5. KlineChart 组件重构

### 5.1 核心变更

**当前问题**：
- KlineChart 通过 props 接收 `data` 和 `loading`，依赖父组件的状态
- `selectedSymbol` 变化时，父组件的数据加载存在时序问题
- 大数据量一次性渲染导致性能问题

**解决思路**：
- KlineChart 内部直接通过 `fetchJson` 获取数据，不依赖父组件传递
- 使用 `[symbol, runId]` 作为依赖项，稳定控制数据获取时机
- 每次渲染最多 100 条数据

### 5.2 Props 变更

```typescript
interface Props {
  symbol: string;            // 品种代码（作为数据键）
  runId: number;            // 回测 ID
}
```

### 5.3 内部数据获取

```typescript
const MAX_VISIBLE_POINTS = 100;

// 内部获取数据（依赖项：[symbol, runId]）
const { data: klineData, loading } = useFetchJson<KlineData>(
  `kline_${symbol}.json`,
  runId
);

// 按需截取数据
const visibleData = useMemo(() => {
  if (!klineData) return null;
  const source = klineData.daily; // 默认使用日线
  if (source.length <= MAX_VISIBLE_POINTS) return source;
  return source.slice(-MAX_VISIBLE_POINTS); // 取末尾 100 条
}, [klineData]);
```

### 5.4 移除内容

无（当前无翻页功能）

### 5.5 保留内容

- 日线/分钟线切换按钮
- SMA 均线开关
- 图表渲染逻辑
- 加载状态和空状态展示
- 所有视觉样式

## 6. 文件变更

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `KlineChart.tsx` | 移除翻页逻辑，添加按需截取逻辑 |
| 修改 | `RunPage.tsx` | 传递 `data` 和 `mode` prop |

## 7. 优势

1. **解决时序问题**：KlineChart 内部按需截取，不依赖外部状态管理
2. **提升性能**：最多渲染 100 条，减少 DOM 节点
3. **简洁界面**：无翻页按钮，用户操作更直观
4. **代码简洁**：组件自包含，减少外部依赖