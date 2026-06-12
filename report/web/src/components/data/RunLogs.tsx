import { useState, useMemo } from "react";
import { Input } from "antd";
import type { RunLogs } from "@/types";
import QlPanel from "@/components/layout/QlPanel";

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
        <div className="text-text-disabled text-sm py-8 text-center">该 run 无日志数据</div>
      </QlPanel>
    );
  }

  const lines = (filter ? filtered : logs).split("\n");

  return (
    <QlPanel qlId="RUN-LOGS" name={`运行日志 (${lines.length} 行)`}>
      <div className="mb-3">
        <Input.Search
          placeholder="搜索关键词…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          allowClear
        />
      </div>

      <div className="bg-console-bg text-[12px] leading-relaxed font-mono rounded-lg p-3 max-h-[600px] overflow-auto whitespace-pre-wrap">
        {lines.map((line, i) => (
          <div
            key={i}
            className="hover:bg-text-inverse/5 px-1 rounded"
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