"""Light-duty vehicle registrations -> ZIP-year fleet composition.

Input
-----
``vehicle_population_ca_cec_jun25.xlsx`` (sheet ``ZIP``)
    California Energy Commission "Light-Duty Vehicle Population in
    California", built from DMV registrations as of 1 January of each year.
    Columns: data year, fuel type (dashboard grouping), fuel type, ZIP, count.

Output
------
``vehicle_proportion.csv``
    One row per ZIP-year (ZCTAs in ``zcta_ca.gpkg`` only) with, for each fuel
    group in :data:`FUEL_TYPES`:

    * ``count_<fuel>``: registered vehicles
    * ``proportion_<fuel>``: share of *all* registered light-duty vehicles in
      the ZIP (including fuel groups not listed, e.g. hydrogen or "Other")

    plus ``land_area`` (m^2, from the ZCTA file). Fuel groups absent in a
    ZIP-year are filled with 0. The treatment variable in the paper is
    ``log(count_Battery Electric (BEV))``.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

#: Fuel groups kept as separate columns.
FUEL_TYPES = [
    "Battery Electric (BEV)",
    "Plug-in Hybrid (PHEV)",
    "Gasoline Hybrid",
    "Gasoline",
    "Diesel",
]


def load_registrations(xlsx_path: Path) -> pd.DataFrame:
    """Read the CEC ZIP sheet with standardized column names (ZIP as string)."""
    df = pd.read_excel(xlsx_path, sheet_name="ZIP")
    df.columns = ["year", "fuel_type_group_dashboard", "fuel_type", "zip_code", "count"]
    df["zip_code"] = df["zip_code"].astype(str)
    return df


def build_vehicle_panel(
    xlsx_path: Path, zcta_path: Path, output_path: Path, fuel_types: list[str] = FUEL_TYPES
) -> pd.DataFrame:
    """Write the ZIP-year vehicle counts and shares (see module docstring)."""
    reg = load_registrations(xlsx_path)
    zcta = gpd.read_file(zcta_path)[["ZCTA5CE20", "ALAND20"]].rename(
        columns={"ZCTA5CE20": "zip_code", "ALAND20": "land_area"}
    )
    reg = reg[reg["zip_code"].isin(zcta["zip_code"])]

    totals = reg.groupby(["year", "zip_code"])["count"].sum().rename("total_count").reset_index()
    sel = (
        reg[reg["fuel_type_group_dashboard"].isin(fuel_types)]
        .groupby(["year", "zip_code", "fuel_type_group_dashboard"])["count"]
        .sum()
        .reset_index()
        .merge(totals, on=["year", "zip_code"])
    )
    sel["proportion"] = sel["count"] / sel["total_count"]

    wide = sel.pivot_table(
        index=["year", "zip_code"],
        columns="fuel_type_group_dashboard",
        values=["count", "proportion"],
        fill_value=0,
    ).reset_index()
    wide.columns = ["_".join(c).strip() if c[1] else c[0] for c in wide.columns.values]
    wide = wide.merge(zcta.drop_duplicates(), on="zip_code", how="left")
    wide.to_csv(output_path, index=False)
    return wide
