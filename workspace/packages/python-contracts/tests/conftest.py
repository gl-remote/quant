"""Shared fixtures for contract validation tests."""

import sys
from pathlib import Path

import pytest

# conftest.py -> tests/ -> python-contracts/ -> packages/ -> workspace/ -> <repo_root>
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return _REPO_ROOT


@pytest.fixture(scope="session")
def latest_run_dir(repo_root: Path) -> Path | None:
    """Return the latest ``project_data/reports/runs/r{N}`` directory, or None if none exists."""
    runs_dir = repo_root / "project_data" / "reports" / "runs"
    if not runs_dir.is_dir():
        return None
    run_dirs: list[tuple[int, Path]] = []
    for child in runs_dir.iterdir():
        if child.is_dir() and child.name.startswith("r") and child.name[1:].isdigit():
            run_dirs.append((int(child.name[1:]), child))
    if not run_dirs:
        return None
    run_dirs.sort(key=lambda x: x[0], reverse=True)
    return run_dirs[0][1]


@pytest.fixture(scope="session")
def nav_path(repo_root: Path) -> Path | None:
    """Return the nav.json path, or None if missing."""
    p = repo_root / "project_data" / "reports" / "data" / "nav.json"
    return p if p.is_file() else None
