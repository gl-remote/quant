"""Validate run artifacts against Quantsmith shared schemas.

Usage::

    from quant_contracts.validate import validate_run_artifacts
    issues = validate_run_artifacts("output/r1/data", nav_path="output/data/nav.json")
    for issue in issues:
        print(issue)

Returns a list of strings.  Empty list => all artifacts conform to their schemas.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import ValidationError as _ValidationError
from jsonschema import validate as _jsonschema_validate

from .schema import load_schema

# Map of JSON filename (without .json) -> schema name
_RUN_ARTIFACT_MAP = {
    "run": "run",
    "summary": "summary",
    "backtests": "backtests",
    "equity": "equity",
    "trades": "trades",
    "optuna": "optuna",
    "logs": "logs",
}


def validate_run_artifacts(
    run_dir: str | Path,
    nav_path: str | Path | None = None,
) -> list[str]:
    """Validate all artifacts of a single run.

    Checks 7 files under ``<run_dir>/data/`` plus an optional
    ``nav_path`` for the global navigation index.

    Args:
        run_dir:  Path to ``output/r{run_id}``.
        nav_path: Path to ``output/data/nav.json`` (optional).

    Returns:
        List of human-readable issue descriptions. Empty list means all OK.
    """
    run_dir = Path(run_dir)
    data_dir = run_dir / "data"
    issues: list[str] = []

    for filename, schema_name in _RUN_ARTIFACT_MAP.items():
        artifact_path = data_dir / f"{filename}.json"
        if not artifact_path.is_file():
            issues.append(f"MISSING: {artifact_path}")
            continue
        try:
            schema = load_schema(schema_name)
        except FileNotFoundError:
            issues.append(f"SCHEMA_NOT_FOUND: {schema_name}.schema.json")
            continue
        except json.JSONDecodeError as exc:
            issues.append(f"SCHEMA_INVALID_JSON: {schema_name}.schema.json ({exc})")
            continue

        try:
            instance = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(f"INVALID_JSON: {artifact_path} ({exc})")
            continue

        try:
            _jsonschema_validate(instance, schema)
        except _ValidationError as exc:
            issues.append(f"SCHEMA_FAIL: {artifact_path} | {exc.message} (path={list(exc.absolute_path)})")

    # --- nav.json (global) ---
    if nav_path is not None:
        nav_path = Path(nav_path)
        if not nav_path.is_file():
            issues.append(f"MISSING: {nav_path}")
        else:
            try:
                schema = load_schema("nav")
                instance = json.loads(nav_path.read_text(encoding="utf-8"))
                _jsonschema_validate(instance, schema)
            except FileNotFoundError:
                issues.append("SCHEMA_NOT_FOUND: nav.schema.json")
            except json.JSONDecodeError as exc:
                issues.append(f"INVALID_JSON / SCHEMA_INVALID_JSON: {nav_path} ({exc})")
            except _ValidationError as exc:
                issues.append(f"SCHEMA_FAIL: {nav_path} | {exc.message} (path={list(exc.absolute_path)})")

    return issues
