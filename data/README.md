# Data

Everything the pipeline needs except the raw PeMS archive is in this folder.
The paths are set in `.env` (`DATA_DIR`, `GIS_DIR`, `RAW_PEMS_DIR`) and read
by `src/ev_congestion/config.py` and `stata/_setup.do`.

```
data/
├── input/          source files, as downloaded, plus the PeMS station-year aggregates
├── intermediate/   compiled ZIP-year and UA-year panels written by the Python stages
├── gis/            boundaries
└── raw/            (not shipped) default location of the raw PeMS archive
```

Stata's `01_build_data.do` merges `intermediate/*.csv` into the analysis
datasets (`maindata.dta`, `maindata_with_radius.dta`, `maindata_r5_iv.dta`,
`uantddata.dta`). These `.dta` files are rebuilt in seconds and are not
tracked.

## input/

| file | source | content |
|---|---|---|
| `traffic_station_year/congestion_index_station_<year>.csv` (2010–2024) | built by `station_year` from Caltrans PeMS station-hour files | one row per detector station: mean speed (mph) and hourly flow (veh/h) by day type (`weekday`, `normal_weekday`, `weekend`) × time window (`peak`, `non_peak`, `all_day`, `mid_night`), days observed; station latitude, longitude, freeway, direction, district |
| `vehicle_population_ca_cec_jun25.xlsx` | California Energy Commission, Light-Duty Vehicle Population in California (June 2025 release) | vehicle counts by ZIP code, year and fuel type, from DMV registrations |
| `evcs_usdoe_aug25.csv` | U.S. DOE Alternative Fuels Data Center, station locator export (August 2025) | one row per public fuel station; EV ports (Level 2, DC fast), ZIP, open date |
| `transit_uza.csv` | Federal Transit Administration, National Transit Database | unlinked passenger trips per year (2010–2024) by urbanized area |
| `uza_zip_crosswalk.csv` | ZIP code–urbanized area crosswalk (2020 urbanized areas) | assigns each ZIP code to an urbanized area: `ua`, `ua_name`, `zip_code` |
| `zip_county_crosswalk.xlsx`, `zip_county_sub_crosswalk.xlsx` | U.S. Department of Housing and Urban Development, USPS ZIP–county crosswalk | assigns each ZIP code to a county (county × year FE, county trends, leave-one-county-out) |

**Station-year files.** Each `congestion_index_station_<year>.csv` is the
only product of the raw archive. Each file also has one column per
day-type × window, e.g. `weekday_avg_speed_peak`.
- Peak hours are 7–10 am and 4–7 pm; midnight is 2–3 am.
- Speeds are flow-weighted.
- The full definitions are in the docstring of
  `src/ev_congestion/station_year.py`.

## intermediate/

One row per ZIP code (5-digit ZCTA) and year unless noted.

| file | built by | key variables |
|---|---|---|
| `zip_code_congestion_index.csv` | `zip_traffic` | stations inside the ZCTA: `<daytype>_<window>_weighted_speed`, `_avg_hourly_flow`, `_n_stations` |
| `zip_code_congestion_index_radius.csv` | `zip_traffic` | stations within r = 1–15 km of the ZCTA internal point: `weekday_peak_weighted_speed_r<r>`, `weekday_mn_weighted_speed_r<r>`, flows and station counts. **The main outcome is `weekday_peak_weighted_speed_r5`; the placebo is `weekday_mn_weighted_speed_r5`.** |
| `vehicle_proportion.csv` | `vehicles` | `count_<fuel type>` and `proportion_<fuel type>` for BEV, PHEV, hybrid, gasoline, diesel; `land_area` (m²). **The treatment is `log(count_Battery Electric (BEV))`.** |
| `zip_code_acs.csv` | `covariates` (Census API) | ACS 5-year: `hh_median_income`, `population`, `bachelor_degree_population`, `public_transport_commute`, `total_commute`, `travel_time_45_59`/`60_89`/`90_plus`, `total_travel_time`; `geo_code` is the ZCTA |
| `zip_code_acs_income_bins.csv` | `covariates` (Census API) | ACS table B19001 household income brackets; `share_above_150k`, `share_above_200k`, `share_below_75k`. The IV instrument `z_cap_100` (the 2014–2015 share above $100k × post-2016) is built from these brackets in `stata/01_build_data.do` |
| `zip_code_evcs_count.csv` | `covariates` | public charging ports open by year: `level2_count`, `dc_count`, `total_count` |
| `uz_ntd_ev.csv` | `transit` | one row per urbanized area (`ua`) × year: `pt_ridership` (NTD), BEV count, chargers and ACS controls summed over the ZIP codes assigned to the UA (`hh_median_income` is population-weighted) |
| `zip_neighbor_pairs.csv` | `neighbors` | pairs of ZIP codes whose centroids are within 15 km: `zip_code`, `neighbor_zip`, `dist_km` (for the ring treatments) |

`stata/_setup.do` (`prep_vars`) derives the regression controls from these
columns:
- population density;
- bachelor's share;
- transit commute share;
- share of commutes over 45 minutes;
- DC and all charging ports per 1,000 residents.

## gis/

| file | source |
|---|---|
| `zcta_ca.gpkg` | Census TIGER/Line 2020 ZIP Code Tabulation Areas, clipped to California |
| `ca_county/california_county_boundary.geojson` | California county boundaries (Census TIGER/Line) |
| `ca_state/CA_State.shp` | California state boundary (Census TIGER/Line) |

## raw/ (not shipped)

The Caltrans PeMS station-hour files (`station_hour/<year>/`) and station
metadata (`station_metadata/<year>/`). They are about 22 GB of text per year
and require a free PeMS account. They are only needed to rebuild
`input/traffic_station_year/`; see `src/ev_congestion/pems_download.py`.

## License

- Derived data (`intermediate/`, `input/traffic_station_year/`): CC BY 4.0.
- Third-party files in `input/` and `gis/` keep the terms of their original
  publishers.
