import type { BacktestRecord } from "@/types";
import QlPanel from "@/components/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";

interface Props {
  backtests: BacktestRecord[] | null;
  selectedSymbol: string;
}

function formatPct(v: number, digits = 2): string {
  return `${(v).toFixed(digits)}%`;
}

export default function BacktestDetail({
  backtests,
  selectedSymbol,
}: Props) {
  if (!backtests || backtests.length === 0) {
    return (
      <QlPanel
        qlId="RUN-BT-EMPTY"
        name={qlIdNameMap["RUN-BT-EMPTY"]}
        style={{ marginBottom: 24 }}
      >
        <></>
      </QlPanel>
    );
  }

  const bt = backtests.find((b) => b.symbol === selectedSymbol);
  if (!bt) {
    return (
      <QlPanel
        qlId="RUN-BT-EMPTY"
        name={qlIdNameMap["RUN-BT-EMPTY"]}
        style={{ marginBottom: 24 }}
      >
        <></>
      </QlPanel>
    );
  }

  const metrics: [string, string][] = [
    ["收益率", formatPct(bt.total_return * 100)],
    ["胜率", formatPct(bt.win_rate, 1)],
    ["最大回撤", formatPct(bt.max_drawdown)],
    ["夏普比率", bt.sharpe_ratio?.toFixed(2) || "-"],
    ["交易次数", String(bt.total_trades)],
    ["初始资金", bt.initial_capital?.toLocaleString() || "-"],
    ["最终权益", bt.end_balance?.toLocaleString() || "-"],
    ["回测区间", `${bt.start_date} ~ ${bt.end_date}`],
    ["K线周期", bt.kline_interval || "-"],
    ["策略版本", bt.strategy_version || "-"],
  ];

  return (
    <QlPanel
      qlId="RUN-BT-CONTAINER"
      name={`${qlIdNameMap["RUN-BT-CONTAINER"]}  ·  ${selectedSymbol}`}
      style={{ marginBottom: 24 }}
    >
      <div data-ql-id="RUN-BT-METRICS" style={styles.grid}>
        {metrics.map(([label, value]) => (
          <div key={label} style={styles.item}>
            <span style={styles.label}>{label}</span>
            <span style={styles.value}>{value}</span>
          </div>
        ))}
      </div>

      {bt.params && bt.params.length > 0 && (
        <div data-ql-id="RUN-BT-PARAMS" style={{ marginTop: 16 }}>
          <div style={styles.subtitle}>策略参数</div>
          <div style={styles.grid}>
            {bt.params.map((p) => (
              <div key={p.name} style={styles.item}>
                <span style={styles.label}>{p.name}</span>
                <span style={styles.value}>{p.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </QlPanel>
  );
}

const styles: Record<string, React.CSSProperties> = {
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
    gap: "8px",
  },
  item: {
    display: "flex",
    justifyContent: "space-between",
    padding: "6px 10px",
    background: "#f8fafc",
    borderRadius: "4px",
  },
  label: {
    fontSize: "12px",
    color: "#94a3b8",
  },
  value: {
    fontSize: "13px",
    fontWeight: 600,
    color: "#475569",
  },
  subtitle: {
    fontSize: "14px",
    fontWeight: 600,
    marginBottom: "8px",
    color: "#475569",
  },
};