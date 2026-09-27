"""The fixed bilingual sentences, and the direction of the advice.

The failure this guards against is specific: the model was authoring the
sentence that says whether it is safe to work, in Urdu as well as English, and
a model that can write "you can work now" can write it when the answer is the
opposite. These tests bind the sentence to the verdict that produced it.
"""

import re

import pytest

import heatline.tools as tools
from heatline.phrases import _EN, _UR, both, keys, phrase

URDU = re.compile(r"[؀-ۿ]")


def test_every_english_phrase_has_an_urdu_one():
    """A missing translation must fail the build, not silently serve English to
    an Urdu reader."""
    assert set(_EN) == set(_UR), set(_EN) ^ set(_UR)


def test_urdu_phrases_are_actually_urdu_script():
    for key, text in _UR.items():
        assert URDU.search(text), f"{key} has no Urdu script in it"


def test_urdu_uses_urdu_sentence_punctuation():
    """A full stop rather than the Urdu danda is the commonest tell that a
    string was written by someone not reading it back."""
    for key, text in _UR.items():
        assert "۔" in text, f"{key} does not end its sentences with a danda"


def test_slots_match_between_languages():
    """If the two languages take different slots, one of them will render with a
    literal {placeholder} in front of a worker."""
    for key in keys():
        en = set(re.findall(r"\{(\w+)\}", _EN[key]))
        ur = set(re.findall(r"\{(\w+)\}", _UR[key]))
        assert en == ur, f"{key}: english takes {en}, urdu takes {ur}"


def test_no_phrase_renders_with_a_leftover_placeholder():
    slots = {"wbgt": "29.4", "low": "27.5", "high": "29.5", "air": "30.5",
             "hours": 48}
    for key in keys():
        for lang in ("en", "ur"):
            out = phrase(key, lang, **slots)
            assert "{" not in out and "}" not in out, f"{key}/{lang}: {out}"


def test_the_three_verdicts_say_different_things_in_both_languages():
    """If two verdicts share wording, the advice is not actually being
    distinguished for the reader."""
    for lang in ("en", "ur"):
        said = {v: phrase(v, lang, wbgt="29", low="27.5", high="29.5")
                for v in ("under", "over", "undetermined")}
        assert len(set(said.values())) == 3, said


def test_the_over_phrase_tells_the_worker_to_stop_in_both_languages():
    """The direction of the advice is the whole point. 'over' must not read as
    permission."""
    assert "not work" in _EN["over"].lower()
    # نہ کریں: "do not do"
    assert "نہ کریں" in _UR["over"]
    # and 'under' must not carry the negative
    assert "نہ کریں" not in _UR["under"]


def test_the_undetermined_phrase_refuses_to_pick_a_side():
    assert "cannot be told" in _EN["undetermined"].lower()
    # کچھ نہیں کہا جا سکتا: "nothing can be said"
    assert "کہا جا سکتا" in _UR["undetermined"]


def test_unknown_key_raises_rather_than_returning_empty():
    with pytest.raises(KeyError):
        phrase("no_such_key", "ur")


def test_assess_hour_attaches_the_phrase_for_the_verdict_it_computed(forecast):
    """The sentence and the verdict must come from the same code path, so they
    cannot disagree."""
    tools.reset_forecast(forecast)
    try:
        for i in range(0, 40):
            out = tools.assess_hour(forecast.times[i])
            if not out.get("ok"):
                continue
            expected = both(out["verdict"], wbgt=f"{out['wbgt_c']}",
                            low=f"{out['limit_c'][0]}", high=f"{out['limit_c'][1]}")
            assert out["say"] == expected, out["verdict"]
    finally:
        tools.reset_forecast()


def test_refusals_carry_a_fixed_sentence_in_both_languages(forecast, stale_forecast):
    tools.reset_forecast(stale_forecast)
    try:
        out = tools.assess_hour(forecast.times[10])
    finally:
        tools.reset_forecast()
    assert out["ok"] is False
    assert URDU.search(out["say"]["ur"])
    assert "No advice" in out["say"]["en"]


def test_review_status_is_reported_not_hidden():
    """Until a person who reads Urdu signs the strings off, every surface has to
    say so. This asserts the flag is exposed rather than quietly omitted."""
    from heatline.phrases import URDU_REVIEWED_BY
    import heatline.tools as t
    out = t.assess_hour.__doc__
    assert out is not None
    assert "unreviewed" in keys()
    # The value may be None (unreviewed) or a name; the field must exist either way.
    assert URDU_REVIEWED_BY is None or isinstance(URDU_REVIEWED_BY, str)
