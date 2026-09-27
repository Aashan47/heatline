# Every number in this project, and where it comes from

All opened 2026-09-27. **Nothing here was written from memory.** The rule in
`../04-PROJECT-DESIGN.md` is that a wrong coefficient or threshold in a public tool about heat risk
to labourers is the one error in this project that actually matters, so each formula below is quoted
from its primary document with the URL.

---

## 1. The exposure index: WBGT

**Primary source.** NIOSH, *Criteria for a Recommended Standard: Occupational Exposure to Heat and
Hot Environments*, Revised Criteria 2016. DHHS (NIOSH) Publication No. 2016-106.
`https://www.cdc.gov/niosh/docs/2016-106/pdfs/2016-106.pdf`

Verbatim, from its measurement chapter:

> "the calculation of the WBGT for outdoors is
>
>     WBGT = 0.7tnwb + 0.2tg + 0.1ta."

and for indoors, `WBGT = 0.7tnwb + 0.3tg`.

Where, also verbatim from the same document's definitions:

- `tnwb` is the **natural wet bulb** temperature, "The wet bulb temperature under conditions of the
  prevailing air movement"
- `tg` is the **globe** temperature, "The temperature inside a blackened, hollow, thin copper globe"
- `ta` is air temperature

**The problem this creates.** Two of the three inputs are physical measurements from instruments at
the worksite. **A weather forecast provides none of them.** This is the single biggest technical
obstacle in the project and it was invisible until the document was opened.

---

## 2. Getting WBGT from forecast variables: Liljegren

**Method.** Liljegren et al. (2008), "Modeling the wet bulb globe temperature using standard
meteorological measurements", *Journal of Occupational and Environmental Hygiene*. The globe and
natural-wet-bulb temperatures are each solved from their steady-state energy balance rather than
approximated by regression.

**Implementation used, rather than reimplemented.** `thermofeel` 2.3.0, from ECMWF,
`calculate_wbgt_liljegren`. Its own docstring, verbatim:

> "Physically based WBGT after Liljegren et al. (2008), the method used operationally by KNMI. The
> globe and natural-wet-bulb temperatures are each solved from their steady-state energy balance by
> fixed-point iteration and combined with the air t[emperature]"

Inputs it requires: 2m temperature (K), relative humidity (%), surface pressure (hPa), 10m wind
(m/s), downward shortwave radiation (W/m2), the direct-beam fraction of that radiation, and the
cosine of the solar zenith angle.

**Why a library and not our own code.** Reimplementing an iterative energy-balance solver from a
paywalled paper, for a public tool about occupational risk, is how a wrong number gets shipped. A
maintained implementation from a national meteorological service is the defensible choice, and it is
cited in the write-up rather than hidden.

**Licence, resolved 2026-09-27.** The installed package metadata carried no licence field, so it was
checked at source: `github.com/ecmwf/thermofeel` reports `Apache-2.0` via the GitHub API, and its
`LICENSE` file is the Apache License 2.0 text. Permits this use, with attribution.

---

## 3. The exposure limits

**Primary source.** The same NIOSH 2016-106, section 8.1 "The NIOSH RALs and RELs". Verbatim:

> "The RALs and RELs are represented by the following equations, where M represents the metabolic
> rate in Watts (W):
>
>     RAL [°C-WBGT] = 59.9 − 14.1 log10 M [W]
>
>     REL [°C-WBGT] = 56.7 − 11.5 log10 M [W]"

- **RAL**, Recommended Alert Limit, is for **unacclimatized** workers
- **REL**, Recommended Exposure Limit, is for **acclimatized** workers

These are closed-form and continuous, which is better than a lookup table: the limit moves with the
workload instead of snapping between categories.

**Cross-check, and it passes.** NIOSH Table 5-1 states the moderate-workload WBGT limit for
acclimatized workers as **28°C (82.4°F)**, for the band 201 to 300 kcal/h (234 to 349 W). The
equation at M = 300 W gives **28.21°C**. Agreement to 0.21°C between a table and an equation in the
same document is the cheapest available validation of the implementation, and it is acceptance test 2
in `../04-PROJECT-DESIGN.md`.

---

## 4. The workload, and its honest error bar

NIOSH Table 5-1, moderate workload: **201 to 300 kcal/h, which the table gives as 234 to 349 W.**

On how good any such estimate is, verbatim from the same document:

> "Errors in estimating metabolic rate from energy expenditure tables are reported to be as high as
> 30% [ISO 1990]."

**This is load-bearing, not a caveat.** A 30% error in M propagates through `56.7 - 11.5 log10 M`.
Computed rather than estimated: over 234 to 349 W the REL runs from **29.45 °C down to 27.46 °C**, a
**2.0 °C spread in the limit itself**, before any forecast error is counted. **So the output cannot
honestly be a single number, and the band-and-refusal design is forced by the arithmetic rather than
chosen as a style.**

An earlier draft of this file put that spread at 1.5 °C from a figure worked out in the head. The
code disagreed, and the code was right. It is corrected here rather than quietly, because the habit
of checking is the point.

---

## 5. Airflow above skin temperature, which is the counterintuitive part

Verbatim from NIOSH 2016-106, on controlling convective heat exchange:

> "as long as ta exceeds t sk, air speed should be reduced to levels that will still permit sweat to
> evaporate freely but will reduce convective heat gain"

Read plainly: **once air temperature exceeds skin temperature, moving air through it adds heat rather
than removing it.** For a motorcycle rider this inverts the intuition that riding faster cools you
down. Karachi exceeds skin temperature routinely in summer.

This is the one thing the tool can tell a rider that is both true and not obvious, and it comes from
the standard rather than from us.

---

## 6. The weather data

**Open-Meteo forecast API.** `https://api.open-meteo.com/v1/forecast`, no key, no auth.

Licence, verbatim from `https://open-meteo.com/en/terms`:

> "Non-Commercial Use By using the Free API for non-commercial use you agree to following terms: Less
> than 10'000 API calls per day, 5'000 per hour and 600 per minute. You may only use the free API
> services for non-commercial purposes. You accept to the CC-BY 4.0 licence"

**CC-BY 4.0 attribution is required** and goes in this README, the app response and the blog post.

**Units trap, found and handled.** Open-Meteo returns `wind_speed_10m` in **km/h**, while Liljegren
wants **m/s**. Feeding km/h straight in would have silently understated the heat load by inflating
the cooling term. Converted at the boundary, with the factor named in the code.

**`cossza` without any solar-geometry code.** Open-Meteo returns both `direct_radiation` (on the
horizontal) and `direct_normal_irradiance` (on the beam normal), and direct horizontal equals DNI
times the cosine of the solar zenith angle. So `cossza = direct_radiation / direct_normal_irradiance`,
guarded for night when both are zero. Verified on live data: the derived values land in
[0.000, 0.892] over 48 hours, which is the range the geometry requires. Using the provider's own two
fields keeps this self-consistent instead of introducing a second sun model that could disagree
with the radiation we were given.

---

## 7. The heat index, and why it does not drive anything

**Primary source.** Rothfusz, L.P., 1990. *The Heat Index "Equation" (or, More Than You Ever Wanted
to Know About Heat Index)*. SR 90-23, Technical Attachment, NWS Southern Region Headquarters, Fort
Worth, TX, 1 July 1990. `https://www.weather.gov/media/ffc/ta_htindx.PDF`

Verbatim:

>     HI = -42.379 + 2.04901523T + 10.14333127R - 0.22475541TR - 6.83783x10-3T2
>          - 5.481717x10-2R2 + 1.22874x10-3T2R + 8.5282x10-4TR2 - 1.99x10-6T2R2
>
>     where T = ambient dry bulb temperature (°F)
>           R = relative humidity (integer percentage).

and on its accuracy:

> "Because this equation is obtained by multiple regression analysis, the heat index value (HI) has an
> error of ±1.3°F."

Confirmed independently against the NWS El Paso calculation document,
`https://www.weather.gov/media/epz/wxcalc/heatIndex.pdf`, which states the same nine coefficients.

### Two reasons it is a secondary display number only

1. **Unit mismatch with the limits.** The NIOSH RAL and REL are defined in **°C-WBGT**. The heat index
   is an apparent temperature in °F on a different scale entirely. Computing a heat index and then
   comparing it to a WBGT threshold would be a category error producing confident, wrong advice. **This
   is exactly the failure mode flagged as the project's highest risk, and reading the sources is what
   caught it.**
2. **Its assumptions are not a rider's.** Rothfusz lists the model's fixed assumptions, verbatim
   including: "Activity. Determines metabolic output. (180 W m-2 of skin area for the model person
   walking outdoors at a speed of 3.1 mph)", "Effective wind speed. ... (5 kts)", and "Clothing cover.
   Long trousers and short-sleeved shirt is assumed. (84% coverage)". A motorcycle courier in Karachi
   matches none of the three. The document is candid about this: "No true equation for the Heat Index
   exists."

The unsourced part is the NWS operational low and high humidity **adjustments**, plus the rule about
averaging with a simpler formula below 80°F. Those live on
`https://www.wpc.ncep.noaa.gov/html/heatindex_equation.html`, which returns **HTTP 404** as of
2026-09-27 and has **no Wayback Machine snapshot** (the availability API returns
`"archived_snapshots": {}`). Neither NWS PDF above carries them. **So they are not implemented**, and
since the heat index is display-only here, nothing depends on them.

---

## 7b. The model, and the quota that shaped the choice

Findings from 2026-09-27, all by trying them rather than reading about them.

| Model | Result with this key |
|---|---|
| `gemini-flash-latest` | works, and resolves to **`gemini-3.8-flash`**, whose free tier allows **5 requests per minute** |
| `gemini-2.5-flash` | **HTTP 404**: "This model models/gemini-2.5-flash is no longer available to new users" |
| `gemini-3.8-flash` | intermittent **HTTP 503**, "currently experiencing high demand" |
| `gemini-flash-lite-latest` | works |
| **`gemini-3.1-flash-lite`** | **works, and is pinned. Chosen.** |

Three reasons for pinning `gemini-3.1-flash-lite`:

1. **One agent answer costs several model calls**, because every tool round trip is a separate call.
   Against a 5-per-minute ceiling, a single question could exhaust the minute. The observed 429 named
   its own quota: `GenerateRequestsPerMinutePerProjectPerModel-FreeTier`, `quotaValue: 5`.
2. **A moving alias means a recorded demo can stop matching the code.** A pinned version is
   reproducible, which matters when the deliverable is a video.
3. **Flash-lite is the right size for the work.** This model narrates and translates a small JSON
   object. It is never asked to reason about a number.

The service retries on 429 and 503, **honouring the `retryDelay` the API returns** rather than
guessing an interval, and then fails with an honest 503 rather than half an answer. The deterministic
endpoints are unaffected by any of this, which is the benefit of having kept them separate.

## 8. What the first live run actually showed

Full output in `probes/out/wbgt_probe_2026-09-27.txt`. Karachi, 24.8607 N 67.0011 E, 48 hours from
2026-09-27.

| | |
|---|---|
| Peak air temperature | **31.3 °C** at 13:00 |
| Peak WBGT (Liljegren) | **30.4 °C** |
| REL interval, moderate work, acclimatized | **27.46 to 29.45 °C** |
| RAL interval, moderate work, unacclimatized | 24.05 to 26.49 °C |
| Hours clearly **over** the whole interval | **six consecutive**, 11:00 to 16:00 |
| Hours **undetermined**, inside the interval | two more, 09:00 and 10:00, then 17:00 |

**31 degrees is a number nobody warns about, and the exposure behind it is above the occupational
limit for moderate work for six straight hours. In late September, not peak summer.**

### The honest count, and why it is lower than the first draft said

An early probe compared WBGT against the **point** REL for M = 300 W, 28.2 °C, and counted eight
hours over. Against the full limit **interval**, the count is **six clearly over and two that cannot
be called**. Over a 48 hour series the interval treatment reclassified **ten hours from a confident
verdict to "cannot tell"**.

The lower number is the true one. This is the design working as intended rather than a result getting
worse: the point estimate was asserting a precision that the metabolic-rate error does not support.

**Not yet claimed anywhere, and not to be claimed until checked:** anything about the 2015 Karachi
heatwave, its mortality, or the sea-breeze mechanism. Those need primary sources of their own before
they enter the post. See `../05-WRITE-UP-AND-VIDEO.md`.
