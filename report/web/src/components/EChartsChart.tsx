import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import {
  BarChart,
  LineChart,
  ScatterChart,
  ParallelChart,
} from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  VisualMapComponent,
  ParallelComponent,
} from "echarts/components";
import type { EChartsOption } from "@/types";

echarts.use([
  CanvasRenderer,
  BarChart,
  LineChart,
  ScatterChart,
  ParallelChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  VisualMapComponent,
  ParallelComponent,
]);

interface EChartsChartProps {
  option: EChartsOption | null;
  style?: React.CSSProperties;
  qlId?: string;
}

export default function EChartsChart({
  option,
  style,
  qlId,
}: EChartsChartProps): JSX.Element | null {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current || !option) return;

    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current);
    }

    chartRef.current.setOption(option, true);

    const handleResize = () => {
      chartRef.current?.resize();
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [option]);

  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  if (!option) return null;

  return (
    <div
      ref={containerRef}
      data-ql-id={qlId}
      style={{
        width: "100%",
        height: style?.height || 400,
        ...style,
      }}
    />
  );
}