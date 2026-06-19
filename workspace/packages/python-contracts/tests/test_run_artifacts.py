"""Contract tests: validate real run artifacts against JSON schemas.

These tests read the latest ``output/r{N}/data/*.json`` files and check them
against the schemas defined in ``workspace/packages/contracts/schemas/``.

If no run directory exists (e.g. first-time clone), tests are skipped.
"""

from pathlib import Path

import pytest
from quantsmith_contracts.validate import validate_run_artifacts


def test_latest_run_artifacts_conform_to_schemas(
    latest_run_dir: Path | None,
    nav_path: Path | None,
) -> None:
    """All 7 artifacts of the latest run + nav.json pass schema validation."""
    if latest_run_dir is None:
        pytest.skip("No output/r{N}/ directory found — run `bash tools/backtest-ma.sh` first")

    issues = validate_run_artifacts(str(latest_run_dir), nav_path=str(nav_path) if nav_path else None)
    if issues:
        failing = "\n".join(f"  {i}" for i in issues)
        pytest.fail(f"Contract validation failed ({len(issues)} issue(s)):\n{failing}")
