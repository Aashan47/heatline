"""Fixed inputs: the place, the worker, and the limits of what we will answer.

Sources for every value are in SOURCES.md. Nothing here is tuned to make a demo
look good.
"""

import os
from dataclasses import dataclass

# Karachi. Coordinates are the city centre, which is what a citywide forecast
# can honestly support. The tool does not claim neighbourhood resolution.
KARACHI_LAT = 24.8607
KARACHI_LON = 67.0011
KARACHI_TZ = "Asia/Karachi"

# How far ahead we will answer. Open-Meteo serves more than this. The cap is
# ours, not the provider's, and it is set because an hourly heat advisory two
# days out is a forecast of a forecast. Beyond this the agent refuses.
SUPPORTED_HORIZON_HOURS = 48

# How old our own copy of the forecast may be before we refuse to use it.
# Open-Meteo's forecast endpoint does not publish a model initialisation time,
# so this is the age of our fetch, not the age of the model run. Said plainly
# because the difference matters and pretending otherwise would be dishonest.
#
# Overridable so the refusal can be demonstrated honestly: set it to 0 and any
# forecast is too old, which makes the real code path fire on real data. That is
# a configuration change, not a mocked response.
MAX_FETCH_AGE_MINUTES = int(os.environ.get("HEATLINE_MAX_FETCH_AGE_MINUTES", "90"))

# Skin temperature, above which moving air adds heat instead of removing it.
# NIOSH 2016-106: "as long as ta exceeds t sk, air speed should be reduced to
# levels that will still permit sweat to evaporate freely but will reduce
# convective heat gain". 35 C is the conventional working value for clothed
# skin under heat stress; it is a round number and is treated as approximate.
SKIN_TEMPERATURE_C = 35.0


@dataclass(frozen=True)
class WorkerProfile:
    """A worker, described by the metabolic rate their work implies.

    m_low_w and m_high_w bracket the workload category from NIOSH 2016-106
    Table 5-1. The bracket is carried through the whole calculation rather than
    collapsed to a midpoint, because NIOSH states that "Errors in estimating
    metabolic rate from energy expenditure tables are reported to be as high as
    30% [ISO 1990]". A single number would imply precision that is not there.
    """

    key: str
    label: str
    # NIOSH Table 5-1 workload category this sits in.
    niosh_category: str
    m_low_w: float
    m_high_w: float
    notes: str


# NIOSH 2016-106 Table 5-1, moderate workload row: "201-300 kcal/h", which the
# table itself gives as "(234-349 W)". Those watt figures are quoted from the
# table rather than converted by us.
MODERATE_M_LOW_W = 234.0
MODERATE_M_HIGH_W = 349.0

PROFILES = {
    "delivery_rider": WorkerProfile(
        key="delivery_rider",
        label="motorcycle delivery rider",
        niosh_category="moderate (NIOSH Table 5-1, 201-300 kcal/h, 234-349 W)",
        m_low_w=MODERATE_M_LOW_W,
        m_high_w=MODERATE_M_HIGH_W,
        notes=(
            "Riding is moderate work with variable air movement. The rider is "
            "not in the still air a fixed worksite measurement assumes, and the "
            "airflow they do get reverses sign above skin temperature."
        ),
    ),
}

DEFAULT_PROFILE = "delivery_rider"
