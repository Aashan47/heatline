"""The limits, against the document they come from."""

import math

import pytest

from heatline.limits import limit_interval, ral_c, rel_c


def test_rel_reproduces_the_niosh_table_for_moderate_work():
    """NIOSH 2016-106 Table 5-1 gives 28 C for moderate work, acclimatized.

    The REL equation in section 8.1 of the same document must agree. An
    equation and a table in one document disagreeing would mean we have
    transcribed one of them wrongly, which is the error this project most
    needs to avoid.
    """
    assert rel_c(300) == pytest.approx(28.0, abs=0.3)


def test_ral_is_stricter_than_rel_at_every_workload():
    """Unacclimatized workers get a lower ceiling. If this inverts, the two
    equations have been swapped."""
    for m in (120, 234, 300, 349, 465, 580):
        assert ral_c(m) < rel_c(m)


def test_limit_falls_as_workload_rises():
    assert rel_c(234) > rel_c(349)
    assert ral_c(234) > ral_c(349)


def test_equations_match_their_published_form():
    for m in (150.0, 275.5, 400.0):
        assert rel_c(m) == pytest.approx(56.7 - 11.5 * math.log10(m), abs=1e-9)
        assert ral_c(m) == pytest.approx(59.9 - 14.1 * math.log10(m), abs=1e-9)


def test_zero_or_negative_metabolic_rate_raises():
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            rel_c(bad)
        with pytest.raises(ValueError):
            ral_c(bad)


def test_interval_spans_the_workload_band_and_is_ordered():
    li = limit_interval("delivery_rider", acclimatized=True)
    assert li.low_c < li.high_c
    assert li.low_c == pytest.approx(rel_c(349.0), abs=1e-9)
    assert li.high_c == pytest.approx(rel_c(234.0), abs=1e-9)


def test_interval_is_wide_enough_to_matter():
    """If the interval were narrow, the undetermined verdict would be
    decoration. It is about 2 C, which is wider than the difference between a
    comfortable hour and an unsafe one."""
    li = limit_interval("delivery_rider", acclimatized=True)
    assert li.high_c - li.low_c > 1.5
