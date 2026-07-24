"""Stage B sweep driver: n_profile × Ω_pattern on the R30 candidate.

Fires the full 15 × 15 = 225 runs entirely in-process by feeding the CLI's
`_dispatch_vnpy` path through argparse.Namespace stubs, so we only pay one
Python startup and one strategy-registry warmup, not 225.

Each individual run is `--mode single --no-search` under the vnpy engine with
`--build-report` off, matching what `main.py backtest` would produce, and the
resulting backtest_id / metrics are aggregated from the shared DB after all
runs complete. The sweep summary is written to
`docs/research/archived-notes/2026-07-03-value-area-reacceptance-stage-b/stage-b-sweep-summary.md`
so it stays out of the long-form spec and plan.

Usage:
    uv run python scripts/ai_tmp/stage_b_sweep.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from itertools import product
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = REPO_ROOT / "workspace"
sys.path.insert(0, str(WORKSPACE))

from cli.commands.backtest import cmd_backtest, register  # noqa: E402
from config.manager import ConfigManager  # noqa: E402


def _db_path() -> str:
    """从 backtest 配置读取 DB 路径，避免脚本内硬编码。"""
    cm = ConfigManager(env="backtest")
    return str(REPO_ROOT / cm.get_data_config().database_path)


def _make_parser() -> argparse.ArgumentParser:
    """一次性构建 backtest 子命令 parser，重用 CLI 注册链上的所有默认与校验。"""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register(subparsers)
    return parser

GROUP_P = [
    "DCE.p2405",
    "DCE.p2409",
    "DCE.p2501",
    "DCE.p2505",
    "DCE.p2509",
    "DCE.p2601",
    "DCE.p2605",
]
GROUP_M = [
    "DCE.m2501",
    "DCE.m2505",
    "DCE.m2509",
    "DCE.m2601",
    "DCE.m2603",
    "DCE.m2605",
    "DCE.m2607",
    "DCE.m2609",
]
SYMBOLS = [(s, "P") for s in GROUP_P] + [(s, "M") for s in GROUP_M]

N_PROFILES = [48, 96, 144]
PATTERN_SETS: list[tuple[str, list[str]]] = [
    ("C1", ["C1"]),
    ("C2", ["C2"]),
    ("C3", ["C3"]),
    ("C1_C2", ["C1", "C2"]),
    ("C1_C2_C3", ["C1", "C2", "C3"]),
]

BASE_PARAMS: dict[str, object] = {
    "kline_period": "5m",
    "n_step": 48,
    "risk_candidates": ["R0"],
    "direction_candidates": ["D_near", "D_far"],
    "tp_candidates": ["TP_fixed"],
    "direction_mode": "to_poc",
    "stop_widen_multiplier": 1.2,
}


def make_args(
    parser: argparse.ArgumentParser,
    symbol: str,
    params: dict[str, object],
) -> argparse.Namespace:
    """通过真正的 argparse parser 解析出 args，所有默认字段（gui/mode/env 等）自动补齐。"""
    argv = [
        "backtest",
        "--engine",
        "vnpy",
        "--mode",
        "single",
        "--strategy",
        "value_area_multi_attempt_poc_reversion",
        "--symbol",
        symbol,
        "--env",
        "backtest",
        "--strategy-params",
        json.dumps(params, separators=(",", ":")),
    ]
    return parser.parse_args(argv)


def run_sweep() -> Path:
    parser = _make_parser()
    total_runs = len(SYMBOLS) * len(N_PROFILES) * len(PATTERN_SETS)
    print(f"[stage-b] launching {total_runs} runs ...", flush=True)
    started = time.time()
    launched = 0
    for symbol, _grp in SYMBOLS:
        for n_profile, (_pat_label, patterns) in product(N_PROFILES, PATTERN_SETS):
            params = dict(BASE_PARAMS)
            params["n_profile"] = n_profile
            params["pattern_candidates"] = patterns
            args = make_args(parser, symbol, params)
            t0 = time.time()
            cmd_backtest(args)
            launched += 1
            print(
                f"[{launched:03d}/{total_runs}] {symbol}"
                f" n_profile={n_profile} pattern={'+'.join(patterns)}"
                f"  {time.time() - t0:.2f}s",
                flush=True,
            )
    elapsed = time.time() - started
    print(f"[stage-b] done. total {elapsed:.1f}s", flush=True)
    return aggregate_and_write(_db_path())


def aggregate_and_write(db_path: str) -> Path:  # noqa: C901
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT b.id AS backtest_id,
               b.symbol, b.total_return, b.total_trades, b.win_rate,
               b.sharpe_ratio, b.max_ddpercent, b.rgr_ratio
        FROM backtests b
        WHERE b.strategy = 'value_area_multi_attempt_poc_reversion'
        ORDER BY b.id
        """
    ).fetchall()

    param_rows = con.execute(
        """
        SELECT backtest_id, param_name, param_value, param_text, param_type
        FROM backtest_params
        WHERE param_name IN ('n_profile','pattern_candidates')
        """
    ).fetchall()
    params_by_bt: dict[int, dict[str, object]] = {}
    for r in param_rows:
        params_by_bt.setdefault(r["backtest_id"], {})
        val: object
        if r["param_type"] == "float":
            val = r["param_value"]
        else:
            val = r["param_text"]
        params_by_bt[r["backtest_id"]][r["param_name"]] = val

    group_of = {s: "P" for s in GROUP_P} | {s: "M" for s in GROUP_M}
    per_row = []
    for r in rows:
        p = params_by_bt.get(r["backtest_id"], {})
        n_profile = int(p.get("n_profile") or 0)
        pattern_raw = p.get("pattern_candidates")
        try:
            pattern_list: list[str] = json.loads(pattern_raw) if pattern_raw else []
        except (TypeError, json.JSONDecodeError):
            pattern_list = []
        pattern_label = "+".join(pattern_list) if pattern_list else "?"
        per_row.append(
            {
                "backtest_id": r["backtest_id"],
                "symbol": r["symbol"],
                "group": group_of.get(r["symbol"], "?"),
                "n_profile": n_profile,
                "pattern": pattern_label,
                "total_return": r["total_return"] or 0.0,
                "total_trades": r["total_trades"] or 0,
                "win_rate": r["win_rate"] or 0.0,
                "sharpe": r["sharpe_ratio"] or 0.0,
                "rgr": r["rgr_ratio"] or 0.0,
                "max_dd_pct": r["max_ddpercent"] or 0.0,
            }
        )
    con.close()

    def cell_stats(recs: list[dict[str, object]]) -> dict[str, float]:
        n = len(recs)
        if n == 0:
            return {"n": 0, "ret_mean": 0, "trade_sum": 0, "wr_mean": 0, "rgr_mean": 0}
        return {
            "n": n,
            "ret_mean": sum(float(rec["total_return"]) for rec in recs) / n,
            "trade_sum": sum(int(rec["total_trades"]) for rec in recs),
            "wr_mean": sum(float(rec["win_rate"]) for rec in recs) / n,
            "rgr_mean": sum(float(rec["rgr"]) for rec in recs) / n,
        }

    def matrix(group_key: str) -> str:
        lines = [
            f"### Group_{group_key}",
            "",
            "| n_profile \\ pattern | " + " | ".join(k for k, _ in PATTERN_SETS) + " |",
            "|---|" + "|".join(["---"] * len(PATTERN_SETS)) + "|",
        ]
        for n_profile in N_PROFILES:
            row = [f"**{n_profile}**"]
            for label, patterns in PATTERN_SETS:
                cell = [
                    rec
                    for rec in per_row
                    if rec["group"] == group_key
                    and rec["n_profile"] == n_profile
                    and rec["pattern"] == "+".join(patterns)
                ]
                stats = cell_stats(cell)
                row.append(
                    f"ret={stats['ret_mean']:.3f} · trades={int(stats['trade_sum'])}"
                    f" · wr={stats['wr_mean']:.2f} · rgr={stats['rgr_mean']:.3f}"
                    f" (n={int(stats['n'])})"
                )
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    # 历史归档：原 driver 输出到 docs/workbench，稳定结论已迁至
    # docs/research/archived-notes/2026-07-03-value-area-reacceptance-stage-b/。
    # 若重跑此脚本，请自行修改 outdir 到当前 workbench 位置或另建归档目录。
    outdir = REPO_ROOT / "docs/workbench"
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / "stage-b-sweep-summary.md"
    with outfile.open("w") as f:
        f.write("# Stage B sweep summary — n_profile × Ω_pattern\n\n")
        f.write(
            "> Source: `scripts/ai_tmp/stage_b_sweep.py`\n"
            "> Fixed: R0 only, D_near+D_far, TP_fixed, direction_mode=to_poc, "
            "λ=1.2, n_step=48\n"
            "> Cells: mean(total_return) · sum(trades) · mean(win_rate) · mean(rgr) (n=samples)\n\n"
        )
        f.write(matrix("P"))
        f.write("\n\n")
        f.write(matrix("M"))
        f.write("\n\n")
        f.write("## All rows (raw)\n\n")
        f.write("| bt_id | symbol | grp | n_profile | pattern | ret | trades | wr | rgr | maxdd% |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for rec in per_row:
            f.write(
                f"| {rec['backtest_id']} | {rec['symbol']} | {rec['group']} |"
                f" {rec['n_profile']} | {rec['pattern']} |"
                f" {float(rec['total_return']):.4f} | {int(rec['total_trades'])} |"
                f" {float(rec['win_rate']):.3f} | {float(rec['rgr']):.3f} |"
                f" {float(rec['max_dd_pct']):.2f} |\n"
            )
    print(f"[stage-b] summary written -> {outfile.relative_to(REPO_ROOT)}", flush=True)
    return outfile


if __name__ == "__main__":
    run_sweep()
