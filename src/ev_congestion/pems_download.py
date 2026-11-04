"""Download raw PeMS station-hour and station-metadata files (Selenium).

PeMS (https://pems.dot.ca.gov) requires a free account and serves files
through the "Data Clearinghouse" web page, so this module drives a Chrome
browser. Credentials are prompted at run time (``getpass``) and are never
stored or printed; set ``PEMS_USERNAME`` in the environment to skip the
username prompt.

Files are written to the layout the rest of the pipeline expects::

    <RAW_PEMS_DIR>/station_hour/<year>/dNN_text_station_hour_<year>_<MM>.txt
    <RAW_PEMS_DIR>/station_hour/<year>/original_zipped/*.txt.gz
    <RAW_PEMS_DIR>/station_metadata/<year>/dNN_text_meta_<YYYY_MM_DD>.txt

Existing files are skipped, so an interrupted download can be resumed.
Requirements: Google Chrome, a matching ``chromedriver`` (``CHROMEDRIVER_PATH``)
and ``selenium`` (``pip install selenium``). Tested on macOS only.

Usage::

    python -m ev_congestion.pems_download --mode station_hour --years 2014 2024
    python -m ev_congestion.pems_download --mode meta --districts 4 7

Adapted from BayAreaMetro/pems-typical-weekday (download-PeMS-data.py).
"""

from __future__ import annotations

import argparse
import getpass
import gzip
import os
import random
import shutil
import time
from pathlib import Path

CLEARINGHOUSE_URL = "https://pems.dot.ca.gov/?dnode=Clearinghouse"
ALL_DISTRICTS = ["3", "4", "5", "6", "7", "8", "10", "11", "12"]


def _pause(lo: float = 0.5, hi: float = 1.5) -> None:
    time.sleep(random.uniform(lo, hi))


def _wait_for(path: Path, poll: float = 2.0) -> None:
    while not path.exists():
        time.sleep(poll)


def login(chromedriver_path: str):
    """Open Chrome, log in to PeMS and return the Selenium driver."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By

    username = os.environ.get("PEMS_USERNAME") or input("PeMS username: ")
    password = getpass.getpass("PeMS password: ")

    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=opts)
    driver.get(CLEARINGHOUSE_URL)
    _pause()
    driver.find_element(By.ID, "username").send_keys(username)
    _pause()
    driver.find_element(By.ID, "password").send_keys(password)
    _pause()
    driver.find_element(By.NAME, "login").click()
    _pause()
    driver.get(CLEARINGHOUSE_URL)
    time.sleep(5)
    if "login" in driver.current_url:
        driver.quit()
        raise RuntimeError("PeMS login failed")
    return driver


def _open_district(driver, mode: str, district: str) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select

    Select(driver.find_element(By.ID, "type")).select_by_value(mode)
    Select(driver.find_element(By.ID, "district_id")).select_by_value(district)
    driver.find_element(By.NAME, "submit").click()
    _pause(1, 3)


def _year_cells(driver, year: int):
    from selenium.webdriver.common.by import By

    return driver.find_elements(
        By.XPATH, f"//td[contains(text(),'{year % 100:02d}')]/following-sibling::td"
    )


def download_station_hour(driver, district: str, years, dest: Path, downloads: Path) -> None:
    """Download and unzip the 12 monthly station_hour files of each year."""
    from selenium.webdriver.common.by import By

    for year in years:
        done = False
        for cell in _year_cells(driver, year):
            try:
                cell.click()
                time.sleep(2)
            except Exception:
                continue
            for month in range(1, 13):
                name = f"d{int(district):02d}_text_station_hour_{year}_{month:02d}.txt.gz"
                unzip_dir = dest / "station_hour" / str(year)
                zip_path = unzip_dir / "original_zipped" / name
                if zip_path.exists():
                    continue
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    driver.find_element(By.LINK_TEXT, name).click()
                except Exception:
                    print(f"  not listed: {name}")
                    continue
                _wait_for(downloads / name)
                shutil.move(downloads / name, zip_path)
                with gzip.open(zip_path, "rb") as fin, open(unzip_dir / name[:-3], "wb") as fout:
                    shutil.copyfileobj(fin, fout)
                print(f"  {name}")
                done = True
            if done:
                break
        print(f"district {district} {year}: {'ok' if done else 'nothing new'}")


def download_metadata(driver, district: str, years, dest: Path, downloads: Path) -> None:
    """Download every metadata snapshot (text format) listed for each year."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    rows_xpath = "//tr[td/a[contains(text(),'(text)')]]"
    for year in years:
        out_dir = dest / "station_metadata" / str(year)
        out_dir.mkdir(parents=True, exist_ok=True)
        previous = driver.find_elements(By.XPATH, rows_xpath)
        done = False
        for cell in _year_cells(driver, year):
            try:
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(cell))
                cell.click()
                time.sleep(2)
                rows = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, rows_xpath))
                )
            except Exception:
                continue
            if rows == previous:
                continue
            previous = rows
            for row in rows:
                try:
                    name = (
                        row.find_element(By.XPATH, "./td[3]").text.replace("tmdd", "text") + ".txt"
                    )
                    if (out_dir / name).exists():
                        continue
                    row.find_element(By.XPATH, "./td/a[contains(text(),'(text)')]").click()
                    time.sleep(2)
                    _wait_for(downloads / name)
                    shutil.move(downloads / name, out_dir / name)
                    print(f"  {name}")
                    done = True
                except Exception:
                    continue
            if done:
                break
        print(f"district {district} {year}: {'ok' if done else 'nothing new'}")


def main(argv=None) -> None:
    from ev_congestion.config import CFG

    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--mode", choices=["station_hour", "meta"], default="station_hour")
    p.add_argument(
        "--districts", nargs="+", default=ALL_DISTRICTS, help="Caltrans district numbers"
    )
    p.add_argument("--years", nargs=2, type=int, default=[2010, 2024], metavar=("FIRST", "LAST"))
    a = p.parse_args(argv)

    driver = login(CFG.chromedriver_path)
    years = range(a.years[0], a.years[1] + 1)
    try:
        for d in a.districts:
            _open_district(driver, a.mode, d)
            fn = download_station_hour if a.mode == "station_hour" else download_metadata
            fn(driver, d, years, CFG.raw_pems_dir, CFG.downloads_dir)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
