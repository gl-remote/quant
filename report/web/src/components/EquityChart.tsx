import type { EquityData, EChartsOption } from "@/types";
import EChartsChart from "@/components/EChartsChart";

interface EquityChartProps {
  data: EquityData | null;
}

export default function EquityChart({ data }: EquityChartProps) {
  if (!data || !data.dates?.length) {
    return (
      <div
        data-ql-id="RUN-EQ-EMPTY"
        style={{
          height: 400,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#999",
          background: "#fafafa",
          borderRadius: 8,
          border: "1px solid #e8e8e8",
        }}
      >
        暂无资金曲线数据
      </div>
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
      data: ["权益曲线", "回撤"],
      top: 0,
      textStyle: { fontSize: 12 },
    },
    grid: { left: 60, right: 80, top: 40, bottom: 100 },
    xAxis: {
      type: "category" as const,
      data: data.dates,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: [
      {
        type: "value" as const,
        name: "权益",
        nameTextStyle: { fontSize: 11 },
        axisLabel: { fontSize: 10, formatter: (v: number) => (v / 10000).toFixed(0) + "w" },
      },
      {
        type: "value" as const,
        name: "回撤 (%)",
        nameTextStyle: { fontSize: 11 },
        axisLabel: { fontSize: 10, formatter: "{value}%" },
        max: 0,
        min: (v: { min: number }) => Math.min(v.min * 100 * 1.2, -5),
      },
    ],
    dataZoom: [
      { type: "slider" as const, xAxisIndex: 0, bottom: 10, height: 20 },
      { type: "inside" as const, xAxisIndex: 0 },
    ],
    series: [
      {
        name: "权益曲线",
        type: "line",
        data: data.equity,
        yAxisIndex: 0,
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#5470c6", width: 2 },
        areaStyle: {
          color: {
            type: "linear" as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(84,112,198,0.2)" },
              { offset: 1, color: "rgba(84,112,198,0.02)" },
            ],
          },
        },
      },
      {
        name: "回撤",
        type: "line",
        data: data.drawdown.map((v: number) => (v * 100).toFixed(2)),
        yAxisIndex: 1,
        symbol: "none",
        lineStyle: { color: "#e74c3c", width: 1.5 },
        areaStyle: {
          color: {
            type: "linear" as const,
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(231,76,60,0.1)" },
              { offset: 1, color: "rgba(231,76,60,0.3)" },
            ],
          },
        },
      },
    ],
  };

  return (
    <div data-ql-id="RUN-EQ-CONTAINER">
      <div
        data-ql-id="RUN-EQ-METRICS"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <div data-ql-id="RUN-EQ-MET-TOTALRET" style={metricStyle}>
          <div style={metricLabelStyle}>累计收益</div>
          <div style={{ ...metricValueStyle, color: Number(totalReturn) >= 0 ? "#27ae60" : "#e74c3c" }}>
            {totalReturn}%
          </div>
        </div>
        <div data-ql-id="RUN-EQ-MET-MAXDD" style={metricStyle}>
          <div style={metricLabelStyle}>最大回撤</div>
          <div style={{ ...metricValueStyle, color: "#e74c3c" }}>{maxDD}%</div>
        </div>
        <div data-ql-id="RUN-EQ-MET-ENDEQ" style={metricStyle}>
          <div style={metricLabelStyle}>最终权益</div>
          <div style={{ ...metricValueStyle, color: "#333" }}>{endEq}</div>
        </div>
      </div>
      <EChartsChart
        qlId="RUN-EQ-CHART"
        option={option}
        style={{ height: 400 }}
      />
    </div>
  );
}

const metricStyle: React.CSSProperties = {
  background: "#f8f9fa",
  borderRadius: 6,
  padding: "10px 14px",
  textAlign: "center",
  border: "1px solid #e8e8e8",
};

const metricLabelStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#888",
  marginBottom: 4,
};

const metricValueStyle: React.CSSProperties = {
  fontSize: 20,
  fontWeight: 700,
};