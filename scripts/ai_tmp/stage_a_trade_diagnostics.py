"""
文件级元信息：
- 创建背景：Stage A smoke 校核（DCE.p2601 5m），需要从 backtest_trades 抽 exit_reason
  分布与 decision_payload_json，验证策略三层诊断是否非 placeholder。
- 用途：一次性诊断脚本，同时打印 exit_reason 直方图与前几笔 open/close 的 payload。
- 注意事项：仅供 Stage A 人工核对，跑完不长期保留；backtest_id 通过命令行参数传入。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="project_data/database/backtest/quant.db")
    parser.add_argument("--backtest-id", type=int, default=1)
    parser.add_argument("--sample", type=int, default=3)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    cur.execute("SELECT reason, offset FROM backtest_trades WHERE backtest_id=?", (args.backtest_id,))
    rows = cur.fetchall()
    all_reasons = Counter(r[0] for r in rows)
    close_reasons = Counter(r[0] for r in rows if r[1] == "close")
    open_reasons = Counter(r[0] for r in rows if r[1] == "open")

    print(f"trade 总数 = {len(rows)} (open={sum(open_reasons.values())} close={sum(close_reasons.values())})")
    print("\nOPEN reason 分布:")
    for k, v in open_reasons.most_common():
        print(f"  {k:<50} {v}")
    print("\nCLOSE reason 分布:")
    for k, v in close_reasons.most_common():
        print(f"  {k:<50} {v}")

    def dump_layer(payload: dict[str, object], layer: str) -> None:
        # decision_payload envelope: {schema_version, source, event_type, diagnostics: {...}}
        diagnostics = payload.get("diagnostics") if isinstance(payload, dict) else None
        obj = diagnostics.get(layer) if isinstance(diagnostics, dict) else None
        if obj is None or (isinstance(obj, dict) and not obj):
            print(f"  [{layer}] <MISSING or EMPTY>")
            return
        text = json.dumps(obj, ensure_ascii=False)
        print(f"  [{layer}] {text[:400]}")

    def sample(offset: str) -> None:
        cur.execute(
            "SELECT datetime, direction, offset, price, reason, decision_payload_json "
            "FROM backtest_trades WHERE backtest_id=? AND offset=? LIMIT ?",
            (args.backtest_id, offset, args.sample),
        )
        print(f"\n=== 抽 {args.sample} 个 {offset.upper()} payload ===")
        for row in cur.fetchall():
            dt, direction, off, price, reason, payload_json = row
            print(f"\n{dt} {direction} {off} @{price} reason={reason}")
            payload = json.loads(payload_json) if payload_json else {}
            for layer in ("strategy", "alpha", "risk", "execution"):
                dump_layer(payload, layer)

    sample("open")
    sample("close")


if __name__ == "__main__":
    main()
