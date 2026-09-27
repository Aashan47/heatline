"""The refusals. These are the behaviour the project is actually about.

Each is a branch in heatline/tools.py, not a line in a prompt, so no model
output is needed to prove it fires.
"""

import heatline.tools as tools
from heatline.config import MAX_FETCH_AGE_MINUTES, SUPPORTED_HORIZON_HOURS


def test_stale_data_refuses_and_returns_no_numbers(stale_forecast):
    """Acceptance test 4. A stale forecast must produce a refusal, and the
    refusal must not leak a figure a caller could mistake for advice."""
    tools.reset_forecast(stale_forecast)
    try:
        out = tools.assess_hour("2026-09-27T14:00")
    finally:
        tools.reset_forecast()

    assert out["ok"] is False
    assert out["refusal"] == "stale_data"
    assert str(MAX_FETCH_AGE_MINUTES) in out["reason"]
    for leaked in ("wbgt_c", "verdict", "limit_c", "margin_c"):
        assert leaked not in out


def test_stale_data_also_refuses_a_whole_day(stale_forecast):
    tools.reset_forecast(stale_forecast)
    try:
        out = tools.assess_day()
    finally:
        tools.reset_forecast()
    assert out["ok"] is False and out["refusal"] == "stale_data"
    assert "hours" not in out


def test_beyond_horizon_refuses_and_says_the_cap_is_ours(forecast):
    """Acceptance test 5. The forecast contains the hour; we decline anyway,
    and the reason says the limit is this tool's own."""
    beyond = forecast.times[SUPPORTED_HORIZON_HOURS + 2]
    tools.reset_forecast(forecast)
    try:
        out = tools.assess_hour(beyond)
    finally:
        tools.reset_forecast()

    assert out["ok"] is False
    assert out["refusal"] == "outside_horizon"
    assert "not Open-Meteo" in out["reason"]
    assert "wbgt_c" not in out


def test_hour_absent_from_the_series_refuses(forecast):
    tools.reset_forecast(forecast)
    try:
        out = tools.assess_hour("1999-01-01T12:00")
    finally:
        tools.reset_forecast()
    assert out["ok"] is False and out["refusal"] == "outside_horizon"


def test_unknown_profile_refuses_and_lists_what_it_knows(forecast):
    tools.reset_forecast(forecast)
    try:
        out = tools.assess_hour(forecast.times[14], profile_key="astronaut")
    finally:
        tools.reset_forecast()
    assert out["ok"] is False and out["refusal"] == "unknown_profile"
    assert "delivery_rider" in out["known"]


def test_inside_the_horizon_does_answer(forecast):
    """The refusals must not be so eager that nothing works."""
    tools.reset_forecast(forecast)
    try:
        out = tools.assess_hour(forecast.times[14])
    finally:
        tools.reset_forecast()
    assert out["ok"] is True
    assert out["verdict"] in ("under", "over", "undetermined")
    assert "Open-Meteo" in out["attribution"]


def test_day_reports_counts_that_sum_to_the_rows(forecast):
    tools.reset_forecast(forecast)
    try:
        out = tools.assess_day(hours=12)
    finally:
        tools.reset_forecast()
    if out["ok"]:
        assert sum(out["counts"].values()) == len(out["hours"])


def test_data_status_exposes_the_age_and_the_horizon(forecast):
    tools.reset_forecast(forecast)
    try:
        s = tools.data_status()
    finally:
        tools.reset_forecast()
    assert s["ok"] is True
    assert s["supported_horizon_hours"] == SUPPORTED_HORIZON_HOURS
    assert s["max_fetch_age_minutes"] == MAX_FETCH_AGE_MINUTES


def test_resolve_hour_does_the_date_arithmetic_the_model_got_wrong():
    """Regression test for the bug found on 2026-09-27: the model composed an
    ISO timestamp for "1pm tomorrow" and got the date wrong."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from heatline.config import KARACHI_TZ

    now = datetime.now(ZoneInfo(KARACHI_TZ))

    today = tools.resolve_hour("today", 13)
    assert today["ok"] is True
    assert today["iso_hour"] == f"{now.strftime('%Y-%m-%d')}T13:00"

    tomorrow = tools.resolve_hour("tomorrow", 13)
    expected = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    assert tomorrow["iso_hour"] == f"{expected}T13:00"


def test_resolve_hour_accepts_an_explicit_date():
    out = tools.resolve_hour("2026-09-28", 13)
    assert out["ok"] is True and out["iso_hour"] == "2026-09-28T13:00"


def test_resolve_hour_rejects_bad_input_rather_than_guessing():
    for bad_hour in (-1, 24, 99):
        out = tools.resolve_hour("today", bad_hour)
        assert out["ok"] is False and "0 to 23" in out["reason"]
    out = tools.resolve_hour("next tuesday-ish", 13)
    assert out["ok"] is False and "YYYY-MM-DD" in out["reason"]


def test_resolve_hour_pads_single_digit_hours():
    assert tools.resolve_hour("today", 9)["iso_hour"].endswith("T09:00")
    assert tools.resolve_hour("today", 0)["iso_hour"].endswith("T00:00")


def test_day_accepts_a_named_start_hour(forecast):
    """A rider at eight in the evening wants tomorrow's shift, not right now."""
    tools.reset_forecast(forecast)
    try:
        out = tools.assess_day(hours=6, from_hour=forecast.times[9])
    finally:
        tools.reset_forecast()
    assert out["ok"] is True
    assert out["from_hour"] == forecast.times[9]
    assert len(out["hours"]) == 6


def test_day_refuses_a_start_hour_beyond_the_horizon(forecast):
    tools.reset_forecast(forecast)
    try:
        out = tools.assess_day(from_hour=forecast.times[SUPPORTED_HORIZON_HOURS + 1])
    finally:
        tools.reset_forecast()
    assert out["ok"] is False and out["refusal"] == "outside_horizon"


def test_day_window_is_clipped_to_the_horizon(forecast):
    """A 24 hour window starting near the horizon must not run past it."""
    tools.reset_forecast(forecast)
    try:
        out = tools.assess_day(hours=24, from_hour=forecast.times[SUPPORTED_HORIZON_HOURS - 3])
    finally:
        tools.reset_forecast()
    assert out["ok"] is True
    assert len(out["hours"]) == 3
