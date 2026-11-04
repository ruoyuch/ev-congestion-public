"""Project paths and run parameters, read from a local ``.env`` file.

Every machine-specific setting (where the raw PeMS archive lives, where the
Stata binary is, API keys) is kept in ``.env`` at the repository root. That
file is gitignored; ``.env.example`` documents every key and is committed.

Relative paths in ``.env`` are resolved against the repository root, so the
defaults work out of the box for a fresh clone::

    from ev_congestion.config import CFG
    CFG.raw_pems_dir        # Path to the PeMS archive (station_hour/, station_metadata/)
    CFG.intermediate_dir    # ZIP-year CSVs consumed by Stata
    CFG.tables_dir          # output/tables: regression tables (.tex)
    CFG.figures_dir         # output/figures: figures (.pdf, .png)

Environment variables that are already set take precedence over ``.env``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path = REPO_ROOT / ".env") -> dict[str, str]:
    """Parse a minimal ``KEY=VALUE`` file into a dict.

    Blank lines and lines starting with ``#`` are ignored; surrounding quotes
    on the value are stripped. No variable interpolation is performed. A
    missing file returns an empty dict, so the package still imports on a
    fresh clone before ``.env`` has been created.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get(env: dict[str, str], key: str, default: str = "") -> str:
    return os.environ.get(key, env.get(key, default))


def _path(env: dict[str, str], key: str, default: str) -> Path:
    p = Path(os.path.expanduser(_get(env, key, default)))
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass(frozen=True)
class Config:
    """Resolved settings. Build it with :func:`get_config`, not directly."""

    raw_pems_dir: Path  # PeMS archive root: station_hour/<year>/, station_metadata/<year>/
    data_dir: Path  # repository data root
    input_dir: Path  # small third-party inputs shipped with the repo
    intermediate_dir: Path  # pipeline outputs read by Stata (ZIP-year / UZA-year CSVs, .dta)
    gis_dir: Path  # zcta_ca.gpkg, ca_county/, ca_state/ (shipped in data/gis)
    output_dir: Path  # generated tables/ and figures/ (default output/)
    stata_bin: str  # Stata executable used by run_all.py
    census_api_key: str  # only needed to re-download ACS controls
    chromedriver_path: str  # only needed to re-download raw PeMS files
    downloads_dir: Path  # browser download folder used by the PeMS downloader
    n_perm: int  # permutation draws in the randomization test
    seed: int  # RNG seed for the permutation test

    @property
    def tables_dir(self) -> Path:
        """Regression tables (.tex) written by Stata."""
        return self.output_dir / "tables"

    @property
    def figures_dir(self) -> Path:
        """Figures written by Stata (.pdf) and by :mod:`ev_congestion.maps` (.png)."""
        return self.output_dir / "figures"

    @property
    def station_hour_dir(self) -> Path:
        return self.raw_pems_dir / "station_hour"

    @property
    def station_metadata_dir(self) -> Path:
        return self.raw_pems_dir / "station_metadata"

    @property
    def station_year_dir(self) -> Path:
        """Station-year traffic summaries (output of :mod:`ev_congestion.station_year`)."""
        return self.input_dir / "traffic_station_year"

    @property
    def zcta_path(self) -> Path:
        """2020 Census ZCTA polygons for California (TIGER/Line, GeoPackage)."""
        return self.gis_dir / "zcta_ca.gpkg"


def get_config(env_file: Path = REPO_ROOT / ".env") -> Config:
    """Read ``.env`` (plus the process environment) and return a :class:`Config`."""
    env = load_dotenv(env_file)
    data_dir = _path(env, "DATA_DIR", "data")
    return Config(
        raw_pems_dir=_path(env, "RAW_PEMS_DIR", "data/raw/pems"),
        data_dir=data_dir,
        input_dir=_path(env, "INPUT_DIR", str(data_dir / "input")),
        intermediate_dir=_path(env, "INTERMEDIATE_DIR", str(data_dir / "intermediate")),
        gis_dir=_path(env, "GIS_DIR", str(data_dir / "gis")),
        output_dir=_path(env, "OUTPUT_DIR", "output"),
        stata_bin=_get(env, "STATA_BIN", "stata-mp"),
        census_api_key=_get(env, "CENSUS_API_KEY"),
        chromedriver_path=_get(env, "CHROMEDRIVER_PATH", "chromedriver"),
        downloads_dir=_path(env, "DOWNLOADS_DIR", "~/Downloads"),
        n_perm=int(_get(env, "N_PERM", "1000")),
        seed=int(_get(env, "SEED", "20260704")),
    )


CFG = get_config()
