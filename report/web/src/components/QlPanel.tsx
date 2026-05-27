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

const panelOuter: CSSProperties = {
  borderRadius: 10,
  border: "1px solid #e2e8f0",
  overflow: "hidden",
  background: "#fff",
};

const headerBar: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "8px 16px",
  background: "linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%)",
  borderBottom: "1px solid #e2e8f0",
  userSelect: "none",
};

const headerBarCompact: CSSProperties = {
  ...headerBar,
  padding: "5px 12px",
};

const headerName: CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: "#334155",
  letterSpacing: "0.3px",
};

const headerId: CSSProperties = {
  fontSize: 10,
  fontFamily: "SF Mono, Monaco, Consolas, monospace",
  color: "#94a3b8",
  letterSpacing: "0.5px",
};

const contentArea: CSSProperties = {
  padding: 16,
};

const contentAreaCompact: CSSProperties = {
  padding: 12,
};

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
      className="ql-section"
      data-ql-id={qlId}
      style={{
        ...panelOuter,
        ...(background ? { background } : {}),
        ...style,
      }}
    >
      <div style={compact ? headerBarCompact : headerBar}>
        <span style={headerName}>{name}</span>
        <span style={headerId}>{qlId}</span>
      </div>
      <div style={compact ? contentAreaCompact : contentArea}>
        {children}
      </div>
    </div>
  );
}