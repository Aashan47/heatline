"""Ingest: the unit conversion that would have been silent, and the cache."""

from heatline.ingest import KMH_TO_MS, _build


def test_kmh_to_ms_factor_is_right_way_round():
    """Inverting this inflates the convective cooling term and understates the
    heat load, which would look plausible in every output."""
    assert KMH_TO_MS == 1000.0 / 3600.0
    assert 36.0 * KMH_TO_MS == 10.0


def test_wind_is_converted_at_the_boundary():
    payload = {
        "timezone": "Asia/Karachi",
        "elevation": 7.0,
        "hourly": {
            "time": ["2026-09-27T12:00"],
            "temperature_2m": [31.0],
            "relative_humidity_2m": [62.0],
            "surface_pressure": [1005.0],
            "wind_speed_10m": [18.0],
            "shortwave_radiation": [794.0],
            "direct_radiation": [520.0],
            "direct_normal_irradiance": [700.0],
        },
    }
    f = _build(payload, fetched_at=1.0, from_cache=False)
    assert f.wind_speed_ms[0] == 18.0 * KMH_TO_MS
    assert f.wind_speed_ms[0] < 6.0


def test_index_lookup_finds_hours_and_misses_cleanly(forecast):
    assert forecast.index_of(forecast.times[5]) == 5
    assert forecast.index_of("not-an-hour") is None


def test_forecast_carries_attribution(forecast):
    assert "Open-Meteo" in forecast.attribution
    assert "CC BY 4.0" in forecast.attribution
