/**
 * @file EChartsChart.tsx
 * @description ECharts图表包装组件
 * 封装了ECharts的初始化、配置更新、窗口大小调整和清理逻辑
 * 支持自定义样式和qlId属性
 */

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

// 注册ECharts组件
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

/**
 * EChartsChart组件属性接口
 * @interface EChartsChartProps
 * @property {EChartsOption | null} option - ECharts配置对象
 * @property {React.CSSProperties} [style] - 自定义样式
 * @property {string} [qlId] - 数据测试ID
 */
interface EChartsChartProps {
  option: EChartsOption | null;
  style?: React.CSSProperties;
  qlId?: string;
}

/**
 * EChartsChart组件
 * ECharts图表包装组件
 * 
 * @component
 * @param {EChartsChartProps} props - 组件属性
 * @returns {JSX.Element | null} 渲染后的图表组件
 */
export default function EChartsChart({
  option,
  style,
  qlId,
}: EChartsChartProps): JSX.Element | null {
  // 容器引用
  const containerRef = useRef<HTMLDivElement>(null);
  // 图表实例引用
  const chartRef = useRef<echarts.ECharts | null>(null);

  /**
   * 初始化和更新图表
   */
  useEffect(() => {
    if (!containerRef.current || !option) return;

    // 初始化图表实例
    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current);
    }

    // 设置图表配置
    chartRef.current.setOption(option, true);

    // 处理窗口大小变化
    const handleResize = () => {
      chartRef.current?.resize();
    };
    window.addEventListener("resize", handleResize);

    // 清理函数
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [option]);

  /**
   * 组件卸载时清理图表实例
   */
  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  // 无配置时返回null
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
