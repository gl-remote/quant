import type { Time, ChartOptions, DeepPartial } from "lightweight-charts";
import { TickMarkType } from "lightweight-charts";

// ─────────────────────────────────────────────────────────────────────
// 共享类型定义（IndicatorState 和 ViewMode 在此统一定义）
// ─────────────────────────────────────────────────────────────────────

export type ViewMode = "daily" | "1m" | "5m" | "15m" | "1h";

export interface IndicatorState {
  sma: boolean;
  trades: boolean;
  macd: boolean;
  kdj: boolean;
}

// ─────────────────────────────────────────────────────────────────────
// 颜色常量
// ─────────────────────────────────────────────────────────────────────

export const CHART_COLORS = {
  bg: "#ffffff",
  text: "#333",
  gridLine: "#f0f0f0",
  paneBorder: "#e0e0e0",
  upCandle: "#26A69A",
  downCandle: "#EF5350",
  smaShort: "#FF6B6B",
  smaLong: "#4ECDC4",
  tradeBuy: "#26A69A",
  tradeSell: "#EF5350",
  tradeBoth: "#FF9800",
} as const;

// ─────────────────────────────────────────────────────────────────────
// 指标参数
// ─────────────────────────────────────────────────────────────────────

export const INDICATOR_PARAMS = {
  smaShort: 5,
  smaLong: 60,
  macdFast: 12,
  macdSlow: 26,
  macdSignal: 9,
  kdjPeriod: 9,
  kdjSmooth: 3,
} as const;

// ─────────────────────────────────────────────────────────────────────
// 时间格式化
// ─────────────────────────────────────────────────────────────────────

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/**
 * tickMarkFormatter: 决定时间轴上每个刻度显示什么文字。
 * 根据刻度类型（年/月/日/时/分）返回不同精度的字符串。
 */
export function tickMarkFormatter(
  time: Time,
  tickMarkType: TickMarkType,
  _locale: string,
): string {
  if (typeof time !== "number") return String(time);
  const d = new Date(time * 1000);
  switch (tickMarkType) {
    case TickMarkType.Year:
      return String(d.getFullYear());
    case TickMarkType.Month:
      return `${d.getFullYear()}/${pad(d.getMonth() + 1)}`;
    case TickMarkType.DayOfMonth:
      return `${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
    case TickMarkType.Time:
      return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
    case TickMarkType.TimeWithSeconds:
      return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }
  return String(time);
}

/**
 * timeFormatter: 鼠标悬浮/十字线上显示的完整时间。
 */
export function timeFormatter(time: Time): string {
  if (typeof time !== "number") return String(time);
  const d = new Date(time * 1000);
  return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

// ─────────────────────────────────────────────────────────────────────
// 图表基础配置
// ─────────────────────────────────────────────────────────────────────

export const CHART_HEIGHT = 600;

/**
 * 创建图表基础配置。所有与渲染无关的逻辑都收敛在此处，
 * 组件内只负责把数据喂给 series，不关心颜色/字体/间距等细节。
 */
export function buildChartOptions(
  width: number,
): DeepPartial<ChartOptions> {
  return {
    layout: {
      background: { color: CHART_COLORS.bg },
      textColor: CHART_COLORS.text,
      panes: { separatorColor: CHART_COLORS.paneBorder },
    },
    grid: {
      vertLines: { color: CHART_COLORS.gridLine },
      horzLines: { color: CHART_COLORS.gridLine },
    },
    width,
    height: CHART_HEIGHT,
    crosshair: {
      mode: 1, // CrosshairMode.Magnet
      vertLine: { width: 1, color: "rgba(180, 180, 180, 0.5)", style: 3, visible: true },
      horzLine: { width: 1, color: "rgba(180, 180, 180, 0.5)", style: 3, visible: true },
    },
    rightPriceScale: { borderColor: CHART_COLORS.paneBorder },
    timeScale: {
      borderColor: CHART_COLORS.paneBorder,
      timeVisible: true,
      secondsVisible: false,
      tickMarkFormatter,
    },
    localization: {
      locale: "zh-CN",
      timeFormatter,
    },
  };
}
