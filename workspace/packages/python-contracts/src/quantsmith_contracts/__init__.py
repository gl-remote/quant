"""Schema loader for Quantsmith shared contracts.

Loads JSON Schema files from ``workspace/packages/contracts/schemas/``
and provides a ``validate`` helper for run artifacts.

Examples::

    from quantsmith_contracts.schema import load_schema
    from quantsmith_contracts.validate import validate_run_artifacts

    schema = load_schema("run")
    validate_run_artifacts(
        run_dir="project_data/reports/runs/r1",
        nav_path="project_data/reports/data/nav.json",
    )
"""
