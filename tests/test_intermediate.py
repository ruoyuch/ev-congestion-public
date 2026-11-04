"""Consistency checks on the ZIP-year files in ``data/intermediate``.

Skipped for any file that has not been built yet.
"""

import pandas as pd
import pytest

from ev_congestion.config import CFG

PANELS = {
    # file: (expected years, minimum number of ZIPs)
    "zip_code_congestion_index.csv": (range(2010, 2025), 1500),
    "zip_code_congestion_index_radius.csv": (range(2014, 2025), 1700),
    "vehicle_proportion.csv": (range(2010, 2025), 1700),
}


def _read(name):
    path = CFG.intermediate_dir / name
    if not path.exists():
        pytest.skip(f"{name} not built")
    return pd.read_csv(path, low_memory=False)


@pytest.mark.parametrize("name", PANELS)
def test_zip_year_panel(name):
    df = _read(name)
    years, min_zips = PANELS[name]
    assert not df.duplicated(["zip_code", "year"]).any()
    assert set(df["year"]) <= set(years)
    # California ZIPs, plus 97635 (New Pine Creek), a ZCTA straddling the OR/CA border
    assert df["zip_code"].between(90000, 96199).sum() >= len(df) - 15, "non-California ZIP"
    assert set(df.loc[~df["zip_code"].between(90000, 96199), "zip_code"]) <= {97635}
    assert df["zip_code"].nunique() >= min_zips


def test_radius_columns_complete():
    df = _read("zip_code_congestion_index_radius.csv")
    for prefix in ("weekday_peak_", "weekday_mn_"):
        for r in range(1, 16):
            assert f"{prefix}weighted_speed_r{r}" in df.columns
    # more stations fall within larger radii
    assert (df["weekday_peak_n_stations_r15"] >= df["weekday_peak_n_stations_r5"]).all()


def test_neighbor_pairs_symmetric():
    df = _read("zip_neighbor_pairs.csv")
    fwd = set(zip(df["zip_code"], df["neighbor_zip"], strict=True))
    assert all((b, a) in fwd for a, b in fwd)
    assert df["dist_km"].between(0, 15).all()
