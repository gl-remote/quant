import type { ViewMode, IndicatorState } from "@/config/chartConfig";
import { Segmented } from "antd";

interface Props {
  symbol: string;
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  indicators: IndicatorState;
  onIndicatorsChange: (indicators: IndicatorState) => void;
  rawDownsampled?: boolean;
}

const VIEW_OPTIONS = [
  { value: "daily" as ViewMode, label: "日线" },
  { value: "1h" as ViewMode, label: "1h" },
  { value: "15m" as ViewMode, label: "15m" },
  { value: "5m" as ViewMode, label: "5m" },
  { value: "1m" as ViewMode, label: "1分钟" },
];

interface IndicatorButton {
  key: keyof IndicatorState;
  label: string;
  activeColor: string;
  activeBg: string;
}

const INDICATOR_BUTTONS: IndicatorButton[] = [
  { key: "sma", label: "SMA 均线", activeColor: "border-green-300 text-green-700", activeBg: "bg-green-50" },
  { key: "macd", label: "MACD", activeColor: "border-purple-300 text-purple-700", activeBg: "bg-purple-50" },
  { key: "kdj", label: "KDJ", activeColor: "border-orange-300 text-orange-700", activeBg: "bg-orange-50" },
  { key: "trades", label: "交易标记", activeColor: "border-blue-300 text-blue-700", activeBg: "bg-blue-50" },
];

/**
 * KlineToolbar —— K线图顶部工具栏（周期切换 + 指标开关）。
 */
export default function KlineToolbar({
  symbol,
  mode,
  onModeChange,
  indicators,
  onIndicatorsChange,
  rawDownsampled,
}: Props) {
  return (
    <div className="flex justify-between items-center mb-4 pb-3 border-b border-border-light">
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold text-text font-mono">{symbol}</span>
        {mode === "1m" && rawDownsampled && (
          <span className="text-[11px] px-2 py-0.5 bg-warning-bg text-warning rounded">抽样显示</span>
        )}
      </div>

      <Segmented
        value={mode}
        onChange={(val) => onModeChange(val as ViewMode)}
        options={VIEW_OPTIONS}
        className="bg-surface-alt rounded-lg"
      />

      <div className="flex gap-2">
        {INDICATOR_BUTTONS.map(({ key, label, activeColor, activeBg }) => {
          const active = indicators[key];
          return (
            <button
              key={key}
              onClick={() => onIndicatorsChange({ ...indicators, [key]: !active })}
              className={
                "px-3.5 py-1 text-xs cursor-pointer rounded-md transition-all border " +
                (active ? `${activeBg} ${activeColor}` : "bg-surface border-border text-text-muted")
              }
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}