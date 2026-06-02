import { useState, useMemo } from "react";
import type { RunLogs } from "@/types";
import QlPanel from "@/components/QlPanel";

const LEVEL_COLORS: Record<string, string> = {
  ERROR: "#dc2626",
  WARNING: "#ca8a04",
  INFO: "#2563eb",
  DEBUG: "#6b7280",
};

const ALL_LEVELS = ["ERROR", "WARNING", "INFO", "DEBUG"] as const;

interface Props {
  logs: RunLogs | null;
}

export default function LogViewer({ logs }: Props) {
  const [filter, setFilter] = useState<string>("");
  const [filterLevel, setFilterLevel] = useState<string>("ALL");

  const filtered = useMemo(() => {
    if (!logs) return [];
    return logs.filter((line) => {
      if (filterLevel !== "ALL") {
        const levelMatch = line.match(/\|\s*(ERROR|WARNING|INFO|DEBUG)\s*\|/);
        if (!levelMatch || levelMatch[1] !== filterLevel) return false;
      }
      if (filter && !line.toLowerCase().includes(filter.toLowerCase())) return false;
      return true;
    });
  }, [logs, filter, filterLevel]);

  if (!logs || logs.length === 0) {
    return (
      <QlPanel qlId="RUN-LOGS" name="运行日志">
        <div className="text-slate-400 text-sm py-8 text-center">该 run 无日志数据</div>
      </QlPanel>
    );
  }

  return (
    <QlPanel qlId="RUN-LOGS" name={`运行日志 (${filtered.length} / ${logs.length} 条)`}>
      {/* 工具栏：搜索 + 级别过滤 */}
      <div className="flex items-center gap-3 mb-3">
        <input
          type="text"
          placeholder="搜索关键词…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="flex-1 text-[13px] px-3 py-1.5 border border-slate-300 rounded-md focus:outline-none focus:border-blue-400"
        />
        <div className="flex gap-1">
          <LevelBtn level="ALL" current={filterLevel} onClick={setFilterLevel} count={logs.length} />
          {ALL_LEVELS.map((lv) => (
            <LevelBtn
              key={lv}
              level={lv}
              current={filterLevel}
              onClick={setFilterLevel}
              count={logs.filter((l) => l.includes(`| ${lv}`)).length}
            />
          ))}
        </div>
      </div>

      {/* 日志列表 */}
      <div className="bg-slate-900 text-[12px] leading-relaxed font-mono rounded-lg p-3 max-h-[600px] overflow-auto">
        {filtered.length === 0 ? (
          <div className="text-slate-500 py-4 text-center">无匹配日志</div>
        ) : (
          filtered.map((line, i) => (
            <div
              key={i}
              className="hover:bg-white/5 px-1 rounded"
              style={{ color: getLevelColor(line) }}
            >
              {line}
            </div>
          ))
        )}
      </div>
    </QlPanel>
  );
}

function LevelBtn({
  level,
  current,
  onClick,
  count,
}: {
  level: string;
  current: string;
  onClick: (l: string) => void;
  count: number;
}) {
  const active = level === current;
  const color = LEVEL_COLORS[level] || "#6b7280";
  return (
    <button
      onClick={() => onClick(level)}
      className="text-[11px] px-2 py-0.5 rounded border transition-colors whitespace-nowrap"
      style={{
        borderColor: active ? color : "#e2e8f0",
        backgroundColor: active ? `${color}15` : "transparent",
        color: active ? color : "#94a3b8",
        fontWeight: active ? 600 : 400,
      }}
    >
      {level} {count > 0 && `(${count})`}
    </button>
  );
}

function getLevelColor(line: string): string {
  for (const [level, color] of Object.entries(LEVEL_COLORS)) {
    if (line.includes(`| ${level} `)) return color;
  }
  return "#94a3b8";
}
