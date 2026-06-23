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
    "ql-section rounded-lg border border-border overflow-hidden bg-surface";

  return (
    <div
      className={[baseClass, className].filter(Boolean).join(" ")}
      data-ql-id={qlId}
      style={{ ...(background ? { background } : {}), ...style }}
    >
      <div
        className={`flex items-center justify-between border-b border-border bg-gradient-to-b from-surface-hover to-surface-alt select-none ${
          compact ? "px-3 py-1.5" : "px-4 py-2"
        }`}
      >
        <span className="text-[13px] font-bold text-text-secondary tracking-wide">
          {name}
        </span>
        <span className="text-[10px] font-mono text-text-disabled tracking-wider">
          {qlId}
        </span>
      </div>
      <div className={compact ? "p-3" : "p-4"}>{children}</div>
    </div>
  );
}