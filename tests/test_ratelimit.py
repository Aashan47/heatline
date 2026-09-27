"""The cap on the one endpoint that spends money."""

import pytest

from heatline.ratelimit import RateLimiter, client_key


def test_allows_up_to_the_limit_then_refuses():
    rl = RateLimiter(limit=3, window_seconds=60)
    for i in range(3):
        allowed, remaining, retry = rl.check("1.2.3.4", now=1000 + i)
        assert allowed is True
        assert remaining == 2 - i
        assert retry == 0
    allowed, remaining, retry = rl.check("1.2.3.4", now=1003)
    assert allowed is False
    assert remaining == 0
    assert 0 < retry <= 61


def test_the_window_frees_up():
    rl = RateLimiter(limit=2, window_seconds=60)
    assert rl.check("a", now=1000)[0]
    assert rl.check("a", now=1001)[0]
    assert rl.check("a", now=1002)[0] is False
    # Past the window, the earliest hits have expired.
    assert rl.check("a", now=1065)[0] is True


def test_clients_are_counted_separately():
    """If this failed, one visitor would exhaust the cap for everyone."""
    rl = RateLimiter(limit=1, window_seconds=60)
    assert rl.check("a", now=1000)[0] is True
    assert rl.check("b", now=1000)[0] is True
    assert rl.check("a", now=1000)[0] is False


def test_retry_after_counts_down():
    rl = RateLimiter(limit=1, window_seconds=100)
    rl.check("a", now=1000)
    _, _, early = rl.check("a", now=1010)
    _, _, late = rl.check("a", now=1090)
    assert early > late >= 1


def test_client_key_reads_the_forwarded_address():
    """Cloud Run terminates TLS, so without this every request looks like it
    came from the load balancer."""
    assert client_key({"x-forwarded-for": "9.9.9.9, 10.0.0.1"}, "10.0.0.1") == "9.9.9.9"
    assert client_key({"x-forwarded-for": "  9.9.9.9  "}, None) == "9.9.9.9"


def test_client_key_falls_back_to_the_socket_then_to_a_constant():
    assert client_key({}, "127.0.0.1") == "127.0.0.1"
    assert client_key({}, None) == "unknown"


def test_the_table_does_not_grow_without_bound():
    """A client that never returns must not keep its slot for ever. Cloud Run
    instances live long enough for that to matter."""
    rl = RateLimiter(limit=1, window_seconds=1, max_keys=100)
    for i in range(5000):
        rl.check(f"ip-{i}", now=1000 + i)
    assert len(rl._hits) <= 101, len(rl._hits)


def test_sweeping_never_frees_a_client_still_inside_its_window():
    """The sweep must only drop expired entries, or it would silently reset
    someone's cap."""
    rl = RateLimiter(limit=1, window_seconds=600, max_keys=10)
    assert rl.check("victim", now=1000)[0] is True
    for i in range(50):
        rl.check(f"other-{i}", now=1001 + i)
    # Still inside its 600s window, so still capped.
    assert rl.check("victim", now=1100)[0] is False
