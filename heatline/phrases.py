"""The load-bearing sentences, fixed in both languages.

This exists because of a real failure mode. The rest of this project is built on
the model never producing a number, and yet the model was authoring the sentence
that says whether it is safe to work, in Urdu as well as English. A model that
writes "you can work now" can also write it when the answer is the opposite, and
no test catches that because the sentence is generated fresh every time.

So the verdict is a template now. The numbers come from the deterministic layer,
the sentence comes from here, and the model is left with the part where being
slightly loose does no harm: the explanation.

Two consequences worth having:

1. The Urdu becomes checkable. Instead of an unbounded stream of generated
   translation, there are eight fixed sentences. A person who reads Urdu can
   review them once, in a few minutes, and they stay reviewed.
2. The direction of the advice can no longer be wrong. It is selected by the
   same code path that computed the verdict.

REVIEW STATUS: written by a language model and checked by one. That is weaker
than a human reader and is not the same thing. Every surface says so until a
person who reads Urdu signs these off, and `reviewed` below is the single place
that changes when they do.
"""

from __future__ import annotations

# Flip to the reviewer's name and date once a human who reads Urdu has read the
# strings below. Nothing else needs to change: the UI and the API read this.
URDU_REVIEWED_BY: str | None = None

_EN = {
    "under": (
        "Safe to work for now. The heat exposure is {wbgt} degrees WBGT, below "
        "the limit of {low} to {high} for this kind of work."
    ),
    "over": (
        "Do not work through this hour without rest breaks. The heat exposure is "
        "{wbgt} degrees WBGT, above the limit of {low} to {high} for this kind of "
        "work, whatever pace you keep."
    ),
    "undetermined": (
        "It cannot be told either way. The heat exposure is {wbgt} degrees WBGT, "
        "inside the limit of {low} to {high}, so whether you are over it depends "
        "on how hard you are working. Take breaks and drink water."
    ),
    "refuse_stale": (
        "No advice for now. The forecast this service is holding is too old to "
        "give a safe answer from."
    ),
    "refuse_horizon": (
        "No advice for that hour. This service only answers {hours} hours ahead, "
        "because an hourly heat reading further out than that is a guess."
    ),
    "air_note": (
        "The air temperature is {air}, which is not the same thing and is not "
        "what the limit is set against."
    ),
    "airflow": (
        "The air is hotter than your skin, so riding faster adds heat instead of "
        "cooling you."
    ),
    "unreviewed": "The Urdu on this page has not yet been checked by a person who reads Urdu.",
}

# Urdu. Notes for whoever reviews these:
#   - Latin digits are kept for numbers, which is normal in Pakistani Urdu.
#   - "ویٹ بلب گلوب" is a transliteration; there is no settled Urdu term for
#     WBGT, and an English reader is no better served by the acronym.
#   - The imperative register is the plain polite form ("کریں"), which is what a
#     safety notice should use.
_UR = {
    "under": (
        "فی الحال کام کرنا محفوظ ہے۔ گرمی کا دباؤ {wbgt} ڈگری ویٹ بلب گلوب ہے، "
        "جو اس نوعیت کے کام کی حد {low} سے {high} سے کم ہے۔"
    ),
    "over": (
        "اس گھنٹے میں بغیر آرام کے کام نہ کریں۔ گرمی کا دباؤ {wbgt} ڈگری ویٹ بلب "
        "گلوب ہے، جو اس نوعیت کے کام کی حد {low} سے {high} سے زیادہ ہے، آپ کام کی "
        "رفتار کوئی بھی رکھیں۔"
    ),
    "undetermined": (
        "یقین سے کچھ نہیں کہا جا سکتا۔ گرمی کا دباؤ {wbgt} ڈگری ویٹ بلب گلوب ہے، "
        "جو حد {low} سے {high} کے اندر ہے، اس لیے آپ حد سے اوپر ہیں یا نہیں، یہ "
        "اس پر ہے کہ آپ کتنی سختی سے کام کر رہے ہیں۔ وقفے لیں اور پانی پیتے رہیں۔"
    ),
    "refuse_stale": (
        "اس وقت کوئی مشورہ نہیں۔ اس سروس کے پاس موجود پیش گوئی اتنی پرانی ہے کہ "
        "اس سے محفوظ جواب نہیں دیا جا سکتا۔"
    ),
    "refuse_horizon": (
        "اس گھنٹے کے لیے کوئی مشورہ نہیں۔ یہ سروس صرف {hours} گھنٹے آگے تک جواب "
        "دیتی ہے، کیونکہ اس سے آگے کی گھنٹہ وار گرمی کی پیمائش محض اندازہ ہے۔"
    ),
    "air_note": (
        "ہوا کا درجہ حرارت {air} ہے، جو اس سے مختلف چیز ہے اور حد اس پر مقرر نہیں "
        "کی جاتی۔"
    ),
    "airflow": (
        "ہوا آپ کی جلد سے زیادہ گرم ہے، اس لیے تیز چلانے سے ٹھنڈک نہیں بلکہ مزید "
        "گرمی ملتی ہے۔"
    ),
    "unreviewed": "اس صفحے کی اردو ابھی کسی اردو پڑھنے والے نے جانچی نہیں ہے۔",
}


def phrase(key: str, lang: str = "en", **slots) -> str:
    table = _UR if lang == "ur" else _EN
    if key not in table:
        raise KeyError(f"no {lang} phrase for {key!r}")
    return table[key].format(**slots)


def both(key: str, **slots) -> dict[str, str]:
    return {"en": phrase(key, "en", **slots), "ur": phrase(key, "ur", **slots)}


def keys() -> list[str]:
    return sorted(_EN)
