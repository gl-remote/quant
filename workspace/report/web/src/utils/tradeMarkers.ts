import type { Time } from "lightweight-charts";
import type { KlinePoint, TradeRecord } from "@/types";
import { parseTradeTimestamp } from "@/utils/chartTime";

type ViewMode = "daily" | "1m" | "5m" | "15m" | "1h";

/**
 * 将交易记录转换为 lightweight-charts 的标记数据。
 * 根据当前查看模式选择不同的标记策略：
 * - daily: 不展示买卖点（K 线周期太大，无法对齐）
 * - 1m: 详细标记（多开/空开/空平/多平，带箭头和文字）
 * - 5m/15m/1h: 聚合标记（按 K 线聚合，买入/卖出/双向）
 */
export function convertTradeToMarkers(
  trades: TradeRecord[],
  klineData: KlinePoint[],
  currentMode: ViewMode,
): any[] {
  if (!trades || trades.length === 0 || !klineData || klineData.length === 0) {
    return [];
  }

  // 日线不展示买卖点
  if (currentMode === "daily") return [];

  // 将交易时间归一化到所属 K 线时间戳的查找函数
  const findKlineTime = _createKlineTimeFinder(klineData);

  if (currentMode === "1m") {
    return _createDetailedMarkers(trades, findKlineTime);
  }

  return _createAggregatedMarkers(trades, findKlineTime);
}

// ─────────────────────────────────────────────────────────────────────
// 内部辅助函数
// ─────────────────────────────────────────────────────────────────────

/**
 * 创建一个函数，将交易时间戳映射到所属 K 线的时间戳。
 * 使用二分查找，时间复杂度 O(log n)。
 */
function _createKlineTimeFinder(
  klineData: KlinePoint[],
): (tradeTimestamp: number) => number | null {
  const sortedKlines = [...klineData].sort(
    (a, b) => Number(a.datetime) - Number(b.datetime),
  );
  const klineTimes = sortedKlines.map((k) => Number(k.datetime));

  return (tradeTimestamp: number): number | null => {
    let lo = 0;
    let hi = klineTimes.length - 1;
    let result = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (klineTimes[mid] <= tradeTimestamp) {
        result = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    if (result === -1) return null;
    return klineTimes[result];
  };
}

/**
 * 1m 模式：每条交易一个标记，区分开仓/平仓和方向。
 */
function _createDetailedMarkers(
  trades: TradeRecord[],
  findKlineTime: (ts: number) => number | null,
): any[] {
  const markers: any[] = [];
  for (const trade of trades) {
    const tradeTs = parseTradeTimestamp(trade.datetime);
    const klineTime = findKlineTime(tradeTs);
    if (klineTime === null) continue;

    const isOpen = trade.offset === "open";
    const isLong = trade.direction === "long";

    let position: "aboveBar" | "belowBar";
    let color: string;
    let shape: "arrowUp" | "arrowDown";
    let text: string;

    if (isOpen) {
      if (isLong) {
        position = "belowBar";
        color = "#26A69A";
        shape = "arrowUp";
        text = "多开";
      } else {
        position = "aboveBar";
        color = "#EF5350";
        shape = "arrowDown";
        text = "空开";
      }
    } else {
      if (isLong) {
        position = "belowBar";
        color = "#26A69A";
        shape = "arrowUp";
        text = "空平";
      } else {
        position = "aboveBar";
        color = "#EF5350";
        shape = "arrowDown";
        text = "多平";
      }
    }

    markers.push({ time: klineTime as Time, position, color, shape, text });
  }
  return markers;
}

/**
 * 5m/15m/1h 模式：按 K 线聚合交易，统计买入/卖出数量。
 */
function _createAggregatedMarkers(
  trades: TradeRecord[],
  findKlineTime: (ts: number) => number | null,
): any[] {
  const tradeByKline: Map<number, { buy: number; sell: number }> = new Map();

  for (const trade of trades) {
    const tradeTs = parseTradeTimestamp(trade.datetime);
    const klineTime = findKlineTime(tradeTs);
    if (klineTime === null) continue;

    if (!tradeByKline.has(klineTime)) {
      tradeByKline.set(klineTime, { buy: 0, sell: 0 });
    }
    const entry = tradeByKline.get(klineTime)!;
    if (trade.direction === "long") {
      entry.buy += 1;
    } else {
      entry.sell += 1;
    }
  }

  const markers: any[] = [];
  for (const [klineTime, counts] of tradeByKline.entries()) {
    const { buy, sell } = counts;

    if (buy > 0 && sell > 0) {
      markers.push({
        time: klineTime as Time,
        position: "belowBar",
        color: "#FF9800",
        shape: "arrowUp",
        text: "T",
      });
    } else if (buy > 0) {
      markers.push({
        time: klineTime as Time,
        position: "belowBar",
        color: "#26A69A",
        shape: "arrowUp",
        text: "多",
      });
    } else if (sell > 0) {
      markers.push({
        time: klineTime as Time,
        position: "aboveBar",
        color: "#EF5350",
        shape: "arrowDown",
        text: "空",
      });
    }
  }

  return markers;
}
