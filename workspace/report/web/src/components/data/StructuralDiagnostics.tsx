import { useMemo, useState } from "react";
import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { ClearingDiagnostics } from "@/types";
import QlPanel from "@/components/layout/QlPanel";

interface Props {
  data: ClearingDiagnostics[] | null;
}

function pct(v: number | undefined, digits = 1): string {
  return v === undefined ? "-" : `${(v * 100).toFixed(digits)}%`;
}

function num(v: number | undefined, digits = 2): string {
  return v === undefined ? "-" : v.toFixed(digits);
}

function topExitReasons(dist: Record<string, number> | undefined): string {
  if (!dist || Object.keys(dist).length === 0) return "-";
  return Object.entries(dist)
    .sort((a, b) => b[1] - a[1])
    .map(([reason, count]) => `${reason}×${count}`)
    .join(", ");
}

const columns: ColumnsType<ClearingDiagnostics> = [
  { title: "品种", dataIndex: "symbol", key: "symbol", width: 90 },
  { title: "成交数", dataIndex: "trade_count", key: "trade_count", width: 70 },
  {
    title: "成本后胜率",
    key: "cost_adjusted_win_rate",
    render: (_, r) => pct(r.cost_adjusted_win_rate),
    width: 95,
  },
  {
    title: "成本后盈亏比",
    key: "cost_adjusted_payoff_ratio",
    render: (_, r) => num(r.cost_adjusted_payoff_ratio),
    width: 105,
  },
  {
    title: "盈亏平衡胜率",
    key: "breakeven_win_rate",
    render: (_, r) => pct(r.breakeven_win_rate),
    width: 105,
  },
  {
    title: "胜率安全边际",
    key: "win_rate_margin",
    render: (_, r) => (
      <span className={(r.win_rate_margin ?? 0) >= 0 ? "text-success" : "text-danger"}>
        {pct(r.win_rate_margin)}
      </span>
    ),
    width: 105,
  },
  {
    title: "最大单笔亏损",
    key: "max_single_loss",
    render: (_, r) => <span className="text-danger">{num(r.max_single_loss, 0)}</span>,
    width: 105,
  },
  {
    title: "最大连亏",
    dataIndex: "max_consecutive_losses",
    key: "max_consecutive_losses",
    width: 75,
  },
  {
    title: "退出结构",
    key: "exit_reason_distribution",
    render: (_, r) => (
      <span className="text-text-secondary text-[12px]">{topExitReasons(r.exit_reason_distribution)}</span>
    ),
  },
];

export default function StructuralDiagnostics({ data }: Props) {
  const rows = useMemo(() => (data ?? []).filter((d) => d.trade_count > 0), [data]);
  const [aSym, setASym] = useState<string>("");
  const [bSym, setBSym] = useState<string>("");

  if (!data || rows.length === 0) {
    return (
      <QlPanel qlId="RUN-DIAG-EMPTY" name="结构诊断" className="mb-7">
        <div className="text-center py-10 text-text-disabled">
          <div className="text-5xl mb-3">🧭</div>
          <p>暂无结构诊断数据（策略尚未填充 alpha/risk/execution 诊断字段）</p>
        </div>
      </QlPanel>
    );
  }

  const a = rows.find((r) => r.symbol === aSym);
  const b = rows.find((r) => r.symbol === bSym);

  return (
    <>
      <QlPanel qlId="RUN-DIAG-CONTAINER" name="结构诊断 · 成本后指标" className="mb-7">
        <Table
          dataSource={rows}
          columns={columns}
          rowKey="backtest_id"
          pagination={false}
          size="small"
          showSorterTooltip={false}
          scroll={{ x: 900 }}
        />
      </QlPanel>

      <QlPanel qlId="RUN-DIAG-DIFF" name="退出结构 Diff" className="mb-7">
        <div className="flex items-center gap-3 mb-4 text-[13px]">
          <span className="text-text-disabled">对比</span>
          <select
            className="border border-border rounded px-2 py-1 bg-surface text-text"
            value={aSym}
            onChange={(e) => setASym(e.target.value)}
          >
            <option value="">选择 A</option>
            {rows.map((r) => (
              <option key={`a-${r.backtest_id}`} value={r.symbol}>
                {r.symbol}
              </option>
            ))}
          </select>
          <span className="text-text-disabled">vs</span>
          <select
            className="border border-border rounded px-2 py-1 bg-surface text-text"
            value={bSym}
            onChange={(e) => setBSym(e.target.value)}
          >
            <option value="">选择 B</option>
            {rows.map((r) => (
              <option key={`b-${r.backtest_id}`} value={r.symbol}>
                {r.symbol}
              </option>
            ))}
          </select>
        </div>

        {a && b ? (
          <DiffTable a={a} b={b} />
        ) : (
          <div className="text-text-disabled text-[13px] py-4 text-center">
            选择两个品种以对比退出结构的成本后表现
          </div>
        )}
      </QlPanel>
    </>
  );
}

function DiffRow({
  label,
  a,
  b,
  isPct,
  goodWhenUp = true,
}: {
  label: string;
  a: number | undefined;
  b: number | undefined;
  isPct?: boolean;
  goodWhenUp?: boolean;
}) {
  const av = a ?? 0;
  const bv = b ?? 0;
  const delta = bv - av;
  const fmt = (v: number) => (isPct ? `${(v * 100).toFixed(1)}%` : v.toFixed(2));
  const positive = goodWhenUp ? delta >= 0 : delta <= 0;
  return (
    <tr className="border-b border-border">
      <td className="py-1.5 text-text-secondary">{label}</td>
      <td className="py-1.5 text-right font-mono">{fmt(av)}</td>
      <td className="py-1.5 text-right font-mono">{fmt(bv)}</td>
      <td className={`py-1.5 text-right font-mono ${positive ? "text-success" : "text-danger"}`}>
        {delta >= 0 ? "+" : ""}
        {fmt(delta)}
      </td>
    </tr>
  );
}

function DiffTable({ a, b }: { a: ClearingDiagnostics; b: ClearingDiagnostics }) {
  return (
    <table className="w-full text-[13px]">
      <thead>
        <tr className="border-b border-border text-text-disabled text-[12px]">
          <th className="py-1.5 text-left font-medium">指标</th>
          <th className="py-1.5 text-right font-medium">{a.symbol}</th>
          <th className="py-1.5 text-right font-medium">{b.symbol}</th>
          <th className="py-1.5 text-right font-medium">变化</th>
        </tr>
      </thead>
      <tbody>
        <DiffRow label="成交数" a={a.trade_count} b={b.trade_count} />
        <DiffRow label="成本后胜率" a={a.cost_adjusted_win_rate} b={b.cost_adjusted_win_rate} isPct />
        <DiffRow label="成本后盈亏比" a={a.cost_adjusted_payoff_ratio} b={b.cost_adjusted_payoff_ratio} />
        <DiffRow label="盈亏平衡胜率" a={a.breakeven_win_rate} b={b.breakeven_win_rate} isPct goodWhenUp={false} />
        <DiffRow label="胜率安全边际" a={a.win_rate_margin} b={b.win_rate_margin} isPct />
        <DiffRow label="最大单笔亏损" a={a.max_single_loss} b={b.max_single_loss} goodWhenUp />
        <DiffRow label="净盈亏" a={a.total_net_pnl} b={b.total_net_pnl} />
      </tbody>
    </table>
  );
}
