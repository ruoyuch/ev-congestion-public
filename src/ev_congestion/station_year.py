"""Raw PeMS station-hour files -> one row per detector station per year.

Input
-----
``<RAW_PEMS_DIR>/station_hour/<year>/dNN_text_station_hour_<year>_<MM>.txt``
    Caltrans PeMS hourly station aggregates (comma-separated, no header;
    column definitions in ``station_hour/README.txt``). One file per district
    per month.
``<RAW_PEMS_DIR>/station_metadata/<year>/dNN_text_meta_<YYYY_MM_DD>.txt``
    Station metadata snapshots (tab-separated, with header): location,
    freeway, direction and lane type of every station.

Output
------
``<INPUT_DIR>/traffic_station_year/congestion_index_station_<year>.csv``
    One row per station, with average speed (mph) and average hourly flow
    (vehicles/hour) for 4 time-of-day windows x 3 day types:

    ==============  ==========================================================
    time window     definition (hour = start of the hourly PeMS interval)
    ==============  ==========================================================
    ``peak``        07-10h and 16-19h (hours 7, 8, 9, 16, 17, 18)
    ``non_peak``    every other hour of the day
    ``all_day``     all 24 hours
    ``mid_night``   02-03h (hour 2), used as the placebo outcome
    ==============  ==========================================================

    Day types: ``weekday`` (Mon-Fri), ``normal_weekday`` (Tue-Thu) and
    ``weekend`` (Sat-Sun). Holidays are not removed.

Aggregation
-----------
1. Keep mainline-type lanes: mainline (ML), HOV (HV), collector/distributor
   (CD) and conventional highway (CH). Ramps and connectors are dropped.
2. Station-day: speed in a window is the flow-weighted mean of the hourly
   speeds (``sum(speed * flow) / sum(flow)``); flow is total flow divided by
   the number of distinct hours observed. The midnight window has a single
   hour, so its speed and flow are the hourly values.
3. Station-year: simple mean of the station-day values over the days of each
   day type; ``<daytype>_days`` counts those days.
4. Attach coordinates and road attributes from the station metadata of the
   same year (falling back up to 5 earlier years when a year has no file).

The paper uses ``weekday_avg_speed_peak`` (outcome) and
``weekday_avg_speed_mid_night`` (placebo); the other columns support
robustness checks.

Runtime: about 20-25 GB of text per year; memory peaks with the largest
district (D4, Bay Area). Only the 8 columns used are parsed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

#: Caltrans districts covered by PeMS with usable detector data.
DISTRICTS = ["d03", "d04", "d05", "d06", "d07", "d08", "d10", "d11", "d12"]

#: Lane types kept: mainline, HOV, collector/distributor, conventional highway.
LANE_TYPES = ["HV", "ML", "CD", "CH"]

#: Hours (start of interval) treated as peak: 7-10 am and 4-7 pm.
PEAK_HOURS = [7, 8, 9, 16, 17, 18]

#: Hour treated as "midnight" (the low-demand placebo window): 2-3 am.
MIDNIGHT_HOUR = 2

#: Positional columns of the station_hour text files (first 12 of 42).
_STATION_HOUR_COLUMNS = {
    0: "timestamp",
    1: "station_id",
    2: "district",
    3: "route",
    4: "direction",
    5: "lane_type",
    6: "station_length",
    7: "total_sample",
    8: "observed_percentage",
    9: "total_flow",
    10: "avg_occupancy",
    11: "avg_speed",
}
_USECOLS = [0, 1, 3, 4, 5, 6, 9, 11]

WINDOWS = ["peak", "non_peak", "all_day", "mid_night"]
DAY_TYPES = ["weekday", "normal_weekday", "weekend"]


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------
def list_files(directory: Path, year: int, district: str, suffix: str = ".txt") -> list[Path]:
    """Return ``<directory>/<year>/<district>*<suffix>`` files, sorted by name.

    Returns an empty list when the year folder does not exist.
    """
    year_dir = Path(directory) / str(year)
    if not year_dir.is_dir():
        return []
    return sorted(
        p for p in year_dir.iterdir() if p.name.startswith(district) and p.name.endswith(suffix)
    )


# ---------------------------------------------------------------------------
# Station metadata
# ---------------------------------------------------------------------------
def read_station_metadata(
    directory: Path, year: int, district: str, year_back: int = 5
) -> pd.DataFrame:
    """Stack every metadata snapshot of ``district`` in ``year``.

    PeMS publishes a new metadata file whenever the detector inventory
    changes, so a year can hold several snapshots. If ``year`` has none, the
    most recent of the previous ``year_back`` years is used instead.
    """
    for y in range(year, year - year_back - 1, -1):
        files = list_files(directory, y, district)
        if files:
            if y != year:
                log.warning("No %s metadata for %s; using %s", district, year, y)
            break
    else:
        log.warning("No %s metadata for %s or the %d years before", district, year, year_back)
        return pd.DataFrame()

    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f, sep="\t", on_bad_lines="skip", engine="python"))
        except Exception as err:  # malformed snapshot: skip, keep the rest
            log.warning("Skipping metadata file %s (%s)", f.name, err)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def clean_station_metadata(meta: pd.DataFrame) -> pd.DataFrame:
    """One row per station ID with coordinates and road attributes.

    * Keeps lane types in :data:`LANE_TYPES`.
    * A station whose coordinates differ across snapshots gets the mean
      location and ``is_averaged = True``.
    * A station whose lane type differs across snapshots is dropped, since it
      cannot be classified.

    Returns columns ``ID, Latitude, Longitude, Type, Fwy, Dir, District,
    is_averaged``.
    """
    cols = ["ID", "Latitude", "Longitude", "Type", "Fwy", "Dir", "District"]
    df = meta[cols]
    df = df[df["Type"].isin(LANE_TYPES)].copy()
    df["is_averaged"] = False

    dup = df[df.duplicated(subset=["ID"], keep=False)]
    to_remove, averaged = set(), set()
    for sid, g in dup.groupby("ID"):
        if g["Latitude"].nunique() > 1 or g["Longitude"].nunique() > 1:
            df.loc[df["ID"] == sid, ["Latitude", "Longitude"]] = [
                g["Latitude"].mean(),
                g["Longitude"].mean(),
            ]
            df.loc[df["ID"] == sid, "is_averaged"] = True
            averaged.add(sid)
        if g["Type"].nunique() > 1:
            to_remove.add(sid)

    df = df[~df["ID"].isin(to_remove)].drop_duplicates(subset=["ID"])
    log.info(
        "Metadata: %d IDs, %d with averaged coordinates, %d dropped (lane type changed)",
        meta["ID"].nunique(),
        len(averaged),
        len(to_remove),
    )
    return df


# ---------------------------------------------------------------------------
# Station-hour data
# ---------------------------------------------------------------------------
def read_station_hour(directory: Path, year: int, district: str) -> pd.DataFrame:
    """Read all monthly station_hour files of one district-year.

    Only the columns needed downstream are parsed (timestamp, station,
    route, direction, lane type, station length, total flow, average speed).
    """
    frames = []
    for f in list_files(directory, year, district):
        frames.append(
            pd.read_csv(
                f,
                header=None,
                usecols=_USECOLS,
                names=[_STATION_HOUR_COLUMNS[i] for i in _USECOLS],
                dtype={"lane_type": "category", "direction": "category"},
            )
        )
        log.debug("read %s", f.name)
    if not frames:
        return pd.DataFrame(columns=[_STATION_HOUR_COLUMNS[i] for i in _USECOLS])
    return pd.concat(frames, ignore_index=True)


def clean_station_hour(df: pd.DataFrame) -> pd.DataFrame:
    """Keep mainline-type lanes and add calendar fields.

    Adds ``date``, ``hour_of_day``, ``is_weekday`` (Mon-Fri) and
    ``is_normal_weekday`` (Tue-Thu).
    """
    df = df[df["lane_type"].isin(LANE_TYPES)].copy()
    ts = pd.to_datetime(df["timestamp"], format="%m/%d/%Y %H:%M:%S")
    df["date"] = ts.dt.normalize()
    df["hour_of_day"] = ts.dt.hour
    dow = ts.dt.dayofweek
    df["is_weekday"] = dow < 5
    df["is_normal_weekday"] = dow.isin([1, 2, 3])
    return df.drop(columns="timestamp")


def station_day_metrics(
    df: pd.DataFrame, peak_hours: list[int] = PEAK_HOURS, midnight_hour: int = MIDNIGHT_HOUR
) -> pd.DataFrame:
    """Station-day speed and flow for each time window.

    For ``peak``, ``non_peak`` and ``all_day``::

        avg_speed_<w>        = sum(speed * flow) / sum(flow)     over hours in w
        avg_hourly_flow_<w>  = sum(flow) / (# distinct hours in w)

    Missing speeds or flows are skipped in the sums (so a day whose hours in
    ``w`` all lack data gets speed NaN and flow 0). For ``mid_night`` both are
    the plain means over the rows at ``midnight_hour``. A station-day with no
    rows in a window gets NaN for that window.
    """
    key = ["station_id", "date"]
    df = df[
        key + ["avg_speed", "total_flow", "hour_of_day", "is_weekday", "is_normal_weekday"]
    ].copy()
    df["speed_x_flow"] = df["avg_speed"] * df["total_flow"]
    is_peak = df["hour_of_day"].isin(peak_hours)

    out = df.groupby(key, sort=True)[["is_weekday", "is_normal_weekday"]].first()

    def weighted(sub: pd.DataFrame, w: str) -> None:
        g = sub.groupby(key, sort=True)
        num, flow, hours = (
            g["speed_x_flow"].sum(),
            g["total_flow"].sum(),
            g["hour_of_day"].nunique(),
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"avg_speed_{w}"] = num / flow
        out[f"avg_hourly_flow_{w}"] = flow / hours

    weighted(df[is_peak], "peak")
    weighted(df[~is_peak], "non_peak")
    weighted(df, "all_day")

    g = df[df["hour_of_day"] == midnight_hour].groupby(key, sort=True)
    out["avg_speed_mid_night"] = g["avg_speed"].mean()
    out["avg_hourly_flow_mid_night"] = g["total_flow"].mean()
    return out.reset_index()


def station_year_metrics(daily: pd.DataFrame) -> pd.DataFrame:
    """Average station-day metrics over the days of each day type.

    Returns one row per station with columns
    ``<daytype>_avg_speed_<window>``, ``<daytype>_avg_hourly_flow_<window>``
    and ``<daytype>_days`` for every day type in :data:`DAY_TYPES`.
    """
    metrics = [f"{m}_{w}" for w in WINDOWS for m in ("avg_speed", "avg_hourly_flow")]
    masks = {
        "weekday": daily["is_weekday"].astype(bool),
        "normal_weekday": daily["is_normal_weekday"].astype(bool),
        "weekend": ~daily["is_weekday"].astype(bool),
    }
    stations = pd.Index(daily["station_id"].unique(), name="station_id").sort_values()
    parts = []
    for name, mask in masks.items():
        g = daily[mask].groupby("station_id")
        part = g[metrics].mean().add_prefix(f"{name}_").reindex(stations)
        part[f"{name}_days"] = g.size().reindex(stations, fill_value=0)
        parts.append(part)
    return pd.concat(parts, axis=1).reset_index()


def merge_metadata(station_year: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Inner-join station metrics to cleaned metadata on station ID."""
    merged = station_year.merge(meta, left_on="station_id", right_on="ID", how="inner")
    log.info(
        "Matched %d/%d stations to metadata (%.1f%%)",
        len(merged),
        len(station_year),
        100 * len(merged) / max(len(station_year), 1),
    )
    return merged


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def build_station_year(
    year: int,
    station_hour_dir: Path,
    station_metadata_dir: Path,
    output_dir: Path,
    districts: list[str] = DISTRICTS,
    overwrite: bool = False,
) -> Path:
    """Build ``congestion_index_station_<year>.csv`` for all ``districts``.

    The file is written once at the end (a single header), so an interrupted
    run never leaves a partial file behind. Existing files are skipped unless
    ``overwrite=True``.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"congestion_index_station_{year}.csv"
    if out_path.exists() and not overwrite:
        log.info("%s exists; skipping (overwrite=False)", out_path.name)
        return out_path

    results = []
    for district in districts:
        hourly = read_station_hour(station_hour_dir, year, district)
        if hourly.empty:
            log.warning("No station_hour files for %s %s", district, year)
            continue
        log.info("%s %s: %d station-hours", year, district, len(hourly))
        hourly = clean_station_hour(hourly)
        station_year = station_year_metrics(station_day_metrics(hourly))
        del hourly
        meta = clean_station_metadata(read_station_metadata(station_metadata_dir, year, district))
        results.append(merge_metadata(station_year, meta))

    out = pd.concat(results, ignore_index=True)
    tmp = out_path.with_suffix(".csv.tmp")
    out.to_csv(tmp, index=False)
    tmp.replace(out_path)
    log.info("Wrote %s (%d stations)", out_path, len(out))
    return out_path
