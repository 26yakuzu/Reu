import numpy as np
import pytest
from pyproj import CRS

from terrasense.geo.boundary import BoundaryUnavailable, boundary_from_files, valid_lonlat
from terrasense.geo.crs import require_crs, utm_for

from .conftest import needs_boundary

INSIDE = {"Lagos": (3.38, 6.52), "Abuja": (7.49, 9.06), "Kano": (8.52, 12.00), "Maiduguri": (13.15, 11.83), "Hadejia": (10.04, 12.45)}
# Neighbouring capitals/cities that a bounding box would wrongly accept.
OUTSIDE = {"Cotonou (Benin)": (2.42, 6.37), "Niamey (Niger)": (2.11, 13.51), "Zinder (Niger)": (8.99, 13.80),
           "Douala (Cameroon)": (9.70, 4.05), "N'Djamena (Chad)": (15.04, 12.13), "Gulf of Guinea": (5.0, 3.5),
           "Paris": (2.35, 48.86)}


@needs_boundary
def test_inside_and_outside_nigeria():
    from terrasense.geo.boundary import nigeria
    b = nigeria()
    for name, (lon, lat) in INSIDE.items():
        assert b.contains([lon], [lat])[0], name
    for name, (lon, lat) in OUTSIDE.items():
        assert not b.contains([lon], [lat])[0], name


@needs_boundary
def test_state_lookup():
    from terrasense.geo.boundary import nigeria
    assert nigeria().state_of(3.38, 6.52) == "Lagos"
    assert nigeria().state_of(10.04, 12.45) == "Jigawa"


def test_invalid_coordinates_rejected():
    ok = valid_lonlat([0, np.nan, 200, 10, 10], [0, 5, 5, -91, np.inf])
    assert ok.tolist() == [True, False, False, False, False]


@needs_boundary
def test_invalid_coordinates_never_inside():
    from terrasense.geo.boundary import nigeria
    assert not nigeria().contains([np.nan, 999.0], [9.0, 9.0]).any()


def test_missing_boundary_raises(tmp_path):
    with pytest.raises(BoundaryUnavailable):
        boundary_from_files(tmp_path / "nope.geojson")


def test_utm_zones_for_nigeria():
    assert utm_for(3.4, 6.5) == CRS.from_epsg(32631)
    assert utm_for(7.5, 9.0) == CRS.from_epsg(32632)
    assert utm_for(13.2, 11.8) == CRS.from_epsg(32633)


def test_missing_crs_refused():
    with pytest.raises(ValueError):
        require_crs(None, "dataset")
