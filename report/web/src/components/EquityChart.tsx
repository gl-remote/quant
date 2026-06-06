import type { EquityData, EChartsOption } from "@/types";
import EChartsChart from "@/components/EChartsChart";
import QlPanel from "@/components/QlPanel";
import { qlIdNameMap } from "@/data/qlIdMapping";

interface EquityChartProps {
  data: EquityData | null;
}

export default function EquityChart({ data }: EquityChartProps) {
  if (!data || !data.dates?.length) {
    return (
      <QlPanel
        qlId="RUN-EQ-EMPTY"
        name={qlIdNameMap["RUN-EQ-EMPTY"]}
        style={{ marginBottom: 28 }}
      >
        <div
          style={{
            height: 400,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#94a3b8",
          }}
        >
          暂无资金曲线数据
        </div>
      </QlPanel>
    );
  }

  const startEq = data.equity[0];
  const totalReturn = startEq
    ? ((data.equity[data.equity.length - 1] / startEq - 1) * 100).toFixed(2)
    : "0";
  const maxDD = data.drawdown.length
    ? (Math.min(...data.drawdown) * 100).toFixed(2)
    : "0";
  const endEq = data.equity[data.equity.length - 1]?.toFixed(2) || "0";

  const option: EChartsOption = {
    tooltip: { trigger: "axis" },
    legend: {
      data: ["权益曲线"],
      top: 0,
      textStyle: { fontSize: 12 },
    },
    grid: { left: 60, right: 20, top: 40, bottom: 100 },
    xAxis: {
      type: "category" as const,
      data: data.dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: "value" as const,
      name: "权益",
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 10, formatter: (v: number) => (v / 10000).toFixed(0) + "w" },
    },
    dataZoom: [
      { type: "slider" as const, xAxisIndex: 0, bottom: 10, height: 20 },
      { type: "inside" as const, xAxisIndex: 0 },
    ],
    series: [
      {
        name: "权益曲线",
        type: "line",
        data: data.equity,
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#5470c6", width: 2 },
        areaStyle: {
          color: {
            type: "linear" as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(84,112,198,0.15)" },
              { offset: 1, color: "rgba(84,112,198,0.02)" },
            ],
          },
        },
      },
    ],
  };

  return (
    <QlPanel
      qlId="RUN-EQ-CONTAINER"
      name={qlIdNameMap["RUN-EQ-CONTAINER"]}
      style={{ marginBottom: 28 }}
    >
      <div
        data-ql-id="RUN-EQ-METRICS"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div data-ql-id="RUN-EQ-MET-TOTALRET" style={metricStyle}>
          <div style={metricLabelStyle}>累计收益</div>
          <div style={{ ...metricValueStyle, color: Number(totalReturn) >= 0 ? "#059669" : "#dc2626" }}>
            {totalReturn}%
          </div>
        </div>
        <div data-ql-id="RUN-EQ-MET-MAXDD" style={metricStyle}>
          <div style={metricLabelStyle}>最大回撤</div>
          <div style={{ ...metricValueStyle, color: "#dc2626" }}>{maxDD}%</div>
        </div>
        <div data-ql-id="RUN-EQ-MET-ENDEQ" style={metricStyle}>
          <div style={metricLabelStyle}>最终权益</div>
          <div style={{ ...metricValueStyle, color: "#334155" }}>{endEq}</div>
        </div>
      </div>
      <EChartsChart
        qlId="RUN-EQ-CHART"
        option={option}
        style={{ height: 400 }}
      />
    </QlPanel>
  );
}

const metricStyle: React.CSSProperties = {
  background: "#f8fafc",
  borderRadius: 6,
  padding: "10px 14px",
  textAlign: "center",
  border: "1px solid #e2e8f0",
};

const metricLabelStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#94a3b8",
  marginBottom: 4,
};

const metricValueStyle: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 700,
};