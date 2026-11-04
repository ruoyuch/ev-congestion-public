# Repository Guidelines

Conventions for anyone (coauthor or coding agent) changing this repository.

## Structure

- Reusable Python logic lives in the package `src/ev_congestion/`, one module per pipeline stage. Paths and parameters come from `src/ev_congestion/config.py`, which reads `.env`; never hardcode paths.
- `pipeline/run_all.py` only orchestrates: it calls `src` functions and the Stata master file in order. Logic belongs in `src/` or `stata/`, not in the pipeline script.
- All regressions are in `stata/`. `_setup.do` defines paths, the control set `$controls` and shared helpers; each numbered do-file produces specific exhibits (see README).
- `data/input/`, `data/intermediate/` (CSV) and `data/gis/` are published and tracked. Never commit `data/raw/`, `.dta` files, `output/` or `.env`.
- `output/tables/` and `output/figures/` are machine-generated and must be reproducible by rerunning the pipeline.
- `docs/manuscript.tex` reads its tables and figures from `../output/`. Only hand-made exhibits (`flow_chart.pdf`) live next to it.

## Commands

- `uv sync --dev` sets up the environment; run everything with `uv run <cmd>`. Add packages with `uv add`; commit `pyproject.toml` and `uv.lock` together.
- Core package versions are pinned to those used for the paper. Upgrading them can change the last floating-point digits of the intermediate CSVs, so check `uv run pytest` and the CSV checksums after any upgrade.
- `uv run prek run -a` runs ruff (lint + format) and the hygiene hooks; CI runs them plus `pytest` on every push.
- After changing anything that affects results: `uv run pipeline/run_all.py --from <stage> --force`, then `uv run pytest`. `tests/reference/` holds the published tables; update a reference only when a result is meant to change, and say so in the commit.

## Consistency

- Text in `docs/manuscript.tex` must match the code: variable definitions, sample, fixed effects, clustering, and every number quoted from a table or figure.
- When a specification changes, update the table, the paper text, the README exhibit map and `tests/reference/` together.

## Version control

- Work on a branch and merge to `main` when a version is ready to be public. Do not commit on the authors' behalf.
