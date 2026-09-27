"""The cache that stops an identical question spending quota twice."""

from heatline.advicecache import AdviceCache


def answer(text="over the limit"):
    return {"answer": text, "tools_called": ["assess_hour"]}


def test_a_hit_returns_what_was_stored():
    c = AdviceCache(ttl_seconds=100)
    k = AdviceCache.key("Can I work at 1pm?", "rider", True)
    assert c.get(k) is None
    c.put(k, answer())
    assert c.get(k) == answer()


def test_whitespace_and_case_do_not_change_an_answer_so_they_share_a_key():
    a = AdviceCache.key("Can I work  at 1pm?", "rider", True)
    b = AdviceCache.key("can i work at 1pm?", "rider", True)
    assert a == b


def test_anything_that_changes_the_answer_changes_the_key():
    base = AdviceCache.key("Can I work at 1pm?", "rider", True)
    assert AdviceCache.key("Can I work at 2pm?", "rider", True) != base
    assert AdviceCache.key("Can I work at 1pm?", "labourer", True) != base
    assert AdviceCache.key("Can I work at 1pm?", "rider", False) != base


def test_an_entry_cannot_outlive_its_ttl():
    c = AdviceCache(ttl_seconds=600)
    k = AdviceCache.key("q", "rider", True)
    c.put(k, answer(), now=1000.0)
    assert c.get(k, now=1000.0 + 599) == answer()
    assert c.get(k, now=1000.0 + 600) is None
    # And the expired entry is gone rather than merely hidden.
    assert len(c) == 0


def test_the_cache_does_not_grow_without_bound():
    c = AdviceCache(ttl_seconds=600, max_entries=8)
    for i in range(50):
        c.put(AdviceCache.key(f"q{i}", "rider", True), answer(str(i)),
              now=1000.0)
    assert len(c) == 8
    # The most recent survive, which is what a demo asking the same two
    # questions repeatedly needs.
    assert c.get(AdviceCache.key("q49", "rider", True), now=1000.0) is not None
    assert c.get(AdviceCache.key("q0", "rider", True), now=1000.0) is None


def test_expired_entries_are_dropped_before_live_ones_are_evicted():
    c = AdviceCache(ttl_seconds=10, max_entries=2)
    c.put(AdviceCache.key("old", "rider", True), answer("old"), now=0.0)
    c.put(AdviceCache.key("live", "rider", True), answer("live"), now=100.0)
    c.put(AdviceCache.key("new", "rider", True), answer("new"), now=100.0)
    # "old" expired, so it should have gone first and left both live entries.
    assert c.get(AdviceCache.key("live", "rider", True), now=100.0) is not None
    assert c.get(AdviceCache.key("new", "rider", True), now=100.0) is not None
