import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { SummaryItem } from "@/types";
import QlPanel from "@/components/layout/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";

interface Props {
  data: SummaryItem[] | null;
  onSelect: (symbol: string) => void;
  selectedSymbol: string;
}

function formatPct(v: number, digits = 2): string {
  return `${v.toFixed(digits)}%`;
}

function formatNumber(v: number): string {
  return v.toLocaleString("zh-CN");
}

const columns: ColumnsType<SummaryItem> = [
  { title: "品种", dataIndex: "symbol", key: "symbol" },
  {
    title: "收益率", dataIndex: "total_return", key: "total_return",
    sorter: (a, b) => a.total_return - b.total_return,
    defaultSortOrder: "descend",
    render: (v: number) => <span className={v >= 0 ? "text-success" : "text-danger"}>{formatPct(v)}</span>,
  },
  {
    title: "胜率", dataIndex: "win_rate", key: "win_rate",
    render: (v: number) => formatPct(v, 1),
  },
  {
    title: "盈亏比", dataIndex: "win_loss_ratio", key: "win_loss_ratio",
    sorter: (a, b) => a.win_loss_ratio - b.win_loss_ratio,
    render: (v: number) => <span className={v >= 1 ? "text-success" : "text-danger"}>{v.toFixed(2)}</span>,
  },
  {
    title: "成交次数", dataIndex: "total_trades", key: "total_trades",
    sorter: (a, b) => a.total_trades - b.total_trades,
    render: (v: number) => formatNumber(v),
  },
  {
    title: "最大回撤(元)", dataIndex: "max_drawdown", key: "max_drawdown",
    render: (v: number) => <span className="text-danger">{formatNumber(v || 0)}</span>,
  },
  {
    title: "夏普比率", dataIndex: "sharpe", key: "sharpe",
    sorter: (a, b) => a.sharpe - b.sharpe,
    render: (v: number) => <span className={v >= 0 ? "text-success" : "text-danger"}>{v.toFixed(2)}</span>,
  },
  {
    title: "年化收益", dataIndex: "annual_return", key: "annual_return",
    render: (v: number) => <span className={v >= 0 ? "text-success" : "text-danger"}>{formatPct(v)}</span>,
  },
  {
    title: "最终权益", dataIndex: "end_balance", key: "end_balance",
    render: (v: number) => formatNumber(v),
  },
  {
    title: "净盈亏", dataIndex: "total_net_pnl", key: "total_net_pnl",
    render: (v: number) => <span className={(v || 0) >= 0 ? "text-success" : "text-danger"}>{formatNumber(v || 0)}</span>,
  },
  {
    title: "手续费", dataIndex: "total_commission", key: "total_commission",
    render: (v: number) => formatNumber(v || 0),
  },
  {
    title: "盈利天数", dataIndex: "profit_days", key: "profit_days",
    render: (v: number | null) => String(v ?? "-"),
  },
  {
    title: "回测ID", dataIndex: "id", key: "id",
  },
];

export default function SymbolTable({ data, onSelect, selectedSymbol }: Props) {
  if (!data || data.length === 0) {
    return (
      <QlPanel qlId="RUN-TBL-EMPTY" name={qlIdNameMap["RUN-TBL-EMPTY"]} className="mb-7">
        <div className="text-center py-10 text-text-disabled">
          <div className="text-5xl mb-3">📭</div>
          <p>暂无回测记录</p>
        </div>
      </QlPanel>
    );
  }

  const totalStats = {
    avgReturn: data.reduce((sum, item) => sum + item.total_return, 0) / data.length,
    avgSharpe: data.reduce((sum, item) => sum + item.sharpe, 0) / data.length,
    totalTrades: data.reduce((sum, item) => sum + item.total_trades, 0),
  };

  return (
    <QlPanel qlId="RUN-TBL-CONTAINER" name={qlIdNameMap["RUN-TBL-CONTAINER"]} className="mb-7">
      <div className="flex justify-between items-center mb-4" data-ql-id="RUN-TBL-HEADER">
        <div>
          <h2 className="text-base font-semibold text-text m-0">📈 品种汇总</h2>
        </div>
        <div className="flex gap-6">
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-text-disabled mb-0.5">平均收益</span>
            <span className={`text-sm font-semibold ${totalStats.avgReturn >= 0 ? "text-success" : "text-danger"}`}>
              {`${totalStats.avgReturn.toFixed(2)}%`}
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-text-disabled mb-0.5">平均夏普</span>
            <span className={`text-sm font-semibold ${totalStats.avgSharpe >= 0 ? "text-success" : "text-danger"}`}>
              {totalStats.avgSharpe.toFixed(2)}
            </span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-[11px] text-text-disabled mb-0.5">总交易次数</span>
            <span className="text-sm font-semibold text-text-secondary">{formatNumber(totalStats.totalTrades)}</span>
          </div>
        </div>
      </div>

      <Table
        dataSource={data}
        columns={columns}
        rowKey="id"
        pagination={false}
        size="small"
        sticky={{ offsetHeader: 0 }}
        scroll={{ y: "50vh" }}
        showSorterTooltip={false}
        rowClassName={(record) => 
          `cursor-pointer ${record.symbol === selectedSymbol ? "bg-primary/5" : ""}`
        }
        onRow={(record) => ({
          onClick: () => onSelect(record.symbol),
        })}
      />
    </QlPanel>
  );
}