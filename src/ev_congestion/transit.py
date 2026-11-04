"""ZIP-level panel -> urbanized-area (UZA) panel for the transit regressions.

Transit ridership is reported by agency and aggregated to Census urbanized
areas, so the BEV and control variables are aggregated from ZIPs to UZAs
with the HUD/Census ZIP-to-UZA crosswalk.

Inputs
------
``transit_uza.csv``       NTD unlinked passenger trips by UZA (wide: one column per year)
``uza_zip_crosswalk.csv`` ZIP -> UZA assignment (``zip_code``, ``ua``, ``ua_name``)
plus the ZIP-level files ``vehicle_proportion.csv``, ``zip_code_acs.csv``
and ``zip_code_evcs_count.csv``.

Output
------
``uz_ntd_ev.csv``
    One row per UZA-year with ``pt_ridership`` (annual unlinked trips) and
    UZA totals of :data:`SUM_VARS`; ``hh_median_income`` is the
    population-weighted mean across ZIPs. UZA-years with
    zero or missing ridership are dropped.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

#: Variables summed across the ZIPs of a UZA.
SUM_VARS = [
    "count_Battery Electric (BEV)",
    "land_area",
    "population",
    "travel_time_45_59",
    "travel_time_60_89",
    "travel_time_90_plus",
    "total_travel_time",
    "white_population",
    "bachelor_degree_population",
    "public_transport_commute",
    "total_commute",
    "dc_count",
    "total_count",
]

#: Variables averaged across ZIPs, weighted by population.
WEIGHTED_VARS = ["hh_median_income"]

KEY = ["ua", "ua_name", "year"]


def load_ridership(path: Path) -> pd.DataFrame:
    """NTD ridership reshaped to long format (``ua``, ``ua_name``, ``year``, ``pt_ridership``)."""
    return (
        pd.read_csv(path)
        .rename(columns={"UACE CD": "ua", "UZA Name": "ua_name"})
        .melt(id_vars=["ua", "ua_name"], var_name="year", value_name="pt_ridership")
        .assign(ua=lambda d: d["ua"].astype(str).str.zfill(5), year=lambda d: d["year"].astype(int))
        .sort_values(["ua", "year"])[KEY + ["pt_ridership"]]
    )


def build_uza_panel(input_dir: Path, intermediate_dir: Path, output_path: Path) -> pd.DataFrame:
    """Write ``uz_ntd_ev.csv`` (see module docstring)."""
    input_dir, intermediate_dir = Path(input_dir), Path(intermediate_dir)
    ridership = load_ridership(input_dir / "transit_uza.csv")

    vehicles = pd.read_csv(intermediate_dir / "vehicle_proportion.csv")
    acs = pd.read_csv(intermediate_dir / "zip_code_acs.csv").rename(
        columns={"geo_code": "zip_code"}
    )
    evcs = pd.read_csv(intermediate_dir / "zip_code_evcs_count.csv").rename(
        columns={"ZIP": "zip_code", "Year": "year"}
    )
    xwalk = pd.read_csv(input_dir / "uza_zip_crosswalk.csv")
    xwalk["zip_code"] = pd.to_numeric(xwalk["zip_code"], errors="coerce")
    xwalk["ua"] = xwalk["ua"].astype(str).str.zfill(5)

    zips = (
        vehicles.merge(acs, how="left", on=["zip_code", "year"])
        .merge(xwalk, how="left", on="zip_code")
        .merge(evcs, how="left", on=["zip_code", "year"])
    )

    sums = zips.groupby(KEY, as_index=False)[SUM_VARS].sum()

    def weighted(g: pd.DataFrame) -> pd.Series:
        w = g["population"]
        return pd.Series(
            {v: (g[v] * w).sum() / w.sum() if w.sum() != 0 else None for v in WEIGHTED_VARS}
        )

    means = zips.groupby(KEY)[WEIGHTED_VARS + ["population"]].apply(weighted).reset_index()

    out = ridership.merge(sums, how="left", on=KEY).merge(means, how="left", on=KEY)
    out = out[out["pt_ridership"] > 0]
    out.to_csv(output_path, index=False)
    return out
