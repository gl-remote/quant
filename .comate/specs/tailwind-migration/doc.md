# Tailwind CSS 迁移

## 背景

当前所有样式使用 React inline `style={}` 对象，缺乏标准化的 CSS 工具。CSS Grid 布局中反复遇到 `min-height: auto`、滚动容器裁剪等坑，每次手调样式无系统化调试路径。

## 方案

迁移至 **Tailwind CSS v4**（零配置版本），用 utility class 替代 inline styles。

## 优势

- `min-h-0` → 解决 Grid 收缩问题
- `h-[calc(100vh-84px)]` → 固定高度容器
- `overflow-y-auto` → 标准滚动
- `scrollbar-thin` → 细滚动条（需 tailwind-scrollbar 插件）
- 构建时 tree-shaking，只保留用到的 class，增量 < 4KB
- 无需 tailwind.config.js（v4 的 `@import "tailwindcss"` 自动识别项目）

## 迁移范围

全部 8 个有自定义样式的组件一次性迁移：

| 组件 | 行数 | 样式复杂度 | 风险 |
|------|------|-----------|------|
| QlPanel.tsx | 89 | 低（纯展示包装器） | 低 |
| BacktestDetail.tsx | 113 | 低（grid + 文本样式） | 低 |
| SymbolTable.tsx | 252 | 中（table + 排序交互） | 低 |
| MetricCards.tsx | ~150 | 低（grid 卡片） | 低 |
| Layout.tsx | ~100 | 低（header + main + footer） | 低 |
| NavPage.tsx | ~100 | 低（表格 + 按钮） | 低 |
| KlineChart.tsx | 460 | 高（图表容器 + 工具栏） | 中 |
| RunPage.tsx | 380 | 高（Grid 布局 + Tab + 复合面板） | 中 |

QlPanel 是其他组件的基础包装器，迁移它首当其冲但风险最低——它只是 header + content 两个区域，样式简单直接。

迁移就是改 `style={styles.xxx}` 为 `className="..."`，然后删除 styles 对象。组件逻辑完全不变。

## 技术细节

### 安装

```bash
npm install tailwindcss @tailwindcss/vite
```

### 配置

1. `vite.config.ts`: 添加 `@tailwindcss/vite` 插件
2. 新建 `src/index.css`: `@import "tailwindcss";`
3. `main.tsx`: `import "./index.css";`

### 迁移模式

```tsx
// 旧: inline style
<div style={styles.rightPanel}>...</div>
const styles = { rightPanel: { display: "flex", ... } }

// 新: Tailwind class
<div className="flex flex-col gap-7 h-[calc(100vh-84px)] overflow-y-auto min-h-0 scrollbar-thin">...</div>
```

## 涉及文件

| 文件 | 修改 |
|------|------|
| `package.json` | 添加 tailwindcss, @tailwindcss/vite |
| `vite.config.ts` | 添加 Tailwind 插件 |
| `src/index.css` | 新建，导入 Tailwind |
| `src/main.tsx` | import index.css |
| `RunPage.tsx` | 右边栏布局迁移 |
| `SymbolTable.tsx` | 表格布局迁移 |
| `BacktestDetail.tsx` | 指标卡片迁移 |

## 验证

- `npm run build` 成功，无新增 TS/CSS 错误
- `output/index.html` 打开，布局与迁移前一致
- 右边栏滚动正常工作