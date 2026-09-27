"""A fixed synthetic forecast, so every test runs offline and deterministically.

No test in this suite calls Open-Meteo. A test that depends on live weather
cannot fail for the right reason.
"""

from __future__ import annotations

import time

import pytest

from heatline.ingest import Forecast


def make_forecast(
    n_hours: int = 72,
    fetched_at: float | None = None,
    base_temp: float = 24.0,
    peak_temp: float = 32.0,
) -> Forecast:
    """A smooth diurnal cycle, hot and humid, shaped like a Karachi day."""
    times, temp, rh, pres, wind, sw, direct, dni = [], [], [], [], [], [], [], []
    for i in range(n_hours):
        hour = i % 24
        day = 27 + i // 24
        times.append(f"2026-09-{day:02d}T{hour:02d}:00")

        # Peak at 14:00, trough at 05:00.
        warmth = max(0.0, 1.0 - abs(hour - 14) / 9.0)
        t = base_temp + (peak_temp - base_temp) * warmth
        temp.append(round(t, 1))
        # Humidity runs opposite to temperature, coastal and high throughout.
        rh.append(round(85.0 - 25.0 * warmth, 0))
        pres.append(1005.0)
        wind.append(15.0)  # km/h, converted to m/s by the Forecast builder

        daylight = 1.0 if 7 <= hour <= 18 else 0.0
        solar = daylight * max(0.0, 1.0 - abs(hour - 12.5) / 6.0)
        sw.append(round(850.0 * solar, 1))
        direct.append(round(600.0 * solar, 1))
        dni.append(round(800.0 * solar, 1) if solar > 0 else 0.0)

    kmh_to_ms = 1000.0 / 3600.0
    return Forecast(
        times=times,
        temperature_c=temp,
        relative_humidity_pct=rh,
        surface_pressure_hpa=pres,
        wind_speed_ms=[w * kmh_to_ms for w in wind],
        shortwave_wm2=sw,
        direct_wm2=direct,
        dni_wm2=dni,
        fetched_at=time.time() if fetched_at is None else fetched_at,
        timezone="Asia/Karachi",
        elevation_m=7.0,
        _index={t: i for i, t in enumerate(times)},
    )


@pytest.fixture
def forecast() -> Forecast:
    return make_forecast()


@pytest.fixture
def stale_forecast() -> Forecast:
    # Fetched four hours ago, well past the 90 minute ceiling.
    return make_forecast(fetched_at=time.time() - 4 * 3600)


@pytest.fixture
def forecast_factory():
    """Build a synthetic forecast with chosen extremes.

    Exposed as a fixture rather than imported directly, because an installed
    package called "tests" can shadow a module import from this directory.
    """
    return make_forecast
