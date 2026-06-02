import { useState, useMemo } from "react";
import type { RunLogs } from "@/types";
import QlPanel from "@/components/QlPanel";

interface Props {
  logs: RunLogs | null;
}

export default function LogViewer({ logs }: Props) {
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    if (!logs) return "";
    if (!filter) return logs;
    return logs
      .split("\n")
      .filter((line) => line.toLowerCase().includes(filter.toLowerCase()))
      .join("\n");
  }, [logs, filter]);

  if (!logs) {
    return (
      <QlPanel qlId="RUN-LOGS" name="运行日志">
        <div className="text-slate-400 text-sm py-8 text-center">该 run 无日志数据</div>
      </QlPanel>
    );
  }

  const lines = (filter ? filtered : logs).split("\n");

  return (
    <QlPanel qlId="RUN-LOGS" name={`运行日志 (${lines.length} 行)`}>
      {/* 搜索 */}
      <div className="mb-3">
        <input
          type="text"
          placeholder="搜索关键词…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="text-[13px] px-3 py-1.5 border border-slate-300 rounded-md focus:outline-none focus:border-blue-400 w-full"
        />
      </div>

      {/* 日志展示 */}
      <div className="bg-slate-900 text-[12px] leading-relaxed font-mono rounded-lg p-3 max-h-[600px] overflow-auto whitespace-pre-wrap">
        {lines.map((line, i) => (
          <div
            key={i}
            className="hover:bg-white/5 px-1 rounded"
            style={{ color: getLineColor(line) }}
          >
            {line}
          </div>
        ))}
      </div>
    </QlPanel>
  );
}

function getLineColor(line: string): string {
  if (line.includes("| ERROR")) return "#f87171";
  if (line.includes("| WARNING")) return "#facc15";
  if (line.includes("| INFO")) return "#60a5fa";
  return "#94a3b8";
}
