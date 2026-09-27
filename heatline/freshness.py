"""The two checks that make the tool refuse instead of answering.

Both are ours, not the provider's, and both say so. Pretending a self-imposed
cap is a data limitation would be the same dishonesty the rest of this tool
exists to avoid.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .config import MAX_FETCH_AGE_MINUTES, SUPPORTED_HORIZON_HOURS
from .ingest import Forecast


@dataclass(frozen=True)
class FreshnessVerdict:
    ok: bool
    fetch_age_minutes: float
    max_fetch_age_minutes: int
    reason: str | None = None


@dataclass(frozen=True)
class HorizonVerdict:
    ok: bool
    requested_hour_offset: int | None
    supported_horizon_hours: int
    reason: str | None = None


def check_freshness(forecast: Forecast, now: float | None = None) -> FreshnessVerdict:
    now = time.time() if now is None else now
    age_minutes = (now - forecast.fetched_at) / 60.0
    if age_minutes > MAX_FETCH_AGE_MINUTES:
        return FreshnessVerdict(
            ok=False,
            fetch_age_minutes=age_minutes,
            max_fetch_age_minutes=MAX_FETCH_AGE_MINUTES,
            reason=(
                f"The forecast in hand was retrieved {age_minutes:.0f} minutes "
                f"ago, and this tool will not advise on data older than "
                f"{MAX_FETCH_AGE_MINUTES} minutes."
            ),
        )
    return FreshnessVerdict(
        ok=True,
        fetch_age_minutes=age_minutes,
        max_fetch_age_minutes=MAX_FETCH_AGE_MINUTES,
    )


def check_horizon(forecast: Forecast, iso_hour: str) -> HorizonVerdict:
    """Is the requested hour inside the window this tool will answer for."""
    i = forecast.index_of(iso_hour)
    if i is None:
        return HorizonVerdict(
            ok=False,
            requested_hour_offset=None,
            supported_horizon_hours=SUPPORTED_HORIZON_HOURS,
            reason=(
                f"{iso_hour} is not in the forecast series, which runs from "
                f"{forecast.times[0]} to {forecast.times[-1]}."
            ),
        )
    if i >= SUPPORTED_HORIZON_HOURS:
        return HorizonVerdict(
            ok=False,
            requested_hour_offset=i,
            supported_horizon_hours=SUPPORTED_HORIZON_HOURS,
            reason=(
                f"{iso_hour} is {i} hours into the series. This tool answers "
                f"only {SUPPORTED_HORIZON_HOURS} hours ahead, because an hourly "
                f"heat advisory further out than that is a forecast of a "
                f"forecast. The cap is this tool's, not Open-Meteo's."
            ),
        )
    return HorizonVerdict(
        ok=True,
        requested_hour_offset=i,
        supported_horizon_hours=SUPPORTED_HORIZON_HOURS,
    )
