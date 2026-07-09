"""Print side-by-side mean_net_atr / paired_diff_vs_E across cost models & scales."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "project_data" / "research" / "structural_shaping_gatekeeper"

FILES = [
    ("S1 flat", "structural_shaping_gatekeeper_scale1_20260706_184310.json"),
    ("S1 real", "structural_shaping_gatekeeper_scale1_realcost_20260706_185751.json"),
    ("S3 flat", "structural_shaping_gatekeeper_scale3_20260706_174647.json"),
    ("S3 real", "structural_shaping_gatekeeper_scale3_realcost_20260706_185944.json"),
    ("S5 flat", "structural_shaping_gatekeeper_scale5_20260706_162925.json"),
    ("S5 real", "structural_shaping_gatekeeper_scale5_realcost_20260706_190541.json"),
]


def main() -> None:
    mean_rows: dict[str, dict[str, float]] = {}
    diff_rows: dict[str, dict[str, tuple[float, float, float, float]]] = {}
    labels: list[str] = []
    for label, fname in FILES:
        labels.append(label)
        d = json.loads((ROOT / fname).read_text())
        for c in d["combos"]:
            k = c["key"]
            mean_rows.setdefault(k, {})[label] = c["mean_net_atr"]
            if c.get("paired_diff_vs_E_mean") is not None:
                diff_rows.setdefault(k, {})[label] = (
                    c["paired_diff_vs_E_mean"],
                    c["paired_diff_vs_E_ci_lo"],
                    c["paired_diff_vs_E_ci_hi"],
                    c["paired_diff_vs_E_p_gt_0"],
                )

    print("=== mean_net_atr (成本后每笔 ATR) ===\n")
    header = f"{'combo':<6}" + " ".join(f"{l:>10}" for l in labels)
    print(header)
    for k in ["A", "B", "C", "D", "E", "F", "D2", "G", "H", "I", "J", "K"]:
        if k not in mean_rows:
            continue
        vals = " ".join(f"{mean_rows[k].get(l, float('nan')):+10.4f}" for l in labels)
        print(f"{k:<6}{vals}")

    print("\n=== paired diff vs E (mean, p_gt_0) ===\n")
    header = f"{'combo':<6}" + " ".join(f"{l:>18}" for l in labels)
    print(header)
    for k in ["A", "B", "C", "D", "F", "D2", "G", "H", "I", "J", "K"]:
        if k not in diff_rows:
            continue
        cells = []
        for l in labels:
            v = diff_rows[k].get(l)
            if v is None:
                cells.append(" " * 18)
            else:
                mean, _, _, p = v
                cells.append(f"{mean:+.4f} p={p:.3f} ")
        print(f"{k:<6}" + " ".join(cells))


if __name__ == "__main__":
    main()
