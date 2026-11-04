"""ZIP-level control variables: ACS demographics and charging stations.

Outputs (all in ``INTERMEDIATE_DIR``):

``zip_code_acs.csv`` (:func:`download_acs_controls`)
    ACS 5-year estimates by California ZCTA, 2014-2023. Columns are the short names in
    :data:`ACS_VARIABLES` plus ``geo_code`` (ZIP), ``year`` and ``dataset``.
    Rows with a missing value or the Census sentinel -666666666 in any
    variable are dropped. Requires ``CENSUS_API_KEY`` in ``.env``.

``zip_code_acs_income_bins.csv`` (:func:`download_income_bins`)
    ACS table B19001 (household income, 16 brackets) by ZCTA. Used in Stata to
    build the CVRP income-cap instrument: the pre-policy (2014-15) share of
    households earning >= $100k, interacted with a post-2016 indicator.

``zip_code_evcs_count.csv`` (:func:`build_charger_counts`)
    Cumulative Level 2 ports and DC fast ports opened by ZIP and year, from
    the U.S. DOE Alternative Fuels Data Center station list.

"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

CENSUS_MISSING = -666666666

#: California ZCTAs run from 90001 to 96162.
CA_ZCTA_RANGE = ("90000", "96199")

#: ACS 5-year vintages used in the paper (the regressions cover 2014-2023).
ACS_YEARS = range(2014, 2024)

#: ACS 5-year variables used as controls (code -> short column name).
ACS_VARIABLES = {
    "B19013_001E": "hh_median_income",
    "B01003_001E": "population",
    "B25077_001E": "home_median_value",
    "B02001_002E": "white_population",
    "B15003_022E": "bachelor_degree_population",
    "B08301_001E": "total_commute",  # workers 16+, all means of transport
    "B08301_010E": "public_transport_commute",  # ... by public transportation
    "B08303_001E": "total_travel_time",  # workers who did not work at home
    "B08303_011E": "travel_time_45_59",
    "B08303_012E": "travel_time_60_89",
    "B08303_013E": "travel_time_90_plus",
}

#: ACS B19001 household income brackets (code -> short column name).
INCOME_BINS = {
    "B19001_001E": "hh_total",
    "B19001_002E": "hh_inc_lt10k",
    "B19001_003E": "hh_inc_10_15k",
    "B19001_004E": "hh_inc_15_20k",
    "B19001_005E": "hh_inc_20_25k",
    "B19001_006E": "hh_inc_25_30k",
    "B19001_007E": "hh_inc_30_35k",
    "B19001_008E": "hh_inc_35_40k",
    "B19001_009E": "hh_inc_40_45k",
    "B19001_010E": "hh_inc_45_50k",
    "B19001_011E": "hh_inc_50_60k",
    "B19001_012E": "hh_inc_60_75k",
    "B19001_013E": "hh_inc_75_100k",
    "B19001_014E": "hh_inc_100_125k",
    "B19001_015E": "hh_inc_125_150k",
    "B19001_016E": "hh_inc_150_200k",
    "B19001_017E": "hh_inc_gt200k",
}
_BELOW_75K = [
    v
    for v in INCOME_BINS.values()
    if v
    not in (
        "hh_total",
        "hh_inc_75_100k",
        "hh_inc_100_125k",
        "hh_inc_125_150k",
        "hh_inc_150_200k",
        "hh_inc_gt200k",
    )
]


# ---------------------------------------------------------------------------
# ACS
# ---------------------------------------------------------------------------
def fetch_acs(
    year: int, variables: dict[str, str], api_key: str, dataset: str = "acs5"
) -> pd.DataFrame:
    """Download one ACS year for all ZCTAs in the U.S.

    Returns columns ``geo_name``, the short names in ``variables``,
    ``geo_code`` (5-digit ZCTA string), ``year`` and ``dataset``. The API
    returns all U.S. ZCTAs; only California ones (900xx-961xx) are kept.
    """
    url = (
        f"https://api.census.gov/data/{year}/acs/{dataset}"
        f"?get=NAME,{','.join(variables)}&for=zip%20code%20tabulation%20area:*&key={api_key}"
    )
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    rows = resp.json()
    df = pd.DataFrame(rows[1:], columns=rows[0])
    for code in variables:
        df[code] = pd.to_numeric(df[code], errors="coerce")
    df = df.rename(
        columns={**variables, "NAME": "geo_name", "zip code tabulation area": "geo_code"}
    )
    df["geo_code"] = df["geo_code"].astype(str).str.zfill(5)
    df["year"], df["dataset"] = year, dataset
    return df[df["geo_code"].between(*CA_ZCTA_RANGE)].reset_index(drop=True)


def download_acs_controls(
    api_key: str, output_path: Path, years: range = ACS_YEARS
) -> pd.DataFrame:
    """Write ``zip_code_acs.csv``: ACS controls, complete cases only."""
    df = pd.concat([fetch_acs(y, ACS_VARIABLES, api_key) for y in years], ignore_index=True)
    for col in ACS_VARIABLES.values():
        df = df[df[col].notna() & (df[col] != CENSUS_MISSING)]
    df.to_csv(output_path, index=False)
    log.info("ACS controls: %d ZIP-years", len(df))
    return df


def download_income_bins(api_key: str, output_path: Path, years: range = ACS_YEARS) -> pd.DataFrame:
    """Write ``zip_code_acs_income_bins.csv`` with B19001 brackets and income shares.

    Adds ``share_above_150k``, ``share_above_200k`` and ``share_below_75k``
    (shares of households; NaN when ``hh_total`` is 0 or missing). The paper's
    instrument uses the >= $100k share, which Stata computes from the bins.
    """
    frames = []
    for y in years:
        df = fetch_acs(y, INCOME_BINS, api_key)
        df[list(INCOME_BINS.values())] = df[list(INCOME_BINS.values())].replace(
            CENSUS_MISSING, pd.NA
        )
        total = df["hh_total"].replace(0, pd.NA)
        df["share_above_150k"] = (df["hh_inc_150_200k"] + df["hh_inc_gt200k"]) / total
        df["share_above_200k"] = df["hh_inc_gt200k"] / total
        df["share_below_75k"] = df[_BELOW_75K].sum(axis=1) / total
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(output_path, index=False)
    log.info("ACS income bins: %d ZIP-years", len(out))
    return out


# ---------------------------------------------------------------------------
# EV charging stations
# ---------------------------------------------------------------------------
def build_charger_counts(afdc_csv: Path, output_path: Path) -> pd.DataFrame:
    """Cumulative charger ports by ZIP and year from the AFDC station export.

    Stations with a non-5-digit ZIP or no valid ``Open Date`` are dropped.
    ZIPs are read as text so the result does not depend on pandas' chunked
    type inference (one mistyped ZIP, ``09048``, survives as an out-of-state
    code and never matches a California ZCTA).
    For each ZIP present in the file and each year from the first to the last
    opening year, writes ports opened that year (``level2_installed``,
    ``dc_installed``) and the cumulative totals (``level2_count``,
    ``dc_count``, ``total_count``). ZIPs with no station are absent; Stata
    sets their charger density to 0.
    """
    df = pd.read_csv(afdc_csv, dtype={"ZIP": str}, low_memory=False)
    df = df[df["ZIP"].str.match(r"^\d{5}$", na=False)]
    df["Open Date"] = pd.to_datetime(df["Open Date"], errors="coerce")
    df = df[df["Open Date"].notna()]
    df["Year"] = df["Open Date"].dt.year
    df["level2_installed"] = pd.to_numeric(df["EV Level2 EVSE Num"], errors="coerce").fillna(0)
    df["dc_installed"] = pd.to_numeric(df["EV DC Fast Count"], errors="coerce").fillna(0)

    yearly = df.groupby(["ZIP", "Year"], as_index=False)[["level2_installed", "dc_installed"]].sum()
    grid = pd.MultiIndex.from_product(
        [df["ZIP"].unique(), range(int(df["Year"].min()), int(df["Year"].max()) + 1)],
        names=["ZIP", "Year"],
    ).to_frame(index=False)
    out = grid.merge(yearly, on=["ZIP", "Year"], how="left").fillna(0).sort_values(["ZIP", "Year"])
    out["level2_count"] = out.groupby("ZIP")["level2_installed"].cumsum()
    out["dc_count"] = out.groupby("ZIP")["dc_installed"].cumsum()
    out["total_count"] = out["level2_count"] + out["dc_count"]
    int_cols = ["level2_installed", "dc_installed", "level2_count", "dc_count", "total_count"]
    out[int_cols] = out[int_cols].astype(int)
    out.to_csv(output_path, index=False)
    return out
