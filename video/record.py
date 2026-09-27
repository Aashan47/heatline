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
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "heatline-demo.mp4"
NARRATION = HERE / "narration.json"

URL = "http://127.0.0.1:8412/?demo=1"
W, H = 1920, 1080


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

    if problems:
        print("page problems:")
        for p_ in problems:
            print("  ", p_)
    else:
        print("page problems: none")
    return path


def main() -> None:
    webm = record()
    size_mb = webm.stat().st_size / 1e6
    print(f"captured {webm.name}  {size_mb:.1f} MB")

    audio = HERE / "narration.m4a"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm)]
    if audio.exists():
        cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "160k", "-shortest"]
        print("muxing narration")
    cmd += [
        "-c:v", "libx264", "-preset", "slow", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", "30",
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
