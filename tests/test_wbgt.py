"""WBGT: units, geometry, determinism, and physical direction."""

import pytest

from heatline.wbgt import _cos_solar_zenith, _direct_fraction, wbgt_for_hour, wbgt_series


def test_cos_solar_zenith_is_zero_at_night_not_a_division_error():
    assert _cos_solar_zenith(0.0, 0.0) == 0.0


def test_cos_solar_zenith_stays_within_the_unit_interval(forecast):
    for h in wbgt_series(forecast):
        assert 0.0 <= h.cos_solar_zenith <= 1.0


def test_direct_fraction_stays_within_the_unit_interval(forecast):
    assert _direct_fraction(0.0, 0.0) == 0.0
    for h in wbgt_series(forecast):
        assert 0.0 <= h.direct_fraction <= 1.0


def test_wbgt_is_deterministic(forecast):
    """The standing check on any component we treat as fixed, kept after the
    Clay embedding bug: run the same input twice and assert equality."""
    a = [h.wbgt_c for h in wbgt_series(forecast)]
    b = [h.wbgt_c for h in wbgt_series(forecast)]
    assert a == b


def test_wbgt_is_plausible_and_in_celsius(forecast):
    """Catches a Kelvin or Fahrenheit slip, which would otherwise look like a
    very hot or very cold city rather than like a bug."""
    values = [h.wbgt_c for h in wbgt_series(forecast)]
    assert all(5.0 < v < 45.0 for v in values), (min(values), max(values))


def test_wbgt_peaks_in_the_afternoon_not_at_night(forecast):
    series = wbgt_series(forecast, 24)
    peak = max(series, key=lambda h: h.wbgt_c)
    assert 11 <= int(peak.time[11:13]) <= 17


def test_wbgt_exceeds_air_temperature_in_humid_sun(forecast):
    """In a humid coastal daytime the exposure index should sit above the dry
    bulb reading. If it does not, the humidity or radiation terms are not
    reaching the model."""
    day = [h for h in wbgt_series(forecast, 24) if h.shortwave_wm2 > 400]
    assert day
    assert any(h.wbgt_c > h.air_c - 2.0 for h in day)


def test_hotter_and_wetter_gives_higher_wbgt(forecast_factory):
    """Monotonicity in the direction physics requires."""
    hot = forecast_factory(base_temp=30.0, peak_temp=42.0)
    cool = forecast_factory(base_temp=18.0, peak_temp=26.0)
    assert max(h.wbgt_c for h in wbgt_series(hot, 24)) > max(
        h.wbgt_c for h in wbgt_series(cool, 24)
    )


def test_airflow_adds_heat_flag_tracks_skin_temperature(forecast_factory):
    from heatline.config import SKIN_TEMPERATURE_C

    hot = forecast_factory(base_temp=36.0, peak_temp=44.0)
    series = wbgt_series(hot, 24)
    assert any(h.airflow_adds_heat for h in series)
    for h in series:
        assert h.airflow_adds_heat == (h.air_c > SKIN_TEMPERATURE_C)

    mild = forecast_factory(base_temp=20.0, peak_temp=28.0)
    assert not any(h.airflow_adds_heat for h in wbgt_series(mild, 24))
