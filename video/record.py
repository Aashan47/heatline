"""Record the demo by driving the real dashboard in a real browser.

This is a genuine screen recording of the running product: Playwright loads
http://127.0.0.1:8412/?demo=1 in Chromium, the page calls the same endpoints
anyone can curl, and Chromium's own screencast captures the frames. Nothing is
mocked and no frame is drawn by hand.

The refusal scene is the service actually returning 409. The advisory scene is
Gemini actually answering.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "heatline-demo.mp4"
NARRATION = HERE / "narration.json"

BASE = "http://127.0.0.1:8412"
URL = f"{BASE}/?demo=1"
W, H = 1920, 1080

# Both questions the scene asks. They are warmed before the camera rolls so
# that the answers are in the service's cache when the scene asks for them.
#
# This is why: the last take was recorded against a rate limited agent. The
# tool chain never appeared, so the caption "the agent works, it resolves the
# hour, reads the forecast" played for twenty seconds over a quota notice,
# and the two waits left ten and nine seconds of dead air that the narration
# then had to be squeezed around. Warming first means the spinner on camera is
# short because the answer is already paid for, and the pre flight below fails
# the run rather than filming that again.
QUESTIONS = [
    "Can I work at 1pm on 28 September?",
    "What about 2pm on 29 September?",
]

# Phrases that mean the agent did not answer. If any of these is on screen at
# the end, the take is not usable however good it looks.
NOT_AN_ANSWER = (
    "spends the deployer's Gemini quota",
    "used this hour's agent questions",
    "temporarily unavailable",
    "could not be reached",
)


def warm(question: str, attempts: int = 6) -> None:
    """Ask once, off camera, until the model answers.

    The free tier allows a few requests a minute and one agent answer spends
    several, so a 429 here is ordinary. Waiting through it costs nothing except
    time; filming through it cost a whole take.
    """
    url = f"{BASE}/advise?q=" + urllib.parse.quote(question)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                body = json.loads(r.read())
            if body.get("answer"):
                print(f"  warmed{' from cache' if body.get('cached') else ''}: "
                      f"{question}")
                return
            raise SystemExit(f"the agent returned an empty answer for: {question}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            # A missing key is not going to clear on its own. Retrying it spent
            # five minutes saying so.
            if "API key" in detail:
                raise SystemExit(
                    "the service has no Gemini API key, so the agent cannot "
                    "answer and nothing was recorded. Start it with the key in "
                    "its environment."
                ) from None
            wait = int(exc.headers.get("Retry-After") or 0) or 20 * attempt
            if attempt == attempts:
                raise SystemExit(
                    f"the agent would not answer {question!r} after {attempts} "
                    f"tries. Last response was HTTP {exc.code}: {detail}\n"
                    "Recording now would film a quota notice, so nothing was "
                    "recorded. Raise HEATLINE_ADVISE_LIMIT for the recording "
                    "service, or wait for the model quota to reset."
                ) from None
            print(f"  HTTP {exc.code}, waiting {wait}s ({attempt}/{attempts})",
                  flush=True)
            time.sleep(wait)


def preflight() -> None:
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=10) as r:
            r.read()
    except OSError as exc:
        raise SystemExit(
            f"nothing is serving {BASE}: {exc}. Start the service first."
        ) from None
    print("warming the agent, off camera")
    for question in QUESTIONS:
        warm(question)


def record() -> Path:
    shutil.rmtree(RAW, ignore_errors=True)
    RAW.mkdir(parents=True)
    problems: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-device-scale-factor=1"])
        context = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=str(RAW),
            record_video_size={"width": W, "height": H},
            device_scale_factor=1,
        )
        page = context.new_page()
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        page.on("console",
                lambda m: problems.append(f"{m.type}: {m.text}")
                if m.type == "error" else None)

        page.goto(URL, wait_until="networkidle")
        # Fonts must be in before the first frame, or the opening slate renders
        # in a fallback face and then reflows on camera.
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=15000)
        page.wait_for_function("typeof window.__demoPlay === 'function'", timeout=15000)

        total = page.evaluate("window.__demoTotal")
        # The recording starts when the context opens, before the scene does.
        # Measuring the offset here is what lets the narration line up with the
        # finished file rather than with the page's own clock.
        lead_in = page.evaluate("performance.now()") / 1000.0
        page.evaluate("window.__demoPlay()")
        page.wait_for_function("window.__demoDone === true",
                               timeout=int((total + 90) * 1000))
        scene_error = page.evaluate("window.__demoError || null")
        if scene_error:
            context.close()
            browser.close()
            raise SystemExit(f"the scene stopped: {scene_error}")

        # What the agent actually said, read off the finished screen. A take
        # that shows a quota notice where the caption claims the agent worked
        # is the defect this check exists for.
        shown = page.evaluate(
            "(document.getElementById('adv-en-t')?.textContent || '') + ' ' + "
            "(document.getElementById('chain')?.textContent || '')")
        marks = page.evaluate("window.__demoMarks")
        facts = page.evaluate("window.__demoFacts")
        elapsed = page.evaluate("window.__demoElapsed")
        page.wait_for_timeout(500)

        video = page.video
        context.close()
        browser.close()
        path = Path(video.path())

    # Each beat's "ready" is the moment its picture was actually on screen.
    # Narration is written per beat, so that is the timestamp it must use.
    NARRATION.write_text(json.dumps({
        "lead_in": round(lead_in, 3),
        "elapsed": round(elapsed, 3),
        "beats": marks,
        "facts": facts,
    }, indent=2))
    print(f"lead-in {lead_in:.2f}s, scene {elapsed:.1f}s")

    for phrase in NOT_AN_ANSWER:
        if phrase.lower() in shown.lower():
            raise SystemExit(
                f"the finished screen still says {phrase!r}, so the agent did "
                "not answer on camera and this take is not usable")
    if len(marks) != 8:
        raise SystemExit(f"expected eight beats, got {len(marks)}")

    if problems:
        print("page problems:")
        for p_ in problems:
            print("  ", p_)
    else:
        print("page problems: none")
    return path


def main() -> None:
    preflight()
    webm = record()
    size_mb = webm.stat().st_size / 1e6
    print(f"captured {webm.name}  {size_mb:.1f} MB")

    # No audio here. narrate.py owns the mux, because narration is timed to the
    # beats of the take that has just been written: the previous take's
    # narration is always the wrong length for this one. Muxing it anyway, with
    # -shortest, silently truncated a 76.7s take to 62.8s.
    stale = HERE / "narration.m4a"
    if stale.exists():
        stale.unlink()
        print("removed the previous take's narration")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm)]
    cmd += [
        # fps as a filter, not -r. As an output flag, -r reinterprets the
        # source frames at the new rate instead of resampling them: a 69.3s
        # capture of 1732 frames came out as a 58s file playing 14% fast, and
        # the closing slate fell off the end entirely. The filter duplicates
        # frames and keeps real time.
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "19",
        "-movflags", "+faststart", str(OUT),
    ]
    subprocess.run(cmd, check=True)

    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(OUT)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    print(f"\n{OUT.name}  {float(dur):.1f}s  {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
