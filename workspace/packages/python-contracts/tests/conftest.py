"""Shared fixtures for contract validation tests."""

from pathlib import Path

import pytest

# conftest.py -> tests/ -> python-contracts/ -> packages/ -> workspace/ -> <repo_root>
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return _REPO_ROOT


@pytest.fixture(scope="session")
def latest_run_dir(repo_root: Path) -> Path | None:
    """Return the latest ``output/r{N}`` directory, or None if none exists."""
    output_dir = repo_root / "output"
    if not output_dir.is_dir():
        return None
    run_dirs: list[tuple[int, Path]] = []
    for child in output_dir.iterdir():
        if child.is_dir() and child.name.startswith("r") and child.name[1:].isdigit():
            run_dirs.append((int(child.name[1:]), child))
    if not run_dirs:
        return None
    run_dirs.sort(key=lambda x: x[0], reverse=True)
    return run_dirs[0][1]


@pytest.fixture(scope="session")
def nav_path(repo_root: Path) -> Path | None:
    """Return the nav.json path, or None if missing."""
    p = repo_root / "output" / "data" / "nav.json"
    return p if p.is_file() else None
