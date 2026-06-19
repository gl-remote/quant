"""Schema loader for Quantsmith shared contracts.

Loads JSON Schema files from ``workspace/packages/contracts/schemas/``
and provides a ``validate`` helper for run artifacts.

Examples::

    from quant_contracts.schema import load_schema
    from quant_contracts.validate import validate_run_artifacts

    schema = load_schema("run")
    validate_run_artifacts(run_dir="output/r1/data", nav_path="output/data/nav.json")
"""
