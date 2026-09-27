"""The three-outcome verdict, especially the third one."""

import pytest

from heatline.band import Verdict, assess
from heatline.limits import limit_interval
from heatline.wbgt import WbgtHour


def _hour(wbgt_c: float, air_c: float = 33.0) -> WbgtHour:
    return WbgtHour(
        time="2026-09-27T14:00",
        wbgt_c=wbgt_c,
        air_c=air_c,
        relative_humidity_pct=65.0,
        wind_ms=4.0,
        shortwave_wm2=800.0,
        cos_solar_zenith=0.9,
        direct_fraction=0.7,
        is_daylight=True,
        airflow_adds_heat=air_c > 35.0,
    )


def test_clearly_below_the_interval_is_under():
    li = limit_interval("delivery_rider", acclimatized=True)
    a = assess(_hour(li.low_c - 3.0))
    assert a.verdict is Verdict.UNDER
    assert a.margin_c is not None and a.margin_c < 0


def test_clearly_above_the_interval_is_over():
    li = limit_interval("delivery_rider", acclimatized=True)
    a = assess(_hour(li.high_c + 3.0))
    assert a.verdict is Verdict.OVER
    assert a.margin_c is not None and a.margin_c > 0


def test_inside_the_interval_is_undetermined_and_carries_no_margin():
    """The behaviour the whole design exists for. Inside the interval, whether
    this rider is over the limit depends on how hard they are actually working.
    A forecast cannot know that, so no margin is reported and the verdict is
    not rounded to a yes or a no."""
    li = limit_interval("delivery_rider", acclimatized=True)
    midpoint = (li.low_c + li.high_c) / 2.0
    a = assess(_hour(midpoint))
    assert a.verdict is Verdict.UNDETERMINED
    assert a.margin_c is None
    assert a.as_dict()["margin_c"] is None


def test_the_interval_edges_are_inclusive_and_undetermined():
    li = limit_interval("delivery_rider", acclimatized=True)
    assert assess(_hour(li.low_c)).verdict is Verdict.UNDETERMINED
    assert assess(_hour(li.high_c)).verdict is Verdict.UNDETERMINED


def test_unacclimatized_is_never_more_permissive():
    """For the same conditions, an unacclimatized worker can never be judged
    safer than an acclimatized one. If this inverts, RAL and REL are swapped."""
    order = {Verdict.UNDER: 0, Verdict.UNDETERMINED: 1, Verdict.OVER: 2}
    for wbgt in (20.0, 25.0, 26.5, 28.0, 29.0, 31.0, 35.0):
        acc = assess(_hour(wbgt), acclimatized=True)
        unacc = assess(_hour(wbgt), acclimatized=False)
        assert order[unacc.verdict] >= order[acc.verdict], wbgt


def test_verdict_is_monotone_in_exposure():
    seen = []
    for wbgt in range(18, 40):
        seen.append(assess(_hour(float(wbgt))).verdict)
    order = {Verdict.UNDER: 0, Verdict.UNDETERMINED: 1, Verdict.OVER: 2}
    ranks = [order[v] for v in seen]
    assert ranks == sorted(ranks)


def test_airflow_flag_is_carried_through_to_the_output():
    assert assess(_hour(30.0, air_c=38.0)).airflow_adds_heat is True
    assert assess(_hour(30.0, air_c=30.0)).airflow_adds_heat is False


def test_unknown_profile_raises_rather_than_guessing():
    with pytest.raises(KeyError):
        assess(_hour(30.0), profile_key="astronaut")
