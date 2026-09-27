"""The tools the agent is given, and the only route to a number.

Every function here is deterministic given its inputs and a forecast. The model
calls them, reads what comes back, and writes prose. It is never asked to
compute, estimate, round or judge a number. The refusal in assess_hour is a
branch in this file, not an instruction in a prompt, because a prompt can be
talked out of a branch.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .band import assess
from .config import (
    DEFAULT_PROFILE,
    KARACHI_TZ,
    PROFILES,
    SKIN_TEMPERATURE_C,
    SUPPORTED_HORIZON_HOURS,
)
from .freshness import check_freshness, check_horizon
from .ingest import ATTRIBUTION, Forecast, fetch_forecast
from .phrases import URDU_REVIEWED_BY, both
from .limits import limit_interval
from .wbgt import wbgt_for_hour

_CACHED: dict[str, Forecast] = {}


def _forecast(refresh: bool = False) -> Forecast:
    if refresh or "f" not in _CACHED:
        _CACHED["f"] = fetch_forecast()
    return _CACHED["f"]


def reset_forecast(forecast: Forecast | None = None) -> None:
    """Test seam: inject a forecast, or clear the cached one."""
    if forecast is None:
        _CACHED.pop("f", None)
    else:
        _CACHED["f"] = forecast


def current_hour_iso(tz: str = KARACHI_TZ) -> str:
    """The current local hour in Karachi, as Open-Meteo formats its timestamps."""
    return datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%dT%H:00")


def resolve_hour(day: str = "today", hour_24: int = 12, tz: str = KARACHI_TZ) -> dict:
    """Turn "tomorrow at 1pm" into an exact timestamp, in code rather than in
    the model.

    This tool exists because of a bug found on 2026-09-27. Asked about 1pm
    tomorrow, the model built the ISO timestamp itself, got the date wrong, and
    was then correctly told by assess_hour that the hour was not in the series.
    The refusal fired, so nothing false was said, but the answer was useless.

    A language model has no reliable clock. Date arithmetic is arithmetic, and
    the rule in this project is that the model does not do arithmetic.

    day accepts "today", "tomorrow" or an explicit YYYY-MM-DD.
    """
    if not 0 <= hour_24 <= 23:
        return {"ok": False, "reason": f"hour_24 must be 0 to 23, got {hour_24}"}

    now = datetime.now(ZoneInfo(tz))
    key = (day or "today").strip().lower()
    if key == "today":
        target = now
    elif key == "tomorrow":
        target = now + timedelta(days=1)
    elif key == "yesterday":
        target = now - timedelta(days=1)
    else:
        try:
            parsed = datetime.strptime(key, "%Y-%m-%d")
        except ValueError:
            return {
                "ok": False,
                "reason": (
                    f"day must be 'today', 'tomorrow' or YYYY-MM-DD, got {day!r}"
                ),
            }
        target = parsed

    return {
        "ok": True,
        "iso_hour": f"{target.strftime('%Y-%m-%d')}T{hour_24:02d}:00",
        "resolved_from": {"day": day, "hour_24": hour_24},
        "timezone": tz,
        "current_hour": now.strftime("%Y-%m-%dT%H:00"),
    }


def data_status() -> dict:
    """How old the data is and how far ahead this tool will answer.

    The agent must call this before advising. If ok is false it must refuse.
    """
    f = _forecast()
    fresh = check_freshness(f)
    return {
        "ok": fresh.ok,
        "reason": fresh.reason,
        "fetch_age_minutes": round(fresh.fetch_age_minutes, 1),
        "max_fetch_age_minutes": fresh.max_fetch_age_minutes,
        "series_first_hour": f.times[0],
        "series_last_hour": f.times[-1],
        "supported_horizon_hours": SUPPORTED_HORIZON_HOURS,
        "current_hour": current_hour_iso(),
        "attribution": ATTRIBUTION,
    }


def exposure_limit(profile_key: str = DEFAULT_PROFILE, acclimatized: bool = True) -> dict:
    """The NIOSH limit for this worker, as an interval in degrees C WBGT."""
    if profile_key not in PROFILES:
        return {"ok": False, "reason": f"unknown profile {profile_key!r}",
                "known": sorted(PROFILES)}
    li = limit_interval(profile_key, acclimatized=acclimatized)
    p = PROFILES[profile_key]
    return {
        "ok": True,
        "limit_low_c": round(li.low_c, 2),
        "limit_high_c": round(li.high_c, 2),
        "label": li.label,
        "equation": (
            "REL = 56.7 - 11.5 log10 M" if acclimatized
            else "RAL = 59.9 - 14.1 log10 M"
        ),
        "metabolic_rate_w": [p.m_low_w, p.m_high_w],
        "niosh_category": p.niosh_category,
        "source": "NIOSH 2016-106 section 8.1",
        "why_an_interval": (
            "The workload is a band, not a point, and NIOSH states that errors "
            "in estimating metabolic rate from energy expenditure tables reach "
            "30 percent. A single limit would imply precision that is not there."
        ),
    }


def assess_hour(
    iso_hour: str | None = None,
    profile_key: str = DEFAULT_PROFILE,
    acclimatized: bool = True,
) -> dict:
    """Assess one hour. Refuses on stale data or beyond the supported horizon.

    Returns a dict whose "ok" field is false when the tool will not advise. The
    agent is instructed to pass the refusal through verbatim rather than work
    around it, and this branch is what makes that instruction enforceable.
    """
    f = _forecast()

    fresh = check_freshness(f)
    if not fresh.ok:
        return {"ok": False, "refusal": "stale_data", "reason": fresh.reason,
                "say": both("refuse_stale"), "urdu_reviewed_by": URDU_REVIEWED_BY}

    iso_hour = iso_hour or current_hour_iso()
    horizon = check_horizon(f, iso_hour)
    if not horizon.ok:
        return {"ok": False, "refusal": "outside_horizon",
                "reason": horizon.reason,
                "say": both("refuse_horizon", hours=SUPPORTED_HORIZON_HOURS),
                "urdu_reviewed_by": URDU_REVIEWED_BY}

    if profile_key not in PROFILES:
        return {"ok": False, "refusal": "unknown_profile",
                "reason": f"unknown profile {profile_key!r}",
                "known": sorted(PROFILES)}

    hour = wbgt_for_hour(f, horizon.requested_hour_offset)
    a = assess(hour, profile_key=profile_key, acclimatized=acclimatized)
    out = {"ok": True, **a.as_dict()}
    out["skin_temperature_c"] = SKIN_TEMPERATURE_C
    out["attribution"] = ATTRIBUTION

    # The sentence that says whether it is safe to work is selected here, by the
    # same code that computed the verdict, and never written by the model.
    d = a.as_dict()
    out["say"] = both(a.verdict.value, wbgt=f"{d['wbgt_c']}",
                      low=f"{d['limit_c'][0]}", high=f"{d['limit_c'][1]}")
    extra = [both("air_note", air=f"{d['air_c']}")]
    if hour.airflow_adds_heat:
        extra.append(both("airflow"))
    out["also"] = extra
    out["urdu_reviewed_by"] = URDU_REVIEWED_BY
    return out


def assess_day(
    profile_key: str = DEFAULT_PROFILE,
    acclimatized: bool = True,
    hours: int = 24,
    from_hour: str | None = None,
) -> dict:
    """Assess a window of hours, for planning a shift.

    Defaults to starting now. from_hour lets a rider ask about a shift that has
    not started yet, which is the more useful question: at eight in the evening,
    "how is right now" is not what anyone needs to know.
    """
    f = _forecast()

    fresh = check_freshness(f)
    if not fresh.ok:
        return {"ok": False, "refusal": "stale_data", "reason": fresh.reason}

    if from_hour is None:
        start = f.index_of(current_hour_iso())
        if start is None:
            return {
                "ok": False,
                "refusal": "current_hour_missing",
                "reason": (
                    f"The current Karachi hour {current_hour_iso()} is not in "
                    f"the forecast series, which runs {f.times[0]} to "
                    f"{f.times[-1]}. This tool will not advise from a series "
                    f"that does not cover now."
                ),
            }
    else:
        horizon = check_horizon(f, from_hour)
        if not horizon.ok:
            return {"ok": False, "refusal": "outside_horizon",
                    "reason": horizon.reason}
        start = horizon.requested_hour_offset

    end = min(start + hours, len(f), SUPPORTED_HORIZON_HOURS)
    if end <= start:
        return {
            "ok": False,
            "refusal": "outside_horizon",
            "reason": (
                f"A window starting at {f.times[start]} has no hours inside the "
                f"{SUPPORTED_HORIZON_HOURS} hour horizon this tool answers for."
            ),
        }

    rows = [
        assess(wbgt_for_hour(f, i), profile_key=profile_key,
               acclimatized=acclimatized).as_dict()
        for i in range(start, end)
    ]
    counts = {"over": 0, "undetermined": 0, "under": 0}
    for r in rows:
        counts[r["verdict"]] += 1
    return {
        "ok": True,
        "from_hour": f.times[start],
        "to_hour": f.times[end - 1],
        "hours": rows,
        "counts": counts,
        "attribution": ATTRIBUTION,
    }


TOOLS = [resolve_hour, data_status, exposure_limit, assess_hour, assess_day]
