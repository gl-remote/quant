import type { ViewMode, IndicatorState } from "@/config/chartConfig";

interface Props {
  symbol: string;
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  indicators: IndicatorState;
  onIndicatorsChange: (indicators: IndicatorState) => void;
  rawDownsampled?: boolean;
}

const VIEW_MODES: { value: ViewMode; label: string }[] = [
  { value: "daily", label: "日线" },
  { value: "1h", label: "1h" },
  { value: "15m", label: "15m" },
  { value: "5m", label: "5m" },
  { value: "1m", label: "1分钟" },
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
 * 纯展示组件，不持有任何状态，状态由父组件管理。
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
    <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
      <div className="flex items-center gap-2">
        <span className="text-lg font-bold text-slate-900 font-mono">{symbol}</span>
        {mode === "1m" && rawDownsampled && (
          <span className="text-[11px] px-2 py-0.5 bg-amber-50 text-amber-800 rounded">抽样显示</span>
        )}
      </div>

      <div className="flex items-center">
        <div className="flex bg-slate-100 rounded-lg p-0.5">
          {VIEW_MODES.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => onModeChange(value)}
              className={
                "px-4 py-1.5 text-[13px] font-medium rounded-md transition-all border-none cursor-pointer " +
                (mode === value ? "bg-white text-slate-900 shadow-md" : "text-slate-500 bg-transparent")
              }
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2">
        {INDICATOR_BUTTONS.map(({ key, label, activeColor, activeBg }) => {
          const active = indicators[key];
          return (
            <button
              key={key}
              onClick={() => onIndicatorsChange({ ...indicators, [key]: !active })}
              className={
                "px-3.5 py-1.5 text-xs cursor-pointer rounded-md transition-all border " +
                (active ? `${activeBg} ${activeColor}` : "bg-white border-slate-200 text-slate-500")
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
