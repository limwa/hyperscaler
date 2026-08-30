# Repository Guidelines

## Organization

- Each module lives in its own top-level directory.
- Top-level module directories must use exact `snake_case`.
- Python package names must match the top-level directory name exactly.
- `project.name` in each module `pyproject.toml` must match the directory name exactly.
- Use a flat package layout:
  - `module_name/module_name/...`
  - `module_name/tests/...`
- Do not use a `src/` layout in this repository.

## Python Conventions

- Use typed Python.
- Keep configuration explicit:
  - do not hide important defaults inside Python models
  - fail if required config values are omitted
- Schema-backed validation is preferred for configuration parsing.
- Use double-underscore (`__name`) for private helper functions and methods.
