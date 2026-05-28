import type { ReactNode, CSSProperties } from "react";

interface QlPanelProps {
  /** data-ql-id 唯一标识 */
  qlId: string;
  /** 行业规范名称，显示在标题栏 */
  name: string;
  /** 面板内容 */
  children: ReactNode;
  /** 额外样式（叠加到面板外层） */
  style?: CSSProperties;
  /** 面板背景色，默认白色 */
  background?: string;
  /** 紧贴模式：标题栏更矮、内边距更小，适合嵌套在已有卡片内部的子面板 */
  compact?: boolean;
}

export default function QlPanel({
  qlId,
  name,
  children,
  style,
  background,
  compact,
}: QlPanelProps) {
  return (
    <div
      className="ql-section rounded-xl border border-slate-200 overflow-hidden bg-white"
      data-ql-id={qlId}
      style={{ ...(background ? { background } : {}), ...style }}
    >
      <div
        className={`flex items-center justify-between border-b border-slate-200 bg-gradient-to-b from-slate-50 to-slate-100 select-none ${
          compact ? "px-3 py-1.5" : "px-4 py-2"
        }`}
      >
        <span className="text-[13px] font-bold text-slate-700 tracking-wide">
          {name}
        </span>
        <span className="text-[10px] font-mono text-slate-400 tracking-wider">
          {qlId}
        </span>
      </div>
      <div className={compact ? "p-3" : "p-4"}>{children}</div>
    </div>
  );
}