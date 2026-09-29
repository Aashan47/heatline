"""The in-memory forecast must expire.

It did not. The deployed service held one fetch for 37 hours and refused every
request for 36 of them, because the tool will not advise on data older than 90
minutes. Every test and every recording runs for minutes, so nothing here
caught it. These tests run the clock forward instead.
"""

import time

import pytest

from heatline import tools
from heatline.ingest import CACHE_TTL_SECONDS


@pytest.fixture(autouse=True)
def clean():
    tools.reset_forecast()
    yield
    tools.reset_forecast()


def test_a_fresh_memo_is_not_refetched(monkeypatch, forecast_factory):
    calls = []

    def fetch():
        calls.append(1)
        return forecast_factory(fetched_at=time.time())

    monkeypatch.setattr(tools, "fetch_forecast", fetch)
    tools._forecast()
    tools._forecast()
    assert len(calls) == 1


def test_a_stale_memo_is_refetched(monkeypatch, forecast_factory):
    """The whole bug in one test."""
    old = forecast_factory(fetched_at=time.time() - CACHE_TTL_SECONDS - 1)
    fresh = forecast_factory(fetched_at=time.time())
    served = [old, fresh]

    monkeypatch.setattr(tools, "fetch_forecast", lambda: served.pop(0))
    first = tools._forecast()
    assert first is old
    second = tools._forecast()
    assert second is fresh, "a memo older than the cache TTL was served again"


def test_age_is_measured_from_the_fetch_not_from_the_memo(
        monkeypatch, forecast_factory):
    """A copy served out of the disk cache must not get a fresh lifetime."""
    from_disk = forecast_factory(fetched_at=time.time() - CACHE_TTL_SECONDS - 1)
    newer = forecast_factory(fetched_at=time.time())
    served = [from_disk, newer]
    monkeypatch.setattr(tools, "fetch_forecast", lambda: served.pop(0))

    tools._forecast()
    assert tools._forecast() is newer


def test_a_failed_refetch_keeps_serving_the_old_forecast(
        monkeypatch, forecast_factory):
    """Open-Meteo being unreachable is not a 500. The age refusal covers it."""
    old = forecast_factory(fetched_at=time.time() - CACHE_TTL_SECONDS - 1)
    calls = []

    def fetch():
        if not calls:
            calls.append(1)
            return old
        raise RuntimeError("open-meteo unreachable")

    monkeypatch.setattr(tools, "fetch_forecast", fetch)
    assert tools._forecast() is old
    assert tools._forecast() is old


def test_the_first_fetch_failing_is_still_an_error(monkeypatch):
    def fetch():
        raise RuntimeError("open-meteo unreachable")

    monkeypatch.setattr(tools, "fetch_forecast", fetch)
    with pytest.raises(RuntimeError):
        tools._forecast()
