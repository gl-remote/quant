import type { EquityData, EChartsOption } from "@/types";
import EChartsChart from "@/components/charts/EChartsChart";
import QlPanel from "@/components/layout/QlPanel";
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
        className="mb-7"
      >
        <div className="h-[400px] flex items-center justify-center text-slate-400">
          暂无资金曲线数据
        </div>
      </QlPanel>
    );
  }

  const startEq = data.equity[0];
  const totalReturn = startEq
    ? ((data.equity[data.equity.length - 1] / startEq - 1) * 100).toFixed(2)
    : "0";
  const maxDD =
    data.max_ddpercent !== undefined && data.max_ddpercent !== null
      ? Math.abs(data.max_ddpercent).toFixed(2)
      : data.drawdown.length
        ? (Math.abs(Math.min(...data.drawdown)) * 100).toFixed(2)
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

  const retClass = Number(totalReturn) >= 0 ? "text-green-600" : "text-red-600";

  return (
    <QlPanel
      qlId="RUN-EQ-CONTAINER"
      name={qlIdNameMap["RUN-EQ-CONTAINER"]}
      className="mb-7"
    >
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div data-ql-id="RUN-EQ-MET-TOTALRET" className="bg-slate-50 rounded border border-slate-200 py-2.5 px-3.5 text-center">
          <div className="text-xs text-slate-400 mb-1">累计收益</div>
          <div className={`text-[20px] font-bold ${retClass}`}>{totalReturn}%</div>
        </div>
        <div data-ql-id="RUN-EQ-MET-MAXDD" className="bg-slate-50 rounded border border-slate-200 py-2.5 px-3.5 text-center">
          <div className="text-xs text-slate-400 mb-1">最大回撤</div>
          <div className="text-[20px] font-bold text-red-600">{maxDD}%</div>
        </div>
        <div data-ql-id="RUN-EQ-MET-ENDEQ" className="bg-slate-50 rounded border border-slate-200 py-2.5 px-3.5 text-center">
          <div className="text-xs text-slate-400 mb-1">最终权益</div>
          <div className="text-[20px] font-bold text-slate-700">{endEq}</div>
        </div>
      </div>
      <EChartsChart
        qlId="RUN-EQ-CHART"
        option={option}
        className="w-full h-[400px]"
      />
    </QlPanel>
  );
}
