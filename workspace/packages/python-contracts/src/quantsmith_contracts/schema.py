"""Load JSON Schema files from the shared contracts directory."""

import json
from pathlib import Path
from typing import Any

# Path to schemas directory relative to this source file.
# In editable-install mode (pip install -e), the source lives at the
# original location, so we can walk up to the repo root and then to
# workspace/packages/contracts/schemas/.
_SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "contracts" / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    """Load a JSON Schema file by its basename (without .schema.json extension).

    Args:
        name: Schema basename, e.g. ``"run"``, ``"summary"``, ``"optuna"``.

    Returns:
        Parsed JSON Schema dict.
    """
    path = _SCHEMAS_DIR / f"{name}.schema.json"
    with open(path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data
