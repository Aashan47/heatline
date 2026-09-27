"""Open-Meteo forecast ingest, with a cache and an honest freshness stamp.

Data source: https://api.open-meteo.com/v1/forecast
Licence: CC-BY 4.0, free tier, non-commercial only. See SOURCES.md section 6.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .config import KARACHI_LAT, KARACHI_LON, KARACHI_TZ

API_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo returns wind in km/h. Liljegren wants m/s. Converting in the wrong
# direction, or not at all, inflates the convective cooling term and silently
# understates the heat load. Named here so the conversion is never implicit.
KMH_TO_MS = 1000.0 / 3600.0

HOURLY_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "wind_speed_10m",
    "shortwave_radiation",
    "direct_radiation",
    "direct_normal_irradiance",
)

# /tmp on Cloud Run, a project directory locally. The container filesystem is
# writable but ephemeral and per-instance, so the cache is a per-instance
# nicety rather than shared state, which is all it was ever meant to be.
CACHE_DIR = Path(os.environ.get(
    "HEATLINE_CACHE_DIR",
    "/tmp/heatline-cache" if os.environ.get("K_SERVICE")
    else str(Path(__file__).resolve().parent.parent / ".cache")))
CACHE_TTL_SECONDS = 15 * 60

ATTRIBUTION = "Weather data by Open-Meteo.com, CC BY 4.0"


@dataclass(frozen=True)
class Forecast:
    """An hourly forecast series, plus when we actually obtained it.

    fetched_at is the honest freshness signal. Open-Meteo's forecast endpoint
    does not publish a model initialisation time, so we do not claim to know
    how old the underlying model run is, only how old our copy is.
    """

    times: list[str]
    temperature_c: list[float]
    relative_humidity_pct: list[float]
    surface_pressure_hpa: list[float]
    wind_speed_ms: list[float]
    shortwave_wm2: list[float]
    direct_wm2: list[float]
    dni_wm2: list[float]
    fetched_at: float
    timezone: str
    elevation_m: float
    from_cache: bool = False
    attribution: str = ATTRIBUTION
    _index: dict[str, int] = field(default_factory=dict, repr=False)

    def index_of(self, iso_hour: str) -> int | None:
        return self._index.get(iso_hour)

    def __len__(self) -> int:
        return len(self.times)


def _cache_path(lat: float, lon: float) -> Path:
    return CACHE_DIR / f"forecast_{lat:.4f}_{lon:.4f}.json"


def _build(payload: dict, fetched_at: float, from_cache: bool) -> Forecast:
    h = payload["hourly"]
    times = list(h["time"])
    return Forecast(
        times=times,
        temperature_c=[float(v) for v in h["temperature_2m"]],
        relative_humidity_pct=[float(v) for v in h["relative_humidity_2m"]],
        surface_pressure_hpa=[float(v) for v in h["surface_pressure"]],
        wind_speed_ms=[float(v) * KMH_TO_MS for v in h["wind_speed_10m"]],
        shortwave_wm2=[float(v) for v in h["shortwave_radiation"]],
        direct_wm2=[float(v) for v in h["direct_radiation"]],
        dni_wm2=[float(v) for v in h["direct_normal_irradiance"]],
        fetched_at=fetched_at,
        timezone=payload.get("timezone", KARACHI_TZ),
        elevation_m=float(payload.get("elevation", 0.0)),
        from_cache=from_cache,
        _index={t: i for i, t in enumerate(times)},
    )


def fetch_forecast(
    lat: float = KARACHI_LAT,
    lon: float = KARACHI_LON,
    forecast_days: int = 3,
    use_cache: bool = True,
    client: httpx.Client | None = None,
) -> Forecast:
    """Fetch the hourly forecast, or serve a recent cached copy.

    The cache is keyed by location and holds the raw payload plus the time we
    fetched it, so a cached forecast carries its real age rather than looking
    freshly downloaded.
    """
    path = _cache_path(lat, lon)

    if use_cache and path.exists():
        try:
            blob = json.loads(path.read_text())
            age = time.time() - float(blob["fetched_at"])
            if age < CACHE_TTL_SECONDS:
                return _build(blob["payload"], float(blob["fetched_at"]), True)
        except (KeyError, ValueError, json.JSONDecodeError):
            # A corrupt cache is not a reason to fail; refetch instead.
            pass

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_FIELDS),
        "timezone": KARACHI_TZ,
        "forecast_days": forecast_days,
    }
    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(API_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            client.close()

    fetched_at = time.time()
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fetched_at": fetched_at, "payload": payload}))

    return _build(payload, fetched_at, False)
