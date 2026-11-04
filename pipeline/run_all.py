#!/usr/bin/env python
"""Run the full replication pipeline, from raw data to tables and figures.

    uv run pipeline/run_all.py                     # every stage that is not up to date
    uv run pipeline/run_all.py --list              # show stages and their status
    uv run pipeline/run_all.py --from zip_traffic  # rerun from a stage onward
    uv run pipeline/run_all.py --only stata        # a single stage
    uv run pipeline/run_all.py --force             # rebuild even if outputs exist

Paths and parameters come from ``.env`` (copy ``.env.example``). A stage is
skipped when all of its outputs already exist, unless it is named with
``--only``/``--from`` or ``--force`` is given. Each run appends to
``output/logs/run_all.log``, with the runtime of each stage.

Stages, in order (inputs -> outputs):

=================  ================================================  ==============================================
stage              does                                              writes
=================  ================================================  ==============================================
download_pems      raw PeMS files (manual: needs a PeMS login)       RAW_PEMS_DIR/station_hour, station_metadata
station_year       hourly detector data -> station-year speed/flow   input/traffic_station_year/*.csv
zip_traffic        stations -> ZIP-year (within ZIP, 1-15 km radii)  zip_code_congestion_index[_radius].csv
vehicles           DMV/CEC registrations -> ZIP-year fleet           vehicle_proportion.csv
covariates         ACS (Census API), chargers                        zip_code_acs*.csv, zip_code_evcs_count.csv, ...
transit            ZIP panel -> urbanized-area panel + NTD           uz_ntd_ev.csv
neighbors          ZIP pairs within 15 km (ring specifications)      zip_neighbor_pairs.csv
stata              merge + all regressions (stata/00_master.do)      output/tables/*.tex, output/figures/*.pdf
maps               Fig. 1 and Fig. A1 maps                           output/figures/map_*.png
=================  ================================================  ==============================================

``download_pems`` and the ACS downloads are never run
automatically; their outputs are shipped with the replication package (or
the raw PeMS archive must be present). Use ``--only download_pems`` or
``--only covariates --download`` to fetch them again.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ev_congestion.config import CFG, REPO_ROOT

#: Years of the ZIP-radius panel. Stata keeps 2014-2023; 2024 is built for
#: the leads/lags and future updates.
YEARS = range(2014, 2025)
#: Years of station-year files and of the within-ZIP panel, which is built
#: from 2010 although the regressions keep 2014-2023.
STATION_YEARS = range(2010, 2025)

log = logging.getLogger("run_all")


@dataclass
class Stage:
    name: str
    run: Callable[[argparse.Namespace], None]
    outputs: Callable[[], list[Path]]
    auto: bool = True  # run when outputs are missing (False = only on request)
    doc: str = ""


# ---------------------------------------------------------------------------
# Stage implementations (imports are local so --list stays fast)
# ---------------------------------------------------------------------------
def _download_pems(args):
    from ev_congestion import pems_download

    pems_download.main(["--years", str(STATION_YEARS[0]), str(STATION_YEARS[-1])])
    pems_download.main(
        ["--mode", "meta", "--years", str(STATION_YEARS[0] - 5), str(STATION_YEARS[-1])]
    )


def _station_year(args):
    from ev_congestion.station_year import build_station_year

    if not CFG.station_hour_dir.is_dir():
        raise SystemExit(
            f"Raw PeMS data not found at {CFG.raw_pems_dir} (set RAW_PEMS_DIR in .env)"
        )
    years = range(args.first_year, args.last_year + 1) if args.first_year else STATION_YEARS
    for y in years:
        t = time.time()
        build_station_year(
            y,
            CFG.station_hour_dir,
            CFG.station_metadata_dir,
            args.station_year_out or CFG.station_year_dir,
            overwrite=args.force,
        )
        log.info("station_year %s: %.1f min", y, (time.time() - t) / 60)


def _zip_traffic(args):
    from ev_congestion import zip_traffic as zt

    src = args.station_year_out or CFG.station_year_dir
    zt.build_zip_within(
        src, CFG.zcta_path, CFG.intermediate_dir / "zip_code_congestion_index.csv", STATION_YEARS
    )
    zt.build_zip_radius(
        src, CFG.zcta_path, CFG.intermediate_dir / "zip_code_congestion_index_radius.csv", YEARS
    )


def _vehicles(args):
    from ev_congestion.vehicles import build_vehicle_panel

    build_vehicle_panel(
        CFG.input_dir / "vehicle_population_ca_cec_jun25.xlsx",
        CFG.zcta_path,
        CFG.intermediate_dir / "vehicle_proportion.csv",
    )


def _covariates(args):
    from ev_congestion import covariates as cv

    out = CFG.intermediate_dir
    cv.build_charger_counts(CFG.input_dir / "evcs_usdoe_aug25.csv", out / "zip_code_evcs_count.csv")
    if args.download:
        if not CFG.census_api_key:
            raise SystemExit("Set CENSUS_API_KEY in .env to download ACS data")
        cv.download_acs_controls(CFG.census_api_key, out / "zip_code_acs.csv")
        cv.download_income_bins(CFG.census_api_key, out / "zip_code_acs_income_bins.csv")
    else:
        for f in ("zip_code_acs.csv", "zip_code_acs_income_bins.csv"):
            if not (out / f).exists():
                raise SystemExit(f"{f} missing: rerun with --only covariates --download")


def _transit(args):
    from ev_congestion.transit import build_uza_panel

    build_uza_panel(CFG.input_dir, CFG.intermediate_dir, CFG.intermediate_dir / "uz_ntd_ev.csv")


def _neighbors(args):
    from ev_congestion.neighbors import build_neighbor_pairs

    build_neighbor_pairs(CFG.zcta_path, CFG.intermediate_dir / "zip_neighbor_pairs.csv")


def _stata(args):
    steps = args.stata_steps or []
    cmd = [CFG.stata_bin, "-b", "do", "00_master.do", *steps]
    log.info("running %s in stata/", " ".join(cmd))
    subprocess.run(cmd, cwd=REPO_ROOT / "stata", check=True)
    logfile = REPO_ROOT / "stata" / "00_master.log"
    text = logfile.read_text(errors="replace") if logfile.exists() else ""
    # Stata batch mode exits 0 even on error; detect r(###) at the end of the log
    tail = text[-3000:]
    if "All steps finished" not in tail:
        raise SystemExit(f"Stata stopped with an error; see {logfile}\n...{tail[-800:]}")


def _maps(args):
    from ev_congestion.maps import make_maps

    make_maps(CFG.intermediate_dir / "maindata.dta", CFG.gis_dir, CFG.figures_dir)


INTER = CFG.intermediate_dir
STAGES = [
    Stage(
        "download_pems",
        _download_pems,
        lambda: [CFG.station_hour_dir, CFG.station_metadata_dir],
        auto=False,
    ),
    Stage(
        "station_year",
        _station_year,
        lambda: [CFG.station_year_dir / f"congestion_index_station_{y}.csv" for y in STATION_YEARS],
    ),
    Stage(
        "zip_traffic",
        _zip_traffic,
        lambda: [
            INTER / "zip_code_congestion_index.csv",
            INTER / "zip_code_congestion_index_radius.csv",
        ],
    ),
    Stage("vehicles", _vehicles, lambda: [INTER / "vehicle_proportion.csv"]),
    Stage(
        "covariates",
        _covariates,
        lambda: [
            INTER / f
            for f in ("zip_code_acs.csv", "zip_code_acs_income_bins.csv", "zip_code_evcs_count.csv")
        ],
    ),
    Stage("transit", _transit, lambda: [INTER / "uz_ntd_ev.csv"]),
    Stage("neighbors", _neighbors, lambda: [INTER / "zip_neighbor_pairs.csv"]),
    Stage(
        "stata",
        _stata,
        lambda: [
            CFG.tables_dir / "twfe_speed_regs.tex",
            CFG.tables_dir / "twfe_speed_regs_robust_peak.tex",
        ],
    ),
    Stage(
        "maps",
        _maps,
        lambda: [CFG.figures_dir / f"map_{m}.png" for m in ("bev_growth", "speed_level")],
    ),
]
NAMES = [s.name for s in STAGES]


def _done(stage: Stage) -> bool:
    return all(p.exists() for p in stage.outputs())


def main(argv=None) -> None:
    p = argparse.ArgumentParser(
        description="Replication pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="stages: " + ", ".join(NAMES),
    )
    p.add_argument(
        "--list", action="store_true", help="show stages and whether their outputs exist"
    )
    p.add_argument("--only", choices=NAMES, nargs="+", help="run only these stages")
    p.add_argument("--from", dest="start", choices=NAMES, help="run this stage and all later ones")
    p.add_argument("--to", dest="stop", choices=NAMES, help="stop after this stage")
    p.add_argument("--force", action="store_true", help="rebuild outputs that already exist")
    p.add_argument("--download", action="store_true", help="covariates: re-download ACS data")
    p.add_argument("--first-year", type=int, help="station_year: first year to build")
    p.add_argument(
        "--last-year", type=int, default=STATION_YEARS[-1], help="station_year: last year to build"
    )
    p.add_argument(
        "--station-year-out",
        type=Path,
        help="station_year/zip_traffic: alternative folder for station-year files (e.g. to test a rebuild)",
    )
    p.add_argument(
        "--stata-steps", nargs="+", help="stata: run only these do-files, e.g. 02_main_tables"
    )
    args = p.parse_args(argv)

    if args.list:
        for s in STAGES:
            print(f"{s.name:15s} {'done' if _done(s) else 'todo'}{'' if s.auto else '  (manual)'}")
        return

    logdir = CFG.output_dir / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(), logging.FileHandler(logdir / "run_all.log")],
    )

    if args.only:
        todo, explicit = [s for s in STAGES if s.name in args.only], True
    else:
        lo = NAMES.index(args.start) if args.start else 0
        hi = NAMES.index(args.stop) if args.stop else len(NAMES) - 1
        todo, explicit = STAGES[lo : hi + 1], bool(args.start)

    t0 = time.time()
    for s in todo:
        if not explicit and not args.force and (not s.auto or _done(s)):
            log.info("skip %-13s (%s)", s.name, "manual stage" if not s.auto else "outputs exist")
            continue
        if not explicit and not s.auto:
            continue
        log.info("start %s", s.name)
        t = time.time()
        s.run(args)
        log.info("done  %-13s %.1f min", s.name, (time.time() - t) / 60)
    log.info("pipeline finished in %.1f min", (time.time() - t0) / 60)


if __name__ == "__main__":
    main()
