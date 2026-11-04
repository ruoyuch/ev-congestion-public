"""Unit tests for the station-hour -> station-year aggregation, on synthetic data."""

import numpy as np
import pandas as pd
import pytest

from ev_congestion.station_year import clean_station_hour, station_day_metrics, station_year_metrics


def _hours(date: str, station: int, rows: dict[int, tuple[float, float]], lane="ML") -> list[dict]:
    """rows: {hour: (flow, speed)} for one station-day."""
    return [
        {
            "timestamp": f"{date} {h:02d}:00:00",
            "station_id": station,
            "lane_type": lane,
            "total_flow": f,
            "avg_speed": s,
        }
        for h, (f, s) in rows.items()
    ]


@pytest.fixture
def hourly() -> pd.DataFrame:
    rows = []
    # Tue 01/07/2020: two peak hours, one non-peak hour, the midnight hour
    rows += _hours("01/07/2020", 1, {7: (100, 60), 17: (300, 40), 12: (200, 65), 2: (50, 70)})
    # Sat 01/11/2020: one peak hour
    rows += _hours("01/11/2020", 1, {8: (100, 50)})
    # an off-ramp (dropped)
    rows += _hours("01/07/2020", 2, {7: (999, 10)}, lane="OR")
    return pd.DataFrame(rows)


def test_lane_filter_and_calendar(hourly):
    df = clean_station_hour(hourly)
    assert set(df["station_id"]) == {1}
    tue = df[df["date"] == "2020-01-07"].iloc[0]
    assert tue["is_weekday"] and tue["is_normal_weekday"]
    assert not df[df["date"] == "2020-01-11"]["is_weekday"].any()


def test_flow_weighted_speed(hourly):
    day = station_day_metrics(clean_station_hour(hourly)).set_index("date")
    tue = day.loc["2020-01-07"]
    assert tue["avg_speed_peak"] == pytest.approx((100 * 60 + 300 * 40) / 400)  # 45
    assert tue["avg_hourly_flow_peak"] == pytest.approx(400 / 2)
    assert tue["avg_speed_non_peak"] == pytest.approx((200 * 65 + 50 * 70) / 250)
    assert tue["avg_speed_mid_night"] == 70 and tue["avg_hourly_flow_mid_night"] == 50
    assert np.isnan(day.loc["2020-01-11", "avg_speed_mid_night"])


def test_year_means_by_day_type(hourly):
    yr = station_year_metrics(station_day_metrics(clean_station_hour(hourly))).iloc[0]
    assert yr["weekday_days"] == 1 and yr["weekend_days"] == 1 and yr["normal_weekday_days"] == 1
    assert yr["weekday_avg_speed_peak"] == pytest.approx(45)
    assert yr["weekend_avg_speed_peak"] == pytest.approx(50)
