"""Comparing a modelled WBGT against a limit interval, with three outcomes.

The third outcome is the point of the tool. When the WBGT falls inside the
limit interval, whether the worker is over the limit depends on where in the
workload band their actual effort sits, and a forecast cannot know that. The
honest answer is that it cannot be determined, not a rounded verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import PROFILES, SKIN_TEMPERATURE_C
from .limits import LimitInterval, limit_interval
from .wbgt import WbgtHour


class Verdict(str, Enum):
    UNDER = "under"
    OVER = "over"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class Assessment:
    time: str
    verdict: Verdict
    wbgt_c: float
    air_c: float
    relative_humidity_pct: float
    wind_ms: float
    limit_low_c: float
    limit_high_c: float
    limit_label: str
    profile_label: str
    niosh_category: str
    margin_c: float | None
    airflow_adds_heat: bool
    skin_temperature_c: float = SKIN_TEMPERATURE_C

    def as_dict(self) -> dict:
        return {
            "time": self.time,
            "verdict": self.verdict.value,
            "wbgt_c": round(self.wbgt_c, 1),
            "air_c": round(self.air_c, 1),
            "relative_humidity_pct": round(self.relative_humidity_pct),
            "wind_ms": round(self.wind_ms, 1),
            "limit_c": [round(self.limit_low_c, 1), round(self.limit_high_c, 1)],
            "limit_label": self.limit_label,
            "profile": self.profile_label,
            "niosh_category": self.niosh_category,
            "margin_c": None if self.margin_c is None else round(self.margin_c, 1),
            "airflow_adds_heat": self.airflow_adds_heat,
        }


def assess(
    hour: WbgtHour,
    profile_key: str = "delivery_rider",
    acclimatized: bool = True,
    limit: LimitInterval | None = None,
) -> Assessment:
    profile = PROFILES[profile_key]
    limit = limit or limit_interval(profile, acclimatized=acclimatized)

    if hour.wbgt_c < limit.low_c:
        verdict = Verdict.UNDER
        # Distance to the nearest edge of the limit, the conservative reading.
        margin: float | None = hour.wbgt_c - limit.low_c
    elif hour.wbgt_c > limit.high_c:
        verdict = Verdict.OVER
        margin = hour.wbgt_c - limit.high_c
    else:
        verdict = Verdict.UNDETERMINED
        margin = None

    return Assessment(
        time=hour.time,
        verdict=verdict,
        wbgt_c=hour.wbgt_c,
        air_c=hour.air_c,
        relative_humidity_pct=hour.relative_humidity_pct,
        wind_ms=hour.wind_ms,
        limit_low_c=limit.low_c,
        limit_high_c=limit.high_c,
        limit_label=limit.label,
        profile_label=profile.label,
        niosh_category=profile.niosh_category,
        margin_c=margin,
        airflow_adds_heat=hour.airflow_adds_heat,
    )
