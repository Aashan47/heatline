"""WBGT from forecast variables, by the Liljegren method.

NIOSH 2016-106 defines outdoor WBGT as

    WBGT = 0.7 tnwb + 0.2 tg + 0.1 ta

where tnwb is a natural wet bulb temperature and tg a black globe temperature.
Both are instrument readings at the worksite. A forecast has neither.

Liljegren et al. (2008) solve the globe and natural-wet-bulb energy balances
from standard meteorological variables instead. We use ECMWF's implementation
in thermofeel (Apache-2.0) rather than reimplementing an iterative solver, so
the numbers come from a maintained library published by a national
meteorological service. See SOURCES.md sections 1 and 2.
"""

from __future__ import annotations

from dataclasses import dataclass

import thermofeel as tf

from .config import SKIN_TEMPERATURE_C
from .ingest import Forecast

KELVIN = 273.15


@dataclass(frozen=True)
class WbgtHour:
    """WBGT for one hour, with the inputs that produced it.

    wbgt_c is a single modelled value, not an interval. Liljegren's own error
    against measured WBGT is not quantified here because we have not opened a
    source for it, so we do not invent one. The interval in this tool comes
    from the limit side, where NIOSH does state an error. See limits.py.
    """

    time: str
    wbgt_c: float
    air_c: float
    relative_humidity_pct: float
    wind_ms: float
    shortwave_wm2: float
    cos_solar_zenith: float
    direct_fraction: float
    is_daylight: bool
    airflow_adds_heat: bool


def _cos_solar_zenith(direct_wm2: float, dni_wm2: float) -> float:
    """Cosine of the solar zenith angle, from Open-Meteo's own two fields.

    Direct radiation on a horizontal surface equals direct normal irradiance
    times cos(solar zenith angle), so the ratio recovers the cosine without a
    second sun model that could disagree with the radiation we were handed.
    Zero at night, when both fields are zero.
    """
    if dni_wm2 <= 0.0:
        return 0.0
    return min(1.0, max(0.0, direct_wm2 / dni_wm2))


def _direct_fraction(direct_wm2: float, shortwave_wm2: float) -> float:
    if shortwave_wm2 <= 0.0:
        return 0.0
    return min(1.0, max(0.0, direct_wm2 / shortwave_wm2))


def wbgt_for_hour(forecast: Forecast, i: int) -> WbgtHour:
    """WBGT for a single hour of a forecast series."""
    cossza = _cos_solar_zenith(forecast.direct_wm2[i], forecast.dni_wm2[i])
    fdir = _direct_fraction(forecast.direct_wm2[i], forecast.shortwave_wm2[i])

    wbgt_k = tf.calculate_wbgt_liljegren(
        t2_k=forecast.temperature_c[i] + KELVIN,
        rh=forecast.relative_humidity_pct[i],
        pressure=forecast.surface_pressure_hpa[i],
        va=forecast.wind_speed_ms[i],
        ssrd=forecast.shortwave_wm2[i],
        fdir=fdir,
        cossza=cossza,
    )
    wbgt_c = float(wbgt_k) - KELVIN

    air_c = forecast.temperature_c[i]
    return WbgtHour(
        time=forecast.times[i],
        wbgt_c=wbgt_c,
        air_c=air_c,
        relative_humidity_pct=forecast.relative_humidity_pct[i],
        wind_ms=forecast.wind_speed_ms[i],
        shortwave_wm2=forecast.shortwave_wm2[i],
        cos_solar_zenith=cossza,
        direct_fraction=fdir,
        is_daylight=forecast.shortwave_wm2[i] > 0.0,
        airflow_adds_heat=air_c > SKIN_TEMPERATURE_C,
    )


def wbgt_series(forecast: Forecast, hours: int | None = None) -> list[WbgtHour]:
    n = len(forecast) if hours is None else min(hours, len(forecast))
    return [wbgt_for_hour(forecast, i) for i in range(n)]
