# Electric vehicle and traffic congestion

[![CI](https://github.com/ruoyuch/ev-congestion-public/actions/workflows/ci.yml/badge.svg)](https://github.com/ruoyuch/ev-congestion-public/actions/workflows/ci.yml)

Replication package for ***The electric vehicle transition exacerbates traffic
congestion in California*** (Chen, Liu, and Zhou;
[working paper](https://www.rchen.info/pdf/wp_ev_congestion.pdf)).

## Pipeline

`uv run pipeline/run_all.py` runs these stages in order:

```
station_year → zip_traffic → vehicles → covariates → transit → neighbors → stata → maps
└────────────── Python: build the ZIP-year panel ──────────────┘  └ regressions ┘  └ maps ┘
```

**Steps**
- **Python** (`src/ev_congestion/`) process the source data into CSVs in `data/intermediate/`.
- **Stata** calls Stata in batch mode (`STATA_BIN -b do
  00_master.do`) and writes `.tex` tables to `output/tables/` and `.pdf` figures to `output/figures/`.
- **Maps** writes the maps to `output/figures/`.

A stage is skipped when its outputs exist. Use `--force` for a full rebuild, `--from <stage>` to rerun from a stage, `--only <stage>` to run one stage, and `--list` to see stage status.

## Replicate

Requirements: [uv](https://docs.astral.sh/uv/) (Python venv management), Stata 17+, and TeX Live for the manuscript.

```bash
# setup environment
uv sync                                               # build python venv
cp .env.example .env                                  # set STATA_BIN
(cd stata && stata-mp -b do install_packages.do)      # install Stata package
# execution
uv run pipeline/run_all.py                            # run pipeline ~2 min
uv run pytest                                         # run tests (optional)
# compile manuscript
(cd docs && latexmk -pdf -outdir=out manuscript.tex)  # compile latex to pdf
```

| start from | command | time |
|---|---|---|
| `data/intermediate/` (in repo) | `uv run pipeline/run_all.py` | ~2 min |
| `data/input/` (in repo) | `... --from zip_traffic --force` | ~3 min |
| raw PeMS archive (not in repo) | `... --from station_year --force` | ~5 min/yr

## Raw PeMS data
The data is about 22 GB per year, with a free account at <https://pems.dot.ca.gov> to download.
Set `RAW_PEMS_DIR` to use it. A fresh download can differ slightly because PeMS revises station metadata.
You do **not** need the raw PeMS data to replicate the results.

## License
- Code: MIT.
- Derived data (`data/intermediate/`,`data/input/traffic_station_year/`): CC BY 4.0.
- Third-party files keep their original terms (sources in `data/README.md`).
