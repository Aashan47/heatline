# heatline

**Is an outdoor worker in Karachi over the occupational heat limit right now?**

### Live: https://heat.aashanjaved.com

Open it on a phone. The verdict, the readings and the hour by hour view need no API key and are not
rate limited. The agent is capped at five questions an hour per visitor, because each one spends the
deployer's Gemini quota.

On 27 September 2026, air temperature in Karachi peaked at **31.3 °C**. Nothing warns anyone about
31 degrees. Computed properly, the occupational heat exposure that afternoon peaked at **30.4 °C
WBGT**, which is above the NIOSH exposure limit for moderate work for **six consecutive hours**, with
two more hours where it cannot be determined either way. In late September, not peak summer.

That gap between the thermometer and the exposure is what this tool measures, for one worker group
in one city.

## Why WBGT and not "feels like"

Pakistan's own post-mortem of the June 2015 Karachi heatwave, which the Ministry of Climate Change
records as having "took more than 1200 human lives", notes that the maximum temperature was 44.8 °C
while the heat index was around 66 °C, "because of low air pressure and wind speed and very high
humidity". The report's own recommendation is a heat-health warning system.

Air temperature is not the hazard. Temperature with humidity, radiation and wind is. The standard
index for that in an occupational setting is Wet Bulb Globe Temperature, and the exposure limits that
matter are defined on WBGT, not on air temperature and not on a heat index.

## What it does

1. Pulls the hourly forecast for Karachi from Open-Meteo.
2. Computes WBGT by the Liljegren method, which solves the globe and natural-wet-bulb energy
   balances from standard meteorological variables.
3. Computes the NIOSH exposure limit for the worker's workload, **as an interval**.
4. Compares the two and returns one of **three** answers: under, over, or **cannot be determined**.
5. A Gemini agent turns that into two short paragraphs in English and Urdu.

## The two design rules

**The model never produces a number.** Every figure comes from a deterministic, tested function. The
agent calls tools, reads the result and writes prose. It is not asked to compute, estimate, round or
judge. It is not even allowed to work out what "1pm tomorrow" means: date arithmetic is arithmetic,
so there is a tool for that too.

**The tool refuses rather than guessing.** If the forecast in hand is too old, or the requested hour
is beyond the horizon this tool will answer for, it declines and says why. Those are branches in
`heatline/tools.py`, not instructions in a prompt, because a prompt can be talked out of a branch.
`/assess` returns HTTP 409 on a refusal so that nothing downstream mistakes it for an answer.

### Why three answers instead of two

NIOSH gives the exposure limit as a function of metabolic rate, and states that "Errors in estimating
metabolic rate from energy expenditure tables are reported to be as high as 30%". Moderate work is a
band, 234 to 349 W, so the limit is a band too: **27.5 to 29.5 °C WBGT**. When the exposure falls
inside that band, whether a particular rider is over the limit depends on how hard they are actually
working, and a forecast cannot know that.

So the honest answer is that it cannot be determined. Rounding it to a yes or a no would be inventing
the one piece of information nobody has. Over 48 hours of real Karachi forecast this turned **ten
hours of false confidence into "cannot tell"**.

## Run it yourself

Needs Python 3.12 and a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
No Google Cloud project and no billing account are required.

```sh
uv venv --python 3.12 && uv pip install -r requirements.txt
export GOOGLE_API_KEY="..."
python -m heatline.service          # serves on http://127.0.0.1:8412
```

Then:

```sh
curl 'http://127.0.0.1:8412/assess'                         # right now
curl 'http://127.0.0.1:8412/day?hours=12'                   # the next 12 hours
curl 'http://127.0.0.1:8412/advise?q=Should I ride now?'     # the agent
```

### Endpoints

| | |
|---|---|
| `GET /status` | how old the data is, and how far ahead this will answer |
| `GET /limit` | the NIOSH limit interval for this worker |
| `GET /assess` | one hour: under, over or undetermined. **409 on a refusal** |
| `GET /day` | the next hours of a shift, with counts |
| `GET /advise` | the agent, English and Urdu |
| `GET /health` | liveness, and whether a model key is present |

**The numbers and the prose are deliberately separate endpoints.** `/assess` and `/day` work with no
API key at all, so the arithmetic is checkable without a language model in the loop and without
spending a token. That separation is the point: the model is visibly a presentation layer.

### See the refusals for yourself

```sh
# beyond the horizon: the hour is in the forecast, and it declines anyway
curl -i 'http://127.0.0.1:8412/assess?hour=2026-09-29T14:00'

# stale data: set the ceiling to zero, so the real code path fires on real data
HEATLINE_MAX_FETCH_AGE_MINUTES=0 python -m heatline.service
curl -i 'http://127.0.0.1:8412/assess'
```

## Tests

```sh
python -m pytest tests/ -q      # 46 tests, no network
```

Nothing in the suite calls Open-Meteo: a test that depends on live weather cannot fail for the right
reason. The tests worth reading are the ones that check the arithmetic against the document it came
from, and the ones that prove the refusals fire:

- `test_limits.py` the REL equation reproduces the value NIOSH's own table gives for moderate work,
  to 0.21 °C. An equation and a table in one document disagreeing would mean a transcription error.
- `test_refusal.py` stale data and beyond-horizon both refuse, **and leak no numbers** in the refusal.
- `test_wbgt.py` determinism, unit sanity, and that the index moves in the direction physics requires.
- `test_ingest.py` the km/h to m/s conversion, which if inverted would silently understate every
  heat load while looking plausible.

## What this does not do

- **One city, one worker group.** Karachi, motorcycle delivery riders.
- **A forecast is not a measurement at the worksite.** WBGT properly requires a black globe and a
  natural wet bulb thermometer where the person actually is. Liljegren models them from grid
  meteorology. Asphalt, walls and traffic make a real street hotter than a citywide forecast.
- **Not medical advice**, and not a substitute for an occupational health assessment. These are
  population-level screening limits.
- **No delivery channel.** It is a local web service, not something reaching a rider on the road.
- **The Urdu is machine-generated** and has not been reviewed by a translator.
- **It cannot tell you your own metabolic rate**, which is why the third answer exists.

## Sources

Every formula, coefficient and threshold is quoted from its primary document, with the URL and the
date it was opened, in **[SOURCES.md](SOURCES.md)**. Nothing was written from memory. The short
version:

- WBGT definition and the exposure limit equations: NIOSH, *Criteria for a Recommended Standard:
  Occupational Exposure to Heat and Hot Environments*, DHHS (NIOSH) Publication No. 2016-106.
- WBGT from meteorological variables: Liljegren et al. (2008), via ECMWF's
  [thermofeel](https://github.com/ecmwf/thermofeel) (Apache-2.0).
- Heat index, which is displayed but drives nothing: Rothfusz, L.P. (1990), NWS SR 90-23.
- The 2015 Karachi heatwave: Government of Pakistan, Ministry of Climate Change, *Technical Report on
  Karachi Heat wave June 2015*.

## Licence and attribution

Code: MIT, see [LICENSE](LICENSE).

**Weather data by [Open-Meteo.com](https://open-meteo.com), CC BY 4.0.** Open-Meteo's free API is
licensed for non-commercial use only, which this is.
