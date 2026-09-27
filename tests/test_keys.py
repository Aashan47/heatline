"""Key resolution order, and that no key is read from the repository."""

from pathlib import Path

from heatline.keys import NAMES, resolve_api_key


def test_documented_name_wins():
    env = {"GOOGLE_API_KEY": "first", "GEMENI_AI_BUILDER_API_KEY": "third"}
    assert resolve_api_key(env) == "first"


def test_falls_back_through_the_other_names():
    assert resolve_api_key({"GEMINI_API_KEY": "second"}) == "second"
    assert resolve_api_key({"GEMENI_AI_BUILDER_API_KEY": "third"}) == "third"


def test_blank_is_treated_as_absent():
    assert resolve_api_key({"GOOGLE_API_KEY": "   "}) is None


def test_missing_returns_none_rather_than_raising():
    assert resolve_api_key({}) is None


def test_order_is_the_documented_one():
    assert NAMES[0] == "GOOGLE_API_KEY"


def test_no_env_file_is_committed():
    """The repository must never carry a key. gitignore is not enough on its
    own, so assert the file is absent as well."""
    root = Path(__file__).resolve().parent.parent
    assert not (root / ".env").exists()
    assert ".env" in (root / ".gitignore").read_text()
