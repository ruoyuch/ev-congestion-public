"""Figure 1 maps (BEV counts, peak-hour speed).

Reads ``maindata.dta`` (written by ``stata/01_build_data.do``) and the GIS
layers in ``GIS_DIR`` (``zcta_ca.gpkg``, ``ca_county/california_county_boundary.geojson``,
``ca_state/CA_State.shp``). Writes ``map_bev_growth.png`` and
``map_speed_level.png`` (300 dpi) to ``OUTPUT_DIR``.

Panel (a) shades each ZIP by its 2023 BEV count, with the statewide BEV
total as an inset. Panel (b) shades each ZIP by its mean 2014-2023 weekday
peak-hour speed of stations *within* the ZIP (ZIPs with fewer than 3 years
of data or a mean below 15 mph are left blank), with the statewide mean
across ZIPs as an inset. Fig. A1 (PeMS sensor coverage) is a fixed image,
``docs/map_pems_sensor.png``.
Projection: California Albers (EPSG:3310).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from shapely.geometry import Point

CRS = "EPSG:3310"  # NAD83 / California Albers (equal-area, meters)
plt.rcParams["font.family"] = "DejaVu Sans"

CITIES = {
    "San Francisco": (-122.4194, 37.7749),
    "Sacramento": (-121.4944, 38.5816),
    "Los Angeles": (-118.2437, 34.0522),
    "San Diego": (-117.1611, 32.7157),
}
# per-city label offsets in data meters (dx, dy) and horizontal alignment,
# chosen so labels clear the legend (lower-left) and trend inset (upper-right)
CITY_OFFSETS = {
    "San Francisco": (-15000, 12000, "right"),
    "Sacramento": (-15000, 2000, "right"),
    "Los Angeles": (15000, 10000, "left"),
    "San Diego": (12000, 15000, "left"),
}


# MAP STYLING
bev_bins = [-np.inf, 50, 250, 1000, 2500, np.inf]
bev_labels = ["0-50", "50-250", "250-1,000", "1,000-2,500", ">2,500"]
bev_colors = ["#deebf7", "#9ecae1", "#6baed6", "#3182bd", "#08519c"]

speed_bins = [-np.inf, 45, 55, 60, 65, np.inf]
speed_labels = ["< 45", "45-55", "55-60", "60-65", "> 65"]
# single-hue red ramp: darker red = slower (more congested), lighter = faster
speed_colors = ["#a50f15", "#de2d26", "#fb6a4a", "#fcae91", "#fee5d9"]

NA_COLOR = "#e8e8e8"


# helper functions
def classify(values, bins, labels):
    return pd.cut(values, bins=bins, labels=labels, right=True, include_lowest=True)


# helper functions for map panels
def add_city_labels(ax, city_gdf):
    for _, row in city_gdf.iterrows():
        x, y = row.geometry.x, row.geometry.y
        dx, dy, ha = CITY_OFFSETS[row.label]
        ax.plot(
            x,
            y,
            marker="o",
            markersize=4.5,
            markerfacecolor="black",
            markeredgecolor="white",
            markeredgewidth=0.8,
            zorder=6,
        )
        ax.annotate(
            row.label,
            xy=(x, y),
            xytext=(x + dx, y + dy),
            fontsize=9.5,
            fontweight="bold",
            ha=ha,
            va="center",
            zorder=7,
            path_effects=[pe.withStroke(linewidth=2.5, foreground="white")],
        )


# helper function to add a choropleth map panel
def add_map_panel(ax, gdf, value_col, bins, labels, colors, legend_title, county, state, city_gdf):
    gdf = gdf.copy()
    gdf["_cat"] = classify(gdf[value_col], bins, labels)

    gdf[gdf[value_col].isna()].plot(
        ax=ax, color=NA_COLOR, edgecolor="white", linewidth=0.15, zorder=1
    )
    for lab, col in zip(labels, colors, strict=True):
        sub = gdf[gdf["_cat"] == lab]
        if len(sub):
            sub.plot(ax=ax, color=col, edgecolor="white", linewidth=0.15, zorder=2)

    county.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#8a8a8a",
        linewidth=0.35,
        linestyle=(0, (1, 1)),
        zorder=3,
    )
    state.boundary.plot(ax=ax, color="black", linewidth=1.2, zorder=4)

    add_city_labels(ax, city_gdf)

    ax.set_axis_off()
    minx, miny, maxx, maxy = state.total_bounds
    ax.set_xlim(minx - 20000, maxx + 20000)
    ax.set_ylim(miny - 20000, maxy + 40000)
    ax.set_aspect("equal")

    # legend, lower-left corner
    handles = [Rectangle((0, 0), 1, 1, facecolor=c, edgecolor="none") for c in colors]
    handles.append(Rectangle((0, 0), 1, 1, facecolor=NA_COLOR, edgecolor="none"))
    handles.append(Line2D([0], [0], color="#8a8a8a", linewidth=0.9, linestyle=(0, (1, 1))))
    leg = ax.legend(
        handles,
        labels + ["No data", "County boundary"],
        title=legend_title,
        loc="lower left",
        bbox_to_anchor=(0.0, 0.0),
        frameon=False,
        fontsize=10,
        title_fontsize=11.5,
        handlelength=1.2,
        handleheight=1.2,
        labelspacing=0.35,
        borderaxespad=0.4,
    )
    leg._legend_box.align = "left"

    # scale bar, to the right of the legend
    fig = ax.get_figure()
    fig.canvas.draw()
    bbox_data = leg.get_window_extent(renderer=fig.canvas.get_renderer()).transformed(
        ax.transData.inverted()
    )

    bar_len = 100_000  # 100 km
    gap = 20000
    bx0 = bbox_data.x1 + gap
    by0 = bbox_data.y0 + 8000
    ax.plot([bx0, bx0 + bar_len], [by0, by0], color="black", linewidth=2, solid_capstyle="butt")
    ax.plot([bx0, bx0], [by0 - 8000, by0 + 8000], color="black", linewidth=1.2)
    ax.plot([bx0 + bar_len, bx0 + bar_len], [by0 - 8000, by0 + 8000], color="black", linewidth=1.2)
    ax.text(bx0 + bar_len / 2, by0 - 25000, "100 km", ha="center", va="top", fontsize=10)

    return ax


# helper function to add a trend inset panel
def add_trend_inset(map_ax, series, ylabel, color, bounds, ylim=None):
    ax = map_ax.inset_axes(bounds)  # Create small axes at specified position
    years = series.index.astype(int)  # Extract years from series index
    ax.plot(
        years, series.values, marker="o", markersize=3, linewidth=1.3, color=color
    )  # Plot line with markers
    ax.set_xticks(years)  # Set x-axis ticks to all years
    ax.set_xticklabels(
        [str(y) for y in years], fontsize=8, rotation=45, ha="right"
    )  # Full 4-digit years, angled
    ax.set_xlabel("Year", fontsize=9, labelpad=1)
    ax.set_ylabel(ylabel, fontsize=9, labelpad=1)
    ax.tick_params(axis="y", labelsize=8, length=2, pad=1)
    ax.tick_params(axis="x", length=2, pad=1)
    if ylim is not None:
        ax.set_ylim(*ylim)  # Optional y-axis limits
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)  # Remove top/right borders
    ax.grid(axis="y", color="#dddddd", linewidth=0.5, zorder=0)  # Add light horizontal grid
    ax.set_facecolor("none")  # Make background transparent
    return ax


def make_maps(maindata_dta: Path, gis_dir: Path, output_dir: Path) -> list[Path]:
    """Draw the map figures and return the written file paths."""
    gis_dir, output_dir = Path(gis_dir), Path(output_dir)
    df = pd.read_stata(maindata_dta)
    df = df[(df.year >= 2014) & (df.year <= 2023)].copy()
    df["zip_code"] = df["zip_code"].astype(int)
    bev = df.pivot(index="zip_code", columns="year", values="count_batteryelectricbev")
    spd = df.pivot(index="zip_code", columns="year", values="weekday_peak_weighted_speed")

    zip_bev_2023 = bev[2023].rename("bev_2023")
    n_years, avg_speed = spd.notna().sum(axis=1), spd.mean(axis=1)
    zip_avg_speed = avg_speed[(n_years >= 3) & (avg_speed >= 15)].rename("avg_speed")
    state_bev_trend = bev.sum(axis=0) / 1000  # thousands of BEVs
    state_speed_trend = spd.mean(axis=0)  # mph, simple mean across ZIPs

    zcta = gpd.read_file(gis_dir / "zcta_ca.gpkg").to_crs(CRS)
    zcta["zip_code"] = zcta["ZCTA5CE20"].astype(int)
    county = gpd.read_file(gis_dir / "ca_county" / "california_county_boundary.geojson").to_crs(CRS)
    state = gpd.read_file(gis_dir / "ca_state" / "CA_State.shp").to_crs(CRS)
    city_gdf = gpd.GeoDataFrame(
        {"label": list(CITIES)}, geometry=[Point(v) for v in CITIES.values()], crs="EPSG:4326"
    ).to_crs(CRS)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []

    fig, ax = plt.subplots(figsize=(5.8, 5.8))
    add_map_panel(
        ax,
        zcta.merge(zip_bev_2023, on="zip_code", how="left"),
        "bev_2023",
        bev_bins,
        bev_labels,
        bev_colors,
        "BEV count (2023)",
        county,
        state,
        city_gdf,
    )
    add_trend_inset(
        ax,
        state_bev_trend,
        "State total BEV\ncount (thousands)",
        "#08519c",
        bounds=[0.58, 0.65, 0.37, 0.30],
    )
    fig.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.02)
    written.append(output_dir / "map_bev_growth.png")
    fig.savefig(written[-1], dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.8, 5.8))
    add_map_panel(
        ax,
        zcta.merge(zip_avg_speed, on="zip_code", how="left"),
        "avg_speed",
        speed_bins,
        speed_labels,
        speed_colors,
        "Speed (mph)",
        county,
        state,
        city_gdf,
    )
    add_trend_inset(
        ax,
        state_speed_trend,
        "Avg. freeway peak-hour\nspeed (mph)",
        "#a50f15",
        bounds=[0.55, 0.65, 0.38, 0.30],
        ylim=(54.5, 60.5),
    )
    fig.subplots_adjust(left=0.01, right=0.99, top=0.98, bottom=0.02)
    written.append(output_dir / "map_speed_level.png")
    fig.savefig(written[-1], dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return written
