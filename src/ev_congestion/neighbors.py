"""ZIP-to-ZIP neighbor pairs for the ring (donut) specifications.

Output ``zip_neighbor_pairs.csv`` has one row per *directed* pair
(``zip_code``, ``neighbor_zip``) of distinct ZCTAs whose internal points are
within ``max_km`` of each other, with ``dist_km``: the planar distance in
California Albers (EPSG:3310), to 3 decimals. Stata uses it to sum BEV counts
of ZIPs located 5-10 km and 5-15 km away (Section 9 of the do-files).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


def build_neighbor_pairs(zcta_path: Path, output_path: Path, max_km: float = 15.0) -> pd.DataFrame:
    """Write all directed ZCTA pairs within ``max_km`` (see module docstring)."""
    z = gpd.read_file(zcta_path)[["ZCTA5CE20", "INTPTLAT20", "INTPTLON20"]].rename(
        columns={"ZCTA5CE20": "zip_code"}
    )
    z["zip_code"] = z["zip_code"].astype(int)
    z[["INTPTLAT20", "INTPTLON20"]] = z[["INTPTLAT20", "INTPTLON20"]].apply(
        pd.to_numeric, errors="coerce"
    )
    z = z.dropna(subset=["INTPTLAT20", "INTPTLON20"]).drop_duplicates("zip_code")

    pts = gpd.GeoDataFrame(
        z[["zip_code"]],
        crs="EPSG:4326",
        geometry=gpd.points_from_xy(z["INTPTLON20"], z["INTPTLAT20"]),
    ).to_crs("EPSG:3310")
    xy = np.column_stack([pts.geometry.x, pts.geometry.y])
    ids = pts["zip_code"].to_numpy()

    pairs = cKDTree(xy).query_pairs(r=max_km * 1000, output_type="ndarray")
    d = np.linalg.norm(xy[pairs[:, 0]] - xy[pairs[:, 1]], axis=1) / 1000
    df = pd.DataFrame(
        {
            "zip_code": np.concatenate([ids[pairs[:, 0]], ids[pairs[:, 1]]]),
            "neighbor_zip": np.concatenate([ids[pairs[:, 1]], ids[pairs[:, 0]]]),
            "dist_km": np.concatenate([d, d]),
        }
    ).sort_values(["zip_code", "dist_km"])
    df.to_csv(output_path, index=False, float_format="%.3f")
    return df
