"""Station-year traffic -> ZIP-code (ZCTA) year traffic.

Two aggregations are produced from the station-year files written by
:mod:`ev_congestion.station_year`:

``zip_code_congestion_index.csv`` (:func:`build_zip_within`)
    Stations located *inside* each ZCTA polygon. For each speed/flow pair in
    :data:`WITHIN_VARIABLES`::

        <prefix>weighted_speed   flow-weighted mean speed of those stations (mph)
        <prefix>avg_hourly_flow  unweighted mean hourly flow (veh/h)
        <prefix>n_stations       stations with both values non-missing

``zip_code_congestion_index_radius.csv`` (:func:`build_zip_radius`)
    Stations within ``r`` km (great-circle) of the ZCTA internal point, for
    r = 1, ..., 15 km. Wide format: ``<prefix>weighted_speed_r5`` etc. **The
    main specification uses the r = 5 km weekday peak speed**
    (``weekday_peak_weighted_speed_r5``) and its midnight placebo
    (``weekday_mn_weighted_speed_r5``).

A ZCTA with no qualifying station, or whose stations report zero total
flow, gets NaN speed and flow.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0
RADII_KM = list(range(1, 16))


def _varset(daytype: str, window: str, prefix: str | None = None) -> dict:
    return {
        "speed_var": f"{daytype}_avg_speed_{window}",
        "flow_var": f"{daytype}_avg_hourly_flow_{window}",
        "prefix": prefix or f"{daytype}_{window}_",
    }


#: All 12 day-type x window combinations, aggregated within ZIP polygons.
WITHIN_VARIABLES = [
    _varset(d, w)
    for d in ("weekday", "normal_weekday", "weekend")
    for w in ("peak", "non_peak", "all_day", "mid_night")
]

#: Variables aggregated by radius: weekday peak (outcome) and midnight (placebo).
RADIUS_VARIABLES = [_varset("weekday", "peak"), _varset("weekday", "mid_night", "weekday_mn_")]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_zcta(zcta_path: Path) -> gpd.GeoDataFrame:
    """ZCTA polygons with internal-point coordinates.

    Returns columns ``zip_code`` (5-character string), ``lat``, ``lon``
    (Census internal point, used as the ZIP "centroid") and ``geometry``.
    """
    gdf = gpd.read_file(zcta_path)[["ZCTA5CE20", "INTPTLAT20", "INTPTLON20", "geometry"]]
    gdf = gdf.rename(columns={"ZCTA5CE20": "zip_code", "INTPTLAT20": "lat", "INTPTLON20": "lon"})
    gdf[["lat", "lon"]] = gdf[["lat", "lon"]].astype(float)
    return gdf


def load_station_year(station_year_dir: Path, year: int) -> pd.DataFrame:
    """Read one station-year file and drop rows without valid coordinates.

    Coordinates and all metric columns are coerced to numeric; this also
    removes the repeated header lines present in station-year files built by
    the original (pre-2026) script, which wrote one header per district.
    """
    path = Path(station_year_dir) / f"congestion_index_station_{year}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, low_memory=False)
    for c in ("Latitude", "Longitude"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)


def _weighted(speed: np.ndarray, flow: np.ndarray) -> tuple[float, float, int]:
    ok = ~np.isnan(speed) & ~np.isnan(flow)
    speed, flow = speed[ok], flow[ok]
    if len(speed) and flow.sum() > 0:
        return float(np.average(speed, weights=flow)), float(flow.mean()), len(speed)
    return np.nan, np.nan, len(speed)


# ---------------------------------------------------------------------------
# Within-ZIP aggregation
# ---------------------------------------------------------------------------
def summarize_within(
    stations: pd.DataFrame, zcta: gpd.GeoDataFrame, speed_var: str, flow_var: str, prefix: str
) -> pd.DataFrame:
    """Aggregate stations that fall inside each ZCTA polygon (one year)."""
    pts = gpd.GeoDataFrame(
        stations,
        crs="EPSG:4326",
        geometry=gpd.points_from_xy(stations["Longitude"], stations["Latitude"]),
    )
    joined = gpd.sjoin(
        pts, zcta.to_crs(pts.crs)[["zip_code", "geometry"]], how="left", predicate="within"
    )
    rows = []
    for z, g in joined.groupby("zip_code"):
        s, w, n = _weighted(
            pd.to_numeric(g[speed_var], errors="coerce").to_numpy(float),
            pd.to_numeric(g[flow_var], errors="coerce").to_numpy(float),
        )
        rows.append(
            {
                "zip_code": z,
                f"{prefix}weighted_speed": s,
                f"{prefix}avg_hourly_flow": w,
                f"{prefix}n_stations": n,
            }
        )
    return pd.DataFrame(rows)


def build_zip_within(
    station_year_dir: Path,
    zcta_path: Path,
    output_path: Path,
    years: range,
    variables: list[dict] = WITHIN_VARIABLES,
) -> pd.DataFrame:
    """Write the ZIP-year panel of within-polygon traffic (all ZCTAs x ``years``)."""
    zcta = load_zcta(zcta_path)
    out = []
    for year in years:
        stations = load_station_year(station_year_dir, year)
        panel = zcta[["zip_code"]].copy()
        for v in variables:
            panel = panel.merge(summarize_within(stations, zcta, **v), on="zip_code", how="left")
        panel["year"] = year
        out.append(panel)
        log.info("within-ZIP traffic: %s done", year)
    df = pd.concat(out, ignore_index=True)
    df.to_csv(output_path, index=False)
    return df


# ---------------------------------------------------------------------------
# Radius aggregation
# ---------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (inputs in degrees; broadcasts like numpy)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def summarize_radius(
    stations: pd.DataFrame,
    zcta: pd.DataFrame,
    speed_var: str,
    flow_var: str,
    prefix: str,
    radii_km: list[int] = RADII_KM,
) -> pd.DataFrame:
    """Aggregate stations within each radius of every ZCTA internal point (one year).

    Returns one row per ZCTA with ``<prefix>weighted_speed_r<k>``,
    ``<prefix>avg_flow_r<k>`` and ``<prefix>n_stations_r<k>`` for each radius.
    """
    s_lat = stations["Latitude"].to_numpy(float)
    s_lon = stations["Longitude"].to_numpy(float)
    speed = pd.to_numeric(stations[speed_var], errors="coerce").to_numpy(float)
    flow = pd.to_numeric(stations[flow_var], errors="coerce").to_numpy(float)
    rows = []
    for z, zlat, zlon in zcta[["zip_code", "lat", "lon"]].itertuples(index=False):
        dist = haversine_km(zlat, zlon, s_lat, s_lon)
        row = {"zip_code": z}
        for r in radii_km:
            within = dist <= r
            s, w, n = _weighted(speed[within], flow[within])
            row |= {
                f"{prefix}weighted_speed_r{r}": s,
                f"{prefix}avg_flow_r{r}": w,
                f"{prefix}n_stations_r{r}": n,
            }
        rows.append(row)
    df = pd.DataFrame(rows)
    # column order: all speeds, all flows, all counts (matches the published file)
    order = ["zip_code"] + [
        f"{prefix}{m}_r{r}"
        for m in ("weighted_speed", "avg_flow", "n_stations")
        for r in sorted(radii_km, key=str)
    ]
    return df[order]


def build_zip_radius(
    station_year_dir: Path,
    zcta_path: Path,
    output_path: Path,
    years: range,
    variables: list[dict] = RADIUS_VARIABLES,
    radii_km: list[int] = RADII_KM,
) -> pd.DataFrame:
    """Write the wide ZIP-year panel of radius-based traffic."""
    zcta = load_zcta(zcta_path)
    out = []
    for year in years:
        stations = load_station_year(station_year_dir, year)
        panel = zcta[["zip_code"]].copy()
        panel["year"] = year
        for v in variables:
            panel = panel.merge(
                summarize_radius(stations, zcta, radii_km=radii_km, **v), on="zip_code", how="left"
            )
        out.append(panel)
        log.info("radius traffic: %s done", year)
    df = pd.concat(out, ignore_index=True)
    df.to_csv(output_path, index=False)
    return df
