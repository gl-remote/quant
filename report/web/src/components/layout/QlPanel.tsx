import type { ReactNode, CSSProperties } from "react";

interface QlPanelProps {
  qlId: string;
  name: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  background?: string;
  compact?: boolean;
}

export default function QlPanel({
  qlId,
  name,
  children,
  className = "",
  style,
  background,
  compact,
}: QlPanelProps) {
  const baseClass =
    "ql-section rounded-xl border border-slate-200 overflow-hidden bg-white";

  return (
    <div
      className={[baseClass, className].filter(Boolean).join(" ")}
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
