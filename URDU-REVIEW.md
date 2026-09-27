# Urdu review sheet

**Eight sentences. That is the whole of the Urdu a worker ever sees.**

This file exists because of a design change. The Urdu used to be written fresh
by the language model on every request, which made it unreviewable: there was no
fixed text to check, and the sentence that says whether it is safe to work could
in principle come out inverted. Those sentences are now templates in
`heatline/phrases.py`, selected by the same code that computes the verdict.

So the review is bounded. Read the eight below, mark anything wrong, and it
stays reviewed.

## How to review

For each one, three questions:

1. **Is the Urdu correct and natural?** Register should be plain and polite, the
   kind a safety notice uses, not literary and not casual.
2. **Does it say the same thing as the English?** Particularly the direction. A
   sentence that reads as permission where the English says stop is the one
   error that could hurt somebody.
3. **Would a delivery rider in Karachi understand it?** "ویٹ بلب گلوب" is a
   transliteration because WBGT has no settled Urdu term. If there is a better
   way to say it, that is the most useful correction on this page.

## When it is signed off

Set `URDU_REVIEWED_BY` in `heatline/phrases.py` to the reviewer's name and the
date. That one change removes the "not yet checked by an Urdu reader" notice
from the live site, the API responses and the write-up. Nothing else needs
editing.

## The sentences

Rendered with example numbers, exactly as a reader sees them.

### under

Shown when exposure is below the limit for any effort level.

**English**

> Safe to work for now. The heat exposure is 30.4 degrees WBGT, below the limit of 27.5 to 29.5 for this kind of work.

**Urdu**

> فی الحال کام کرنا محفوظ ہے۔ گرمی کا دباؤ 30.4 ڈگری ویٹ بلب گلوب ہے، جو اس نوعیت کے کام کی حد 27.5 سے 29.5 سے کم ہے۔

- [ ] Urdu is correct and natural
- [ ] means the same as the English
- [ ] a rider would understand it

Correction, if any:


---

### undetermined

Shown when exposure falls inside the limit band. Must NOT read as a yes or a no.

**English**

> It cannot be told either way. The heat exposure is 30.4 degrees WBGT, inside the limit of 27.5 to 29.5, so whether you are over it depends on how hard you are working. Take breaks and drink water.

**Urdu**

> یقین سے کچھ نہیں کہا جا سکتا۔ گرمی کا دباؤ 30.4 ڈگری ویٹ بلب گلوب ہے، جو حد 27.5 سے 29.5 کے اندر ہے، اس لیے آپ حد سے اوپر ہیں یا نہیں، یہ اس پر ہے کہ آپ کتنی سختی سے کام کر رہے ہیں۔ وقفے لیں اور پانی پیتے رہیں۔

- [ ] Urdu is correct and natural
- [ ] means the same as the English
- [ ] a rider would understand it

Correction, if any:


---

### over

Shown when exposure is above the limit for any effort level. Must read as stop, not as permission.

**English**

> Do not work through this hour without rest breaks. The heat exposure is 30.4 degrees WBGT, above the limit of 27.5 to 29.5 for this kind of work, whatever pace you keep.

**Urdu**

> اس گھنٹے میں بغیر آرام کے کام نہ کریں۔ گرمی کا دباؤ 30.4 ڈگری ویٹ بلب گلوب ہے، جو اس نوعیت کے کام کی حد 27.5 سے 29.5 سے زیادہ ہے، آپ کام کی رفتار کوئی بھی رکھیں۔

- [ ] Urdu is correct and natural
- [ ] means the same as the English
- [ ] a rider would understand it

Correction, if any:


---

### refuse_stale

Shown when the forecast in hand is too old to advise from. No numbers are given.

**English**

> No advice for now. The forecast this service is holding is too old to give a safe answer from.

**Urdu**

> اس وقت کوئی مشورہ نہیں۔ اس سروس کے پاس موجود پیش گوئی اتنی پرانی ہے کہ اس سے محفوظ جواب نہیں دیا جا سکتا۔

- [ ] Urdu is correct and natural
- [ ] means the same as the English
- [ ] a rider would understand it

Correction, if any:


---

### refuse_horizon

Shown when the hour asked about is past the 48 hour cap.

**English**

> No advice for that hour. This service only answers 48 hours ahead, because an hourly heat reading further out than that is a guess.

**Urdu**

> اس گھنٹے کے لیے کوئی مشورہ نہیں۔ یہ سروس صرف 48 گھنٹے آگے تک جواب دیتی ہے، کیونکہ اس سے آگے کی گھنٹہ وار گرمی کی پیمائش محض اندازہ ہے۔

- [ ] Urdu is correct and natural
- [ ] means the same as the English
- [ ] a rider would understand it

Correction, if any:


---

### air_note

Added after the verdict, to stop air temperature being mistaken for the limit.

**English**

> The air temperature is 31.3, which is not the same thing and is not what the limit is set against.

**Urdu**

> ہوا کا درجہ حرارت 31.3 ہے، جو اس سے مختلف چیز ہے اور حد اس پر مقرر نہیں کی جاتی۔

- [ ] Urdu is correct and natural
- [ ] means the same as the English
- [ ] a rider would understand it

Correction, if any:


---

### airflow

Added only when air temperature is above skin temperature.

**English**

> The air is hotter than your skin, so riding faster adds heat instead of cooling you.

**Urdu**

> ہوا آپ کی جلد سے زیادہ گرم ہے، اس لیے تیز چلانے سے ٹھنڈک نہیں بلکہ مزید گرمی ملتی ہے۔

- [ ] Urdu is correct and natural
- [ ] means the same as the English
- [ ] a rider would understand it

Correction, if any:


---

### unreviewed

The disclaimer on the page itself, until this sheet is signed off.

**English**

> The Urdu on this page has not yet been checked by a person who reads Urdu.

**Urdu**

> اس صفحے کی اردو ابھی کسی اردو پڑھنے والے نے جانچی نہیں ہے۔

- [ ] Urdu is correct and natural
- [ ] means the same as the English
- [ ] a rider would understand it

Correction, if any:


---
