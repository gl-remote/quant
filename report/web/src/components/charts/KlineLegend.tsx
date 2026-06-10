import type { ViewMode } from "@/config/chartConfig";

interface LegendItem {
  color: string;
  label: string;
  isText?: boolean; // 如果是 ▲/▼ 文本标记而非颜色圆点
}

/**
 * KlineLegend —— K线图图例（底部图例条）。
 * 简单的展示组件，不与图表状态交互。
 */
export default function KlineLegend({ mode }: { mode: ViewMode }) {
  const items: LegendItem[] = [
    { color: "#FF6B6B", label: "SMA(5)" },
    { color: "#4ECDC4", label: "SMA(60)" },
    { color: "#26A69A", label: "阳线" },
    { color: "#EF5350", label: "阴线" },
  ];

  return (
    <div className="flex justify-center gap-6 mt-3 pt-3 border-t border-border-light">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5 text-xs text-text-muted">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
          <span>{item.label}</span>
        </div>
      ))}

      {mode === "1m" && (
        <>
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <span className="text-[#26A69A]">▲</span>
            <span>多开/空平</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <span className="text-[#EF5350]">▼</span>
            <span>空开/多平</span>
          </div>
        </>
      )}

      {mode !== "daily" && mode !== "1m" && (
        <>
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <span className="text-[#26A69A]">▲</span>
            <span>买入</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <span className="text-[#EF5350]">▼</span>
            <span>卖出</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <span className="text-[#FF9800]">▲</span>
            <span>双向(T)</span>
          </div>
        </>
      )}
    </div>
  );
}