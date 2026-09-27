"""Render the captured session into a captioned 1080p video.

What this is, said plainly so it is never misrepresented: a rendered playback of
a real terminal session. Every command and every character of output in
session.json came from an actual run on 2026-09-27, captured by capture.py with
the wall clock time each command took. This script lays that out and encodes it.
It is the same category of artifact as an asciinema recording, not a mockup, and
nothing on screen was typed into a transcript by hand.

Frames are rendered by headless Chrome rather than by a drawing library, because
the agent answers in Urdu and Urdu needs real text shaping. Pillow without raqm
renders it as disconnected letters in the wrong direction.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames"
SESSION = HERE / "session.json"
OUT_MP4 = HERE / "heatline-demo.mp4"
OUT_SRT = HERE / "heatline-demo.srt"

CHROME = Path(
    os.environ.get(
        "CHROME_BIN",
        str(
            Path.home()
            / "Library/Caches/ms-playwright/chromium-1243/chrome-mac-arm64"
            / "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        ),
    )
)

W, H = 1920, 1080
PROMPT = "heatline ~ $"

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1920px; height: 1080px; overflow: hidden; }
body {
  background: #0b0f14;
  color: #d8e0e8;
  font: 26px/1.5 Menlo, monospace;
  display: flex; flex-direction: column;
}
.chrome {
  height: 52px; flex: none; display: flex; align-items: center; gap: 10px;
  padding: 0 22px; background: #151b23; border-bottom: 1px solid #222b36;
}
.dot { width: 13px; height: 13px; border-radius: 50%; }
.title {
  margin-left: 14px; font-size: 20px; color: #8b98a5; letter-spacing: .04em;
}
.screen { flex: 1; padding: 34px 44px; overflow: hidden; }
.cmd { color: #d8e0e8; margin-bottom: 14px; white-space: pre-wrap;
       word-break: break-all; }
.cmd .p { color: #58a6ff; }
.cmd .caret { background: #d8e0e8; color: #0b0f14; }
pre { white-space: pre-wrap; font: 26px/1.42 Menlo, monospace; color: #b9c4cf; }
.k { color: #79c0ff; }  .n { color: #ffa657; }  .s { color: #a5d6ff; }
.over { color: #ff7b72; font-weight: 700; }
.undet { color: #e3b341; font-weight: 700; }
.under { color: #7ee787; }
.warn { color: #ff7b72; font-weight: 700; }
.dim { color: #6e7b8a; }
.urdu {
  font-family: "Geeza Pro", serif; direction: rtl; text-align: right;
  font-size: 32px; line-height: 1.85; color: #a5d6ff; margin-top: 18px;
}
.caption {
  flex: none; min-height: 132px; padding: 26px 56px;
  background: #05080b; border-top: 2px solid #1b2530;
  display: flex; align-items: center;
  font: 600 38px/1.35 -apple-system, "Helvetica Neue", sans-serif;
  color: #ffffff; letter-spacing: -.01em;
}
.card { flex: 1; display: flex; flex-direction: column; justify-content: center;
        padding: 0 110px; }
.card h1 { font: 800 92px/1.08 -apple-system, sans-serif; letter-spacing: -.03em; }
.card h1 .hl { color: #ff7b72; }
.card p { font: 400 38px/1.5 -apple-system, sans-serif; color: #9fb0c0;
          margin-top: 34px; max-width: 1400px; }
.card .repo { font: 600 46px/1 Menlo, monospace; color: #7ee787; margin-top: 44px; }
.attrib { font: 400 26px/1 -apple-system, sans-serif; color: #5c6b7a;
          margin-top: 30px; }
ul.lim { margin-top: 30px; list-style: none; }
ul.lim li { font: 400 36px/1.75 -apple-system, sans-serif; color: #9fb0c0; }
ul.lim li::before { content: "not "; color: #ff7b72; font-weight: 700; }
"""


def colourise(text: str) -> str:
    """Highlight the verdicts and the status line, in a single pass.

    Sequential str.replace was wrong here and it showed: replacing "  over"
    first inserted a span, and the later '"over"' rule then matched inside that
    span's own attribute, rendering `"over">over` on screen. One regex, one
    pass, no self-collision.
    """
    escaped = html.escape(text)
    rules = {
        "over": "over",
        "undetermined": "undet",
        "under": "under",
        "HTTP 409": "warn",
        "409": "warn",
        "outside_horizon": "warn",
        "null": "warn",
        "49 passed": "under",
    }
    pattern = re.compile(
        r"(HTTP 409|outside_horizon|49 passed|\b(?:undetermined|under|over|null)\b)"
    )
    return pattern.sub(
        lambda m: f'<span class="{rules[m.group(0)]}">{m.group(0)}</span>', escaped
    )


def split_urdu(text: str) -> tuple[str, str]:
    """Separate the Urdu block so it can be laid out right to left."""
    latin, urdu = [], []
    for line in text.split("\n"):
        if any("؀" <= ch <= "ۿ" for ch in line):
            urdu.append(line)
        else:
            latin.append(line)
    return "\n".join(latin).strip("\n"), "\n".join(urdu).strip("\n")


@dataclass
class Frame:
    name: str
    seconds: float
    caption: str
    cmd: str | None = None
    output: str = ""
    urdu: str = ""
    card: str = ""
    caret: bool = False
    srt: str = field(default="")

    def as_html(self) -> str:
        if self.card:
            body = f'<div class="card">{self.card}</div>'
        else:
            bits = []
            if self.cmd:
                caret = '<span class="caret">&nbsp;</span>' if self.caret else ""
                bits.append(
                    f'<div class="cmd"><span class="p">{PROMPT}</span> '
                    f"{html.escape(self.cmd)}{caret}</div>"
                )
            if self.output:
                bits.append(f"<pre>{colourise(self.output)}</pre>")
            if self.urdu:
                bits.append(f'<div class="urdu">{html.escape(self.urdu)}</div>')
            body = f'<div class="screen">{"".join(bits)}</div>'

        return f"""<!doctype html><meta charset="utf-8"><style>{CSS}</style>
<div class="chrome">
  <span class="dot" style="background:#ff5f57"></span>
  <span class="dot" style="background:#febc2e"></span>
  <span class="dot" style="background:#28c840"></span>
  <span class="title">heatline &middot; Karachi occupational heat exposure</span>
</div>
{body}
<div class="caption">{html.escape(self.caption)}</div>"""


def shown(scene: dict) -> str:
    """The command as displayed: identical in effect to what ran, with the base
    URL in a shell variable so the line fits on screen without truncation."""
    return scene.get("show") or scene["cmd"]


def build_timeline(session: list[dict]) -> list[Frame]:
    by_id = {s["id"]: s for s in session}
    f: list[Frame] = []

    f.append(Frame(
        "01_title", 6.5,
        "Karachi, 27 September 2026. Air temperature peaked at 31.3 degrees.",
        card=(
            '<h1>31 degrees is not a<br>safe afternoon in <span class="hl">Karachi</span></h1>'
            "<p>For a motorcycle delivery rider, six hours of that afternoon were over "
            "the occupational heat limit. Two more were too close to call.</p>"
            '<div class="attrib">Nothing on their phone said so.</div>'
        ),
        srt="Karachi, 27 September 2026. Air temperature peaked at 31.3 degrees. "
            "Six hours of that afternoon were over the occupational heat limit.",
    ))

    counts = by_id["counts"]
    f.append(Frame("02_counts", 6.0,
                   "Eleven hours of tomorrow's shift for a delivery rider.",
                   cmd=shown(counts), output=counts["output"],
                   srt="Eleven hours of tomorrow's shift for a delivery rider. One hour "
                       "over the limit, seven that cannot be called."))

    day = by_id["day"]
    f.append(Frame("03_day", 13.0,
                   "Air temperature on the left, never above 31. Exposure on the right.",
                   cmd=shown(day), output=day["output"],
                   srt="Air temperature on the left, never above 31 degrees. The exposure "
                       "index on the right. Eight of these eleven hours are over the limit "
                       "or too close to call."))

    lim = by_id["limit"]
    f.append(Frame("04_limit", 7.5,
                   "The limit is a range, because the workload is a range.",
                   cmd=shown(lim), output=lim["output"],
                   srt="The limit is a range, because the workload is. NIOSH says "
                       "metabolic rate estimates can be thirty percent out, so the limit "
                       "spans two full degrees."))

    und = by_id["undetermined"]
    f.append(Frame("05_undetermined", 8.5,
                   "Inside that range it will not guess. margin_c is null.",
                   cmd=shown(und), output=und["output"],
                   srt="When the exposure lands inside that range, the honest answer is "
                       "that it cannot be determined. Across 48 hours this moved ten hours "
                       "out of a confident verdict."))

    ref = by_id["refuse_status"]
    f.append(Frame("06_refuse", 11.0,
                   "This hour is in the forecast. It declines anyway, with a 409.",
                   cmd=shown(ref), output=ref["output"],
                   srt="This hour is in the forecast, and it declines anyway, because that "
                       "is past the horizon this tool will answer for. A 409, so nothing "
                       "downstream mistakes a refusal for an answer. That is a branch in "
                       "the code, not a line in a prompt."))

    agent = by_id["refuse_agent"]
    latin, urdu = split_urdu(agent["output"])
    f.append(Frame("07_agent", 13.5,
                   f"The refusal survives the model. Real latency, {agent['seconds']:.0f} seconds.",
                   cmd=shown(agent), output=latin, urdu=urdu,
                   srt="Put to the agent, the refusal survives the language model, in "
                       "English and Urdu, and there is not a single number in it."))

    tests = by_id["tests"]
    f.append(Frame("08_tests", 7.0,
                   "Forty nine tests. None of them touch the network.",
                   cmd=shown(tests), output=tests["output"],
                   srt="Forty nine tests, and none of them touch the network. A test that "
                       "depends on today's weather cannot fail for the right reason."))

    f.append(Frame("09_limits", 8.5,
                   "What it does not do, said out loud.",
                   card=(
                       "<h1>What it does not do</h1>"
                       '<ul class="lim">'
                       "<li>more than one city and one worker group</li>"
                       "<li>a measurement on the street; a forecast is a grid cell</li>"
                       "<li>medical advice; these are screening limits</li>"
                       "<li>reviewed Urdu; it is machine generated</li>"
                       "<li>able to know your own metabolic rate</li>"
                       "</ul>"
                   ),
                   srt="One city, one worker group. A forecast is not a measurement on the "
                       "street, the Urdu has not been checked by a translator, and it "
                       "cannot know your own metabolic rate. Which is why the third answer "
                       "exists."))

    f.append(Frame("10_repo", 6.5,
                   "Every number has a primary source. Built with Gemini and ADK.",
                   card=(
                       "<h1>Every number has a<br>primary source</h1>"
                       "<p>WBGT by Liljegren via ECMWF thermofeel. Limits from NIOSH "
                       "2016-106. Each one quoted with a URL in SOURCES.md.</p>"
                       '<div class="repo">github.com/Aashan47/heatline</div>'
                       '<div class="attrib">Weather data by Open-Meteo.com, CC BY 4.0. '
                       "Built with Gemini and the Agent Development Kit.</div>"
                   ),
                   srt="The code and every source is at github.com/Aashan47/heatline. "
                       "Weather data by Open-Meteo, CC BY 4.0."))
    return f


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> None:
    if not CHROME.exists():
        raise SystemExit(f"Chrome not found at {CHROME}. Set CHROME_BIN.")
    session = json.loads(SESSION.read_text())
    frames = build_timeline(session)

    shutil.rmtree(FRAMES, ignore_errors=True)
    FRAMES.mkdir(parents=True)

    for fr in frames:
        page = FRAMES / f"{fr.name}.html"
        page.write_text(fr.as_html())
        subprocess.run(
            [str(CHROME), "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1", f"--window-size={W},{H}",
             f"--screenshot={FRAMES / (fr.name + '.png')}", page.as_uri()],
            check=True, capture_output=True,
        )
        print(f"  rendered {fr.name}  {fr.seconds:5.1f}s")

    concat = FRAMES / "concat.txt"
    lines = []
    for fr in frames:
        lines.append(f"file '{fr.name}.png'")
        lines.append(f"duration {fr.seconds}")
    lines.append(f"file '{frames[-1].name}.png'")
    concat.write_text("\n".join(lines) + "\n")

    total = sum(fr.seconds for fr in frames)
    # -t is not optional. The concat demuxer needs the final image repeated for
    # its duration to apply, and then holds that repeat for a default interval,
    # which made the first encode 94.5s against an 88.0s timeline and put the
    # captions out of sync with the picture.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(concat), "-t", f"{total:.3f}",
         "-vf", "fps=25,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-crf", "20",
         "-movflags", "+faststart", str(OUT_MP4)],
        check=True,
    )

    blocks, t = [], 0.0
    for i, fr in enumerate(frames, 1):
        if fr.srt:
            blocks.append(f"{i}\n{srt_time(t)} --> {srt_time(t + fr.seconds)}\n"
                          f"{fr.srt}\n")
        t += fr.seconds
    OUT_SRT.write_text("\n".join(blocks))

    print(f"\n{OUT_MP4.name}  {total:.1f}s  {OUT_MP4.stat().st_size / 1e6:.1f} MB")
    print(f"{OUT_SRT.name}  {len(blocks)} caption blocks")


if __name__ == "__main__":
    main()
