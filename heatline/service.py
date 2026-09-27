"""HTTP service. Two kinds of endpoint, deliberately.

/assess and /day return the deterministic numbers with no model involved, so
anyone can check the arithmetic without paying for a token or trusting a
language model. /advise runs the agent and returns prose in English and Urdu.

Keeping them separate is the point: the numbers are verifiable on their own,
and the model is visibly a presentation layer rather than the source of truth.
"""

from __future__ import annotations

import asyncio
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.genai.errors import ClientError, ServerError

from .agent import MODEL, root_agent
from .config import DEFAULT_PROFILE, SUPPORTED_HORIZON_HOURS
from .ingest import ATTRIBUTION
from .keys import ensure_google_api_key
from .tools import assess_day, assess_hour, data_status, exposure_limit

APP_NAME = "heatline"

# One agent answer costs several model calls, so a free tier rate limit is a
# normal condition here. Retry a few times before giving up.
MAX_MODEL_ATTEMPTS = 4

app = FastAPI(title="heatline", docs_url=None, redoc_url=None)

_session_service = InMemorySessionService()
_runner = Runner(
    app_name=APP_NAME, agent=root_agent, session_service=_session_service
)


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "model": MODEL,
        "model_key_present": ensure_google_api_key(),
        "supported_horizon_hours": SUPPORTED_HORIZON_HOURS,
        "attribution": ATTRIBUTION,
    }


@app.get("/status")
def status() -> dict:
    return data_status()


@app.get("/limit")
def limit(profile: str = DEFAULT_PROFILE, acclimatized: bool = True) -> dict:
    out = exposure_limit(profile, acclimatized)
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out)
    return out


@app.get("/assess")
def assess_endpoint(
    hour: str | None = None,
    profile: str = DEFAULT_PROFILE,
    acclimatized: bool = True,
) -> JSONResponse:
    """One hour. Returns HTTP 409 when the tool refuses, so a refusal is not
    mistaken for an answer by anything consuming this."""
    out = assess_hour(hour, profile, acclimatized)
    return JSONResponse(out, status_code=200 if out.get("ok") else 409)


@app.get("/day")
def day_endpoint(
    hours: int = 12,
    profile: str = DEFAULT_PROFILE,
    acclimatized: bool = True,
) -> JSONResponse:
    out = assess_day(profile, acclimatized, hours)
    return JSONResponse(out, status_code=200 if out.get("ok") else 409)


def _retry_after_seconds(exc: Exception, default: float) -> float:
    """Honour the delay the API asks for, when it names one.

    A 429 from the Gemini free tier carries a RetryInfo with a retryDelay.
    Guessing an interval instead would either waste time or hammer the quota.
    """
    match = re.search(r"[\'\"]retryDelay[\'\"]:\s*[\'\"](\d+(?:\.\d+)?)s", str(exc))
    if match:
        return min(30.0, float(match.group(1)) + 1.0)
    return default


async def _ensure_session(session_id: str) -> None:
    """Create the session only if it is not already there.

    The Runner will auto-create one, so creating it unconditionally raises
    AlreadyExistsError on the second request with the same session id.
    """
    existing = await _session_service.get_session(
        app_name=APP_NAME, user_id="rider", session_id=session_id
    )
    if existing is None:
        await _session_service.create_session(
            app_name=APP_NAME, user_id="rider", session_id=session_id
        )


@app.get("/advise")
async def advise(
    q: str = "Should I ride right now?",
    session: str = "demo",
) -> dict:
    """Run the agent. The prose is the model's; every number in it came from a tool."""
    if not ensure_google_api_key():
        raise HTTPException(
            status_code=503,
            detail=(
                "No Gemini API key in the environment. Set GOOGLE_API_KEY. "
                "The deterministic endpoints /assess and /day work without one."
            ),
        )

    await _ensure_session(session)
    message = types.Content(role="user", parts=[types.Part(text=q)])

    chunks: list[str] = []
    calls: list[str] = []

    async def run_once() -> None:
        chunks.clear()
        calls.clear()
        async for event in _runner.run_async(
            user_id="rider", session_id=session, new_message=message
        ):
            content = getattr(event, "content", None)
            for part in getattr(content, "parts", None) or []:
                if getattr(part, "function_call", None):
                    calls.append(part.function_call.name)
                text = getattr(part, "text", None)
                if text:
                    chunks.append(text)

    # The free tier allows a small number of requests per minute and one agent
    # answer spends several of them, so a rate limit is an expected condition
    # here rather than an exceptional one. Retry when the API says to, then give
    # up honestly instead of emitting half an answer.
    last: Exception | None = None
    for attempt in range(MAX_MODEL_ATTEMPTS):
        try:
            await run_once()
            last = None
            break
        except (ServerError, ClientError, Exception) as exc:  # noqa: BLE001
            text = str(exc)
            transient = ("429" in text or "RESOURCE_EXHAUSTED" in text
                         or "503" in text or "UNAVAILABLE" in text)
            if not transient:
                raise
            last = exc
            if attempt < MAX_MODEL_ATTEMPTS - 1:
                await asyncio.sleep(_retry_after_seconds(exc, 4.0 * (attempt + 1)))

    if last is not None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "the model was rate limited or unavailable",
                "attempts": MAX_MODEL_ATTEMPTS,
                "upstream": str(last)[:300],
                "advice": (
                    "The deterministic endpoints /assess, /day, /limit and "
                    "/status are unaffected. The numbers never depended on the "
                    "model."
                ),
            },
        )

    return {
        "question": q,
        "answer": "".join(chunks).strip(),
        "tools_called": calls,
        "model": MODEL,
        "attribution": ATTRIBUTION,
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return f"""<!doctype html>
<title>heatline</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.6 system-ui, sans-serif; max-width: 42rem;
         margin: 0 auto; padding: 2rem 1rem; }}
  code {{ background: rgba(127,127,127,.18); padding: .1em .35em;
          border-radius: .25em; }}
  li {{ margin: .35rem 0; }}
</style>
<h1>heatline</h1>
<p>Occupational heat exposure for outdoor workers in Karachi. WBGT computed from
public forecast data by the Liljegren method, compared against the NIOSH
exposure limit for the worker's workload.</p>
<p>The numbers and the prose are separate endpoints on purpose. The arithmetic
is checkable without a language model.</p>
<ul>
  <li><code>/status</code> how old the data is, and how far ahead this answers</li>
  <li><code>/limit</code> the NIOSH limit interval for this worker</li>
  <li><code>/assess</code> one hour: under, over, or undetermined</li>
  <li><code>/day?hours=12</code> the next hours of a shift</li>
  <li><code>/advise?q=...</code> the agent, in English and Urdu</li>
</ul>
<p>A request outside the supported {SUPPORTED_HORIZON_HOURS} hour horizon, or
against data this service considers stale, returns HTTP 409 and no advice.
That is intended.</p>
<p>{ATTRIBUTION}</p>
"""


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HEATLINE_HOST", "127.0.0.1"),
        port=int(os.environ.get("HEATLINE_PORT", "8412")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
