"""Tests for ``src/waypoint_utils.py``.

Graded by ``warg run utils grade-tests``: pass on the real code, 90% branch
coverage, and fail on every broken copy in ``grader/mutants/``.
"""

import pytest

from src.types import Coordinate
from src.waypoint_utils import (
    east_north_coordinate_offset_m,
    parse_waypoints_file,
    sort_clockwise_sweep,
)

# Meters in one degree of latitude (or of longitude at the equator).
METERS_PER_DEGREE = 111195.08


def write_to_tmp_waypoints_file(tmp_path, text):
    """Write ``text`` to a YAML file and hand back its path.

    ``tmp_path`` is a pytest fixture: a fresh empty directory per test.
    """
    path = tmp_path / "waypoints.yaml"
    path.write_text(text)
    return path


# ---------------------------------------------------------------------------
# parse_waypoints_file: files that parse fine
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            """
            home: {lat: 1, lon: 2, alt: 3}
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
        (
            """
            waypoints:
              - {lat: 4, lon: 5, alt: 6}
              - {lat: 7, lon: 8, alt: 9}
            """,
            (None, [Coordinate(4, 5, 6), Coordinate(7, 8, 9)]),
        ),
        (
            """
            # a lap

            home: {lat: 1, lon: 2, alt: 3}

            waypoints:
              # first leg
              - {lat: 4, lon: 5, alt: 6}
            """,
            (Coordinate(1, 2, 3), [Coordinate(4, 5, 6)]),
        ),
    ],
    ids=["home-and-waypoints", "no-home", "comments-and-blank-lines"],
)
def test_parse_waypoints_file_success(tmp_path, text, expected):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == expected


def test_parse_accepts_decimal_values(tmp_path):
    text = "waypoints:\n  - {lat: 43.47179, lon: -80.541524, alt: 15.5}\n"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    _, waypoints = parse_waypoints_file(path)
    assert waypoints[0].lat == pytest.approx(43.47179)
    assert waypoints[0].lon == pytest.approx(-80.541524)
    assert waypoints[0].alt == pytest.approx(15.5)


def test_parse_accepts_numbers_written_as_strings(tmp_path):
    text = 'waypoints:\n  - {lat: "4.5", lon: "5", alt: "6"}\n'
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == (None, [Coordinate(4.5, 5.0, 6.0)])


def test_parse_keeps_waypoint_order(tmp_path):
    text = (
        "waypoints:\n"
        "  - {lat: 3, lon: 3, alt: 3}\n"
        "  - {lat: 1, lon: 1, alt: 1}\n"
        "  - {lat: 2, lon: 2, alt: 2}\n"
    )
    path = write_to_tmp_waypoints_file(tmp_path, text)
    _, waypoints = parse_waypoints_file(path)
    assert waypoints == [
        Coordinate(3, 3, 3),
        Coordinate(1, 1, 1),
        Coordinate(2, 2, 2),
    ]


def test_parse_accepts_string_path(tmp_path):
    text = "waypoints:\n  - {lat: 1, lon: 2, alt: 3}\n"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(str(path)) == (None, [Coordinate(1, 2, 3)])


# ---------------------------------------------------------------------------
# parse_waypoints_file: bad data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("- 1\n- 2\n", "expected a mapping"),
        ("just a string\n", "expected a mapping"),
        ("waypoints:\n  - {lon: 2, alt: 3}\n", "missing key.*lat"),
        ("waypoints:\n  - {lat: 1, alt: 3}\n", "missing key.*lon"),
        ("waypoints:\n  - {lat: 1, lon: 2}\n", "missing key.*alt"),
        ("waypoints:\n  - {lat: abc, lon: 2, alt: 3}\n", "non-numeric"),
        ("waypoints:\n  - {lat: 1, lon: 2, alt: null}\n", "non-numeric"),
        ("waypoints:\n  - {lat: [1], lon: 2, alt: 3}\n", "non-numeric"),
        ("waypoints:\n  - 5\n", "must be a mapping"),
        ("waypoints: 5\n", "must be a list"),
        ("waypoints: [1, 2\n", "invalid YAML"),
        ("home: 5\n", "home"),
        ("home: {lat: 1, lon: 2}\n", "home is missing"),
        ("home: {lat: abc, lon: 2, alt: 3}\n", "non-numeric"),
        (
            "waypoints:\n  - {lat: 1, lon: 2, alt: 3}\n  - {lat: x, lon: 2, alt: 3}\n",
            "waypoint 2",
        ),
        ("waypoints:\n  - {lat: x, lon: 2, alt: 3}\n", "waypoint 1"),
    ],
    ids=[
        "top-level-list",
        "top-level-scalar",
        "missing-lat",
        "missing-lon",
        "missing-alt",
        "lat-not-a-number",
        "alt-null",
        "lat-is-a-list",
        "waypoint-not-a-mapping",
        "waypoints-not-a-list",
        "invalid-yaml",
        "home-not-a-mapping",
        "home-missing-alt",
        "home-not-a-number",
        "error-names-second-waypoint",
        "error-names-first-waypoint",
    ],
)
def test_parse_rejects_bad_data(tmp_path, text, message):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match=message):
        parse_waypoints_file(path)


def test_parse_missing_file_raises(tmp_path):
    with pytest.raises(OSError):
        parse_waypoints_file(tmp_path / "does_not_exist.yaml")


# ---------------------------------------------------------------------------
# parse_waypoints_file: out of range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90.1, 0), (-90.1, 0), (0, 180.1), (0, -180.1)],
    ids=["lat-too-high", "lat-too-low", "lon-too-high", "lon-too-low"],
)
def test_parse_rejects_out_of_range_waypoint(tmp_path, lat, lon):
    text = f"waypoints:\n  - {{lat: {lat}, lon: {lon}, alt: 0}}\n"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match="out of range"):
        parse_waypoints_file(path)


@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90.1, 0), (-90.1, 0), (0, 180.1), (0, -180.1)],
    ids=["lat-too-high", "lat-too-low", "lon-too-high", "lon-too-low"],
)
def test_parse_rejects_out_of_range_home(tmp_path, lat, lon):
    text = f"home: {{lat: {lat}, lon: {lon}, alt: 0}}\n"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    with pytest.raises(ValueError, match="out of range"):
        parse_waypoints_file(path)


@pytest.mark.parametrize(
    ("lat", "lon"),
    [(90, 180), (-90, -180), (90, -180), (-90, 180)],
    ids=["ne-corner", "sw-corner", "nw-corner", "se-corner"],
)
def test_parse_accepts_values_exactly_on_the_limit(tmp_path, lat, lon):
    text = f"waypoints:\n  - {{lat: {lat}, lon: {lon}, alt: 0}}\n"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == (None, [Coordinate(lat, lon, 0)])


# ---------------------------------------------------------------------------
# parse_waypoints_file: nothing to work with
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["", "\n\n", "# only a comment\n", "waypoints: []\n", "waypoints:\n"],
    ids=["empty", "blank-lines", "only-comment", "empty-list", "null-list"],
)
def test_parse_empty_file_has_no_home_and_no_waypoints(tmp_path, text):
    path = write_to_tmp_waypoints_file(tmp_path, text)
    assert parse_waypoints_file(path) == (None, [])


def test_parse_home_without_waypoints(tmp_path):
    path = write_to_tmp_waypoints_file(tmp_path, "home: {lat: 1, lon: 2, alt: 3}\n")
    assert parse_waypoints_file(path) == (Coordinate(1, 2, 3), [])


def test_parse_returns_frozen_coordinates(tmp_path):
    text = "home: {lat: 1, lon: 2, alt: 3}\nwaypoints:\n  - {lat: 4, lon: 5, alt: 6}\n"
    path = write_to_tmp_waypoints_file(tmp_path, text)
    home, waypoints = parse_waypoints_file(path)

    with pytest.raises(AttributeError):
        home.lat = 99.0
    with pytest.raises(AttributeError):
        waypoints[0].alt = 99.0


# ---------------------------------------------------------------------------
# east_north_coordinate_offset_m
# ---------------------------------------------------------------------------


def test_offset_same_point_is_zero():
    east, north = east_north_coordinate_offset_m(5.0, 5.0, 5.0, 5.0)
    assert east == pytest.approx(0.0, abs=1e-6)
    assert north == pytest.approx(0.0, abs=1e-6)


def test_offset_one_degree_north():
    east, north = east_north_coordinate_offset_m(0.0, 0.0, 1.0, 0.0)
    assert east == pytest.approx(0.0, abs=1e-6)
    assert north == pytest.approx(METERS_PER_DEGREE, abs=0.1)


def test_offset_one_degree_south_is_negative_north():
    east, north = east_north_coordinate_offset_m(1.0, 0.0, 0.0, 0.0)
    assert east == pytest.approx(0.0, abs=1e-6)
    assert north == pytest.approx(-METERS_PER_DEGREE, abs=0.1)


def test_offset_one_degree_east_at_equator():
    east, north = east_north_coordinate_offset_m(0.0, 0.0, 0.0, 1.0)
    assert east == pytest.approx(METERS_PER_DEGREE, abs=0.1)
    assert north == pytest.approx(0.0, abs=1e-6)


def test_offset_one_degree_west_is_negative_east():
    east, north = east_north_coordinate_offset_m(0.0, 0.0, 0.0, -1.0)
    assert east == pytest.approx(-METERS_PER_DEGREE, abs=0.1)
    assert north == pytest.approx(0.0, abs=1e-6)


def test_offset_east_shrinks_with_latitude():
    # cos(60 degrees) is 0.5, so a degree of longitude is half as long.
    east, north = east_north_coordinate_offset_m(60.0, 0.0, 60.0, 1.0)
    assert east == pytest.approx(METERS_PER_DEGREE / 2, abs=0.1)
    assert north == pytest.approx(0.0, abs=1e-6)


def test_offset_uses_the_average_of_the_two_latitudes():
    # Average latitude is 60, so east is half a degree's worth, and the
    # trip covers two degrees of latitude going north.
    east, north = east_north_coordinate_offset_m(59.0, 0.0, 61.0, 1.0)
    assert east == pytest.approx(METERS_PER_DEGREE / 2, abs=0.1)
    assert north == pytest.approx(2 * METERS_PER_DEGREE, abs=0.1)


# ---------------------------------------------------------------------------
# sort_clockwise_sweep
#
# Cardinal points around (10, 10). These coordinates add up exactly in
# floating point, so the centroid is exactly (10, 10) and the bearings are
# exactly north 0, east pi/2, south pi, west 3*pi/2.
# ---------------------------------------------------------------------------

NORTH = Coordinate(11.0, 10.0, 0.0)
EAST = Coordinate(10.0, 11.0, 0.0)
SOUTH = Coordinate(9.0, 10.0, 0.0)
WEST = Coordinate(10.0, 9.0, 0.0)
CENTROID = Coordinate(10.0, 10.0, 0.0)


def test_sort_empty_list():
    assert sort_clockwise_sweep([]) == []


def test_sort_single_waypoint():
    assert sort_clockwise_sweep([NORTH]) == [NORTH]


def test_sort_single_waypoint_with_home():
    assert sort_clockwise_sweep([NORTH], home=EAST) == [NORTH]


def test_sort_returns_a_new_list():
    waypoints = [NORTH]
    result = sort_clockwise_sweep(waypoints)
    assert result is not waypoints
    assert result == waypoints


def test_sort_without_home_starts_north_and_goes_clockwise():
    result = sort_clockwise_sweep([WEST, SOUTH, NORTH, EAST])
    assert result == [NORTH, EAST, SOUTH, WEST]


def test_sort_without_home_does_not_depend_on_input_order():
    result = sort_clockwise_sweep([EAST, WEST, NORTH, SOUTH])
    assert result == [NORTH, EAST, SOUTH, WEST]


def test_sort_does_not_change_the_input_list():
    waypoints = [WEST, SOUTH, NORTH, EAST]
    sort_clockwise_sweep(waypoints)
    assert waypoints == [WEST, SOUTH, NORTH, EAST]


def test_sort_with_home_starts_in_homes_direction():
    # Home is due west of the centroid, so the lap starts at WEST and keeps
    # going clockwise: west, north, east, south.
    home = Coordinate(10.0, 5.0, 0.0)
    result = sort_clockwise_sweep([NORTH, EAST, SOUTH, WEST], home=home)
    assert result == [WEST, NORTH, EAST, SOUTH]


def test_sort_with_home_due_south():
    home = Coordinate(5.0, 10.0, 0.0)
    result = sort_clockwise_sweep([NORTH, EAST, SOUTH, WEST], home=home)
    assert result == [SOUTH, WEST, NORTH, EAST]


def test_sort_with_home_barely_off_the_centroid_still_uses_its_direction():
    # About 0.1 m west of the centroid. Small, but not "on top of it".
    home = Coordinate(10.0, 9.999999, 0.0)
    result = sort_clockwise_sweep([NORTH, EAST, SOUTH, WEST], home=home)
    assert result == [WEST, NORTH, EAST, SOUTH]


def test_sort_with_home_on_the_centroid_starts_north():
    result = sort_clockwise_sweep([WEST, SOUTH, NORTH, EAST], home=CENTROID)
    assert result == [NORTH, EAST, SOUTH, WEST]


def test_sort_same_direction_closer_waypoint_comes_first():
    # Both are due north of the centroid. The nearer one goes first.
    near = Coordinate(11.0, 10.0, 0.0)
    far = Coordinate(12.0, 10.0, 0.0)
    behind = Coordinate(8.0, 10.0, 0.0)
    result = sort_clockwise_sweep([far, behind, near])
    assert result == [near, far, behind]
