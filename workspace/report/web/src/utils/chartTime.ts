import type { Time } from "lightweight-charts";

/**
 * 将各种格式的时间戳转换为 lightweight-charts 需要的时间格式。
 *
 * 统一规则：所有时间字符串都按 UTC 处理，避免时区差异导致的对齐问题。
 *
 * @param dt - 可能是 number（秒级时间戳）或 string（"YYYY-MM-DD HH:MM:SS" / "YYYY-MM-DDTHH:MM:SS" / "YYYY-MM-DD"）
 * @returns lightweight-charts 的 Time 类型（number 或 string）
 */
export function toChartTime(dt: string | number): Time {
  if (typeof dt === "number") {
    return dt as Time;
  }

  // 纯数字字符串（如 "1718000000"）→ 直接当作时间戳
  if (!isNaN(Number(dt))) {
    return Number(dt) as Time;
  }

  // "YYYY-MM-DD HH:MM:SS" → 替换空格为 T 并加 Z 当作 UTC
  if (dt.includes(" ")) {
    return (new Date(dt.replace(" ", "T") + "Z").getTime() / 1000) as Time;
  }

  // "YYYY-MM-DDTHH:MM:SS"（ISO 格式但不带时区）→ 加 Z 当作 UTC
  if (dt.includes("T")) {
    return (new Date(dt + "Z").getTime() / 1000) as Time;
  }

  // "YYYY-MM-DD"（日线数据）→ 直接返回字符串，lightweight-charts 原生支持
  return dt as Time;
}

/**
 * 解析交易记录的时间戳，返回秒级 Unix 时间戳。
 * 统一使用 UTC 解析，确保与 K 线时间轴对齐。
 *
 * @param datetime - 交易时间（number 秒级时间戳 或 字符串）
 * @returns 秒级 Unix 时间戳（number）
 */
export function parseTradeTimestamp(datetime: string | number): number {
  if (typeof datetime === "number") {
    return datetime;
  }

  if (datetime.includes(" ")) {
    return new Date(datetime.replace(" ", "T") + "Z").getTime() / 1000;
  }

  if (datetime.includes("T")) {
    return new Date(datetime + "Z").getTime() / 1000;
  }

  return Number(datetime);
}
