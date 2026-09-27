"""NIOSH heat exposure limits, and why they are an interval.

NIOSH 2016-106, section 8.1, verbatim:

    RAL [degrees C-WBGT] = 59.9 - 14.1 log10 M [W]
    REL [degrees C-WBGT] = 56.7 - 11.5 log10 M [W]

RAL is the Recommended Alert Limit, for unacclimatized workers.
REL is the Recommended Exposure Limit, for acclimatized workers.

M is metabolic rate in watts. NIOSH also states that "Errors in estimating
metabolic rate from energy expenditure tables are reported to be as high as 30%
[ISO 1990]", and Table 5-1 gives moderate work as a range, 234 to 349 W, not a
point. So the limit is a range too, and collapsing it to a midpoint would
manufacture precision. See SOURCES.md sections 3 and 4.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import PROFILES, WorkerProfile


def rel_c(m_watts: float) -> float:
    """Recommended Exposure Limit, acclimatized workers, degrees C WBGT."""
    if m_watts <= 0.0:
        raise ValueError("metabolic rate must be positive")
    return 56.7 - 11.5 * math.log10(m_watts)


def ral_c(m_watts: float) -> float:
    """Recommended Alert Limit, unacclimatized workers, degrees C WBGT."""
    if m_watts <= 0.0:
        raise ValueError("metabolic rate must be positive")
    return 59.9 - 14.1 * math.log10(m_watts)


@dataclass(frozen=True)
class LimitInterval:
    """The limit as a closed interval, because the workload is one.

    A higher metabolic rate gives a lower limit, so the interval runs from the
    limit at the top of the workload band to the limit at the bottom.
    """

    low_c: float
    high_c: float
    acclimatized: bool
    profile_key: str
    m_low_w: float
    m_high_w: float

    @property
    def label(self) -> str:
        return "REL, acclimatized" if self.acclimatized else "RAL, unacclimatized"


def limit_interval(
    profile: WorkerProfile | str = "delivery_rider",
    acclimatized: bool = True,
) -> LimitInterval:
    if isinstance(profile, str):
        profile = PROFILES[profile]
    fn = rel_c if acclimatized else ral_c
    at_high_effort = fn(profile.m_high_w)
    at_low_effort = fn(profile.m_low_w)
    return LimitInterval(
        low_c=min(at_high_effort, at_low_effort),
        high_c=max(at_high_effort, at_low_effort),
        acclimatized=acclimatized,
        profile_key=profile.key,
        m_low_w=profile.m_low_w,
        m_high_w=profile.m_high_w,
    )
