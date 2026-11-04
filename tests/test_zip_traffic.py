"""Unit tests for the station -> ZIP spatial aggregation helpers."""

import numpy as np
import pytest

from ev_congestion.zip_traffic import haversine_km


def test_haversine_known_distance():
    # Los Angeles City Hall -> San Francisco City Hall, about 559 km
    assert haversine_km(34.0537, -118.2428, 37.7793, -122.4193) == pytest.approx(559, abs=2)


def test_haversine_broadcasts_and_zero():
    d = haversine_km(
        np.array([[34.0]]), np.array([[-118.0]]), np.array([34.0, 35.0]), np.array([-118.0, -118.0])
    )
    assert d.shape == (1, 2)
    assert d[0, 0] == 0
    assert d[0, 1] == pytest.approx(111.2, abs=0.2)  # one degree of latitude
