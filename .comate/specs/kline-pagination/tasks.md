# K线图表按需加载重构任务清单

## 任务概览
- 重构 KlineChart 组件，内部直接获取数据
- 修改 RunPage 传递 symbol 和 runId props
- 验证图表正常显示

---

- [x] Task 1: 重构 KlineChart 组件
    - 1.1: 修改 Props 接口，接收 `symbol: string` 和 `runId: number`
    - 1.2: 删除 `data` 和 `loading` props
    - 1.3: 内部添加 `useFetchJson` 获取 K 线数据
    - 1.4: 添加 `useMemo` 按需截取最多 100 条数据
    - 1.5: 保留日线/分钟线切换功能
    - 1.6: 保留 SMA 均线功能
    - 1.7: 保留所有视觉样式不变

- [x] Task 2: 修改 RunPage 组件
    - 2.1: 修改 KlineChart 调用方式，传递 `symbol={selectedSymbol}` 和 `runId={runId}`
    - 2.2: 移除原有的 kline 数据获取逻辑（useFetchJson 那一行）

- [x] Task 3: 验证功能
    - 3.1: 检查语法正确性
    - 3.2: 确认类型定义正确
