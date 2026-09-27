"""Resolve the Gemini API key from the environment.

Order: GOOGLE_API_KEY, which is what ADK and google-genai document, then
GEMINI_API_KEY, then GEMENI_AI_BUILDER_API_KEY. The third spelling exists
because that is what the key is called where this was developed. No file path
is searched: the key is passed in by the environment, never read out of this
repository.
"""

from __future__ import annotations

import os

NAMES = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMENI_AI_BUILDER_API_KEY")


def resolve_api_key(env: dict | None = None) -> str | None:
    env = os.environ if env is None else env
    for name in NAMES:
        value = (env.get(name) or "").strip()
        if value:
            return value
    return None


def ensure_google_api_key(env: dict | None = None) -> bool:
    """Copy whichever name is set into GOOGLE_API_KEY, which is what ADK reads."""
    key = resolve_api_key(env)
    if not key:
        return False
    os.environ["GOOGLE_API_KEY"] = key
    return True
