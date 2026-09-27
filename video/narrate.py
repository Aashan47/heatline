"""Generate the narration track, timed to the same scene clock as the demo.

The voice is synthesised with Gemini TTS. That is a deliberate, disclosed
choice and not a pretence: see 08-VIDEO-DELIVERABLE.md. Aashan's own recording
is the better option for a programme about meeting real builders, and swapping
it in is one ffmpeg command, because each line is rendered as its own clip and
placed at its scene's start time.

One clip per scene, laid onto a silent bed of the exact video length, so the
audio cannot drift from the picture however long any clip turns out to be.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import wave
from pathlib import Path

from google import genai
from google.genai import types

HERE = Path(__file__).resolve().parent
CLIPS = HERE / "voice"
OUT = HERE / "narration.m4a"

MODEL = "gemini-2.5-flash-preview-tts"
# Charon reads low and level, which suits a safety tool. A bright, upbeat
# delivery would be wrong for the subject.
VOICE = "Charon"
TOTAL = 84.0

STYLE = (
    "Read this as a calm, measured product narration for a workplace safety "
    "tool. Even pace, no salesmanship, no rising enthusiasm. Plain and factual."
)

# (start second, text). Starts match SCENES in heatline/static/demo.js.
LINES: list[tuple[float, str]] = [
    (0.5, "Karachi, the twenty seventh of September. Air temperature peaked at "
          "thirty one point three."),
    (6.6, "Nobody warns you about thirty one degrees."),
    (13.1, "The thermometer says thirty point eight. The exposure index says "
           "twenty nine point seven, and that is the one the limit uses."),
    (20.6, "Blue is exposure. The amber band is the NIOSH limit. At noon it "
           "crosses in."),
    (28.6, "The limit is a band because the workload is. NIOSH says effort "
           "estimates can be thirty percent out."),
    (36.6, "So for seven hours it will not call it. Inside the band, it depends "
           "on how hard this rider is working, and a forecast cannot know."),
    (45.6, "Ask past the horizon it answers for, and it declines. Four zero nine, "
           "every reading withheld."),
    (55.6, "Put to the Gemini agent, the refusal survives, in English and Urdu, "
           "with no numbers in it."),
    (66.6, "One city, one worker group. A forecast is not the street, and the "
           "Urdu is unreviewed."),
    (75.6, "Every formula quoted from its source. Code at github dot com, "
           "Aashan forty seven, heatline."),
]


def pcm_to_wav(pcm: bytes, path: Path, rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def synth(client: genai.Client, text: str, dest: Path) -> float:
    """Render one line, retrying on the free tier's 3-per-minute quota.

    The API states its own retryDelay on a 429, so that is what we wait, rather
    than guessing an interval and either wasting time or hammering the quota.
    """
    for attempt in range(6):
        try:
            return _synth_once(client, text, dest)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
                raise
            m = re.search(r"retryDelay[\'\"]:\s*[\'\"](\d+(?:\.\d+)?)s", msg)
            wait = min(70.0, float(m.group(1)) + 2.0 if m else 25.0)
            print(f"      quota hit, waiting {wait:.0f}s")
            time.sleep(wait)
    raise SystemExit("TTS quota did not clear")


def _synth_once(client: genai.Client, text: str, dest: Path) -> float:
    r = client.models.generate_content(
        model=MODEL,
        contents=f"{STYLE}\n\n{text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE)
                )
            ),
        ),
    )
    pcm = r.candidates[0].content.parts[0].inline_data.data
    pcm_to_wav(pcm, dest)
    seconds = len(pcm) / 2 / 24000
    return seconds


def main() -> None:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("set GOOGLE_API_KEY")
    CLIPS.mkdir(exist_ok=True)
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    made: list[tuple[float, Path, float]] = []
    for i, (at, text) in enumerate(LINES):
        dest = CLIPS / f"{i:02d}.wav"
        if dest.exists():
            # Resume: a quota stall part way through should not re-spend the
            # lines already rendered.
            with wave.open(str(dest)) as w:
                secs = w.getnframes() / w.getframerate()
            print(f"  {i:02d}  cached")
        else:
            secs = synth(client, text, dest)
            time.sleep(21)  # 3 requests per minute on the free tier
        made.append((at, dest, secs))
        room = (LINES[i + 1][0] - at) if i + 1 < len(LINES) else TOTAL - at
        flag = "  OVERRUNS" if secs > room else ""
        print(f"  {i:02d}  starts {at:5.1f}s  spoken {secs:5.1f}s  "
              f"room {room:5.1f}s{flag}")

    # A silent bed of exactly the right length, then each clip placed at its
    # own start time. Nothing can drift.
    inputs, filters, mixes = ["-f", "lavfi", "-t", f"{TOTAL}", "-i", "anullsrc=r=24000:cl=mono"], [], ["[0:a]"]
    for i, (at, dest, _) in enumerate(made, start=1):
        inputs += ["-i", str(dest)]
        filters.append(f"[{i}:a]adelay={int(at * 1000)}|{int(at * 1000)}[d{i}]")
        mixes.append(f"[d{i}]")
    graph = ";".join(filters) + ";" + "".join(mixes) + \
        f"amix=inputs={len(made) + 1}:duration=first:normalize=0[out]"

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", graph, "-map", "[out]",
         "-c:a", "aac", "-b:a", "160k", str(OUT)],
        check=True,
    )
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(OUT)], capture_output=True, text=True, check=True,
    ).stdout.strip()
    print(f"\n{OUT.name}  {float(dur):.1f}s  {OUT.stat().st_size / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
