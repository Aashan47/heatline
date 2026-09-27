"""Narration, generated from what the recording actually put on screen.

Written to Hackathons/DEMO-RECORDING/RECORDING-PROMPT.md:

- Gemini TTS, voice Charon, tempo 1.15. Charon reads level and informative;
  the livelier voices are wrong for a tool about workplace injury.
- Every line is keyed to a beat's "ready" time from narration.json, which is
  the moment that beat's picture was actually on screen in this recording, not
  the moment the scene asked for it.
- **A line that overruns its beat is a build error, not a warning.** An overrun
  means the voice describes the next picture.
- Numbers are spelled out, because the voice reads digit strings badly.
- Any number spoken is read out of the recording's own facts, so the voice can
  never contradict the screen.
- Clips are content-hash cached: changing one line re-synthesises that line and
  nothing else.
"""

from __future__ import annotations

import hashlib
import json
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
MARKS = HERE / "narration.json"
OUT = HERE / "narration.m4a"

MODEL = "gemini-2.5-flash-preview-tts"
VOICE = "Charon"
TEMPO = 1.15
STYLE = (
    "Read this as the narrator of a software product demo: calm, precise and "
    "unhurried, stating facts rather than selling. Neutral professional tone, "
    "no excitement, no upsell."
)

ONES = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
    "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten",
    "11": "eleven", "12": "twelve",
}
TENS = {
    "20": "twenty", "26": "twenty six", "27": "twenty seven",
    "28": "twenty eight", "29": "twenty nine", "30": "thirty",
    "31": "thirty one", "32": "thirty two", "33": "thirty three",
}


def say_number(text: str) -> str:
    """Spell a decimal the way the voice should read it."""
    whole, _, frac = text.partition(".")
    words = TENS.get(whole) or ONES.get(whole) or whole
    if frac:
        words += " point " + " ".join(ONES.get(d, d) for d in frac)
    return words


def lines_for(facts: dict) -> dict[str, str]:
    """The narration, with every stated number taken from the recording."""
    air = say_number(facts.get("air_c") or "")
    wbgt = say_number(facts.get("wbgt_c") or "")
    counts = facts.get("counts") or {}
    undet = ONES.get(str(counts.get("undetermined", "")), str(counts.get("undetermined", "")))

    return {
        "open": "It is the morning in Karachi, and a delivery rider wants to know "
                "about this afternoon.",
        "ask": "They ask the agent, in the words they would actually use.",
        "tools": "It works out which hour is meant, reads the forecast, and "
                 "computes the heat exposure.",
        "verdict": f"The thermometer reads {air}. The exposure index reads "
                   f"{wbgt}, and that is the one the limit is defined on.",
        "band": "Blue is exposure. The amber band is the NIOSH limit, and it is a "
                "band because the workload is a band.",
        "strip": f"So for {undet} of these hours it will not call it either way. "
                 "Inside the band, it depends on how hard this rider is working.",
        "refuse": "Now they ask about the day after tomorrow, past the horizon "
                  "this tool will answer for.",
        "withheld": "It declines. Every reading is withheld, and the agent says "
                    "so in both languages.",
        "close": "Every formula is quoted from its primary document. The code is "
                 "open source.",
    }


def clip_path(text: str) -> Path:
    key = hashlib.sha256(
        f"{MODEL}|{VOICE}|{TEMPO}|{STYLE}|{text}".encode()
    ).hexdigest()[:16]
    return CLIPS / f"{key}.wav"


def synth(client: genai.Client, text: str, dest: Path) -> None:
    for attempt in range(8):
        try:
            r = client.models.generate_content(
                model=MODEL,
                contents=f"{STYLE}\n\n{text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=VOICE)))),
            )
            pcm = r.candidates[0].content.parts[0].inline_data.data
            raw = dest.with_suffix(".raw.wav")
            with wave.open(str(raw), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                w.writeframes(pcm)
            # Tempo in the render, not in the prompt: asking a model to read
            # faster changes the reading, atempo changes only the rate.
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                 "-filter:a", f"atempo={TEMPO}", str(dest)], check=True)
            raw.unlink()
            return
        except subprocess.CalledProcessError:
            raise
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
                raise
            m = re.search(r"retryDelay['\"]:\s*['\"](\d+)", msg)
            wait = (int(m.group(1)) + 3) if m else 30
            print(f"      quota, waiting {wait}s", flush=True)
            time.sleep(wait)
    raise SystemExit("TTS quota did not clear")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def main() -> None:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise SystemExit("set GOOGLE_API_KEY")
    if not MARKS.exists():
        raise SystemExit("run record.py first: narration is timed to its beats")

    data = json.loads(MARKS.read_text())
    beats, facts = data["beats"], data.get("facts") or {}
    lead_in, total = data["lead_in"], data["elapsed"]
    text_for = lines_for(facts)

    CLIPS.mkdir(exist_ok=True)
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    placed: list[tuple[float, Path]] = []
    overruns: list[str] = []
    fresh = 0

    for i, beat in enumerate(beats):
        text = text_for.get(beat["id"])
        if not text:
            continue
        dest = clip_path(text)
        if not dest.exists():
            print(f"  {beat['id']:10s} synthesising", flush=True)
            synth(client, text, dest)
            fresh += 1
            time.sleep(21)  # free tier allows 3 requests a minute
        secs = duration(dest)

        # Start when the picture is ready, offset by the recording's lead-in.
        start = lead_in + beat["ready"] + 0.25
        nxt = beats[i + 1]["ready"] if i + 1 < len(beats) else total
        room = (lead_in + nxt) - start
        flag = ""
        if secs > room:
            flag = "  OVERRUN"
            overruns.append(f"{beat['id']}: {secs:.1f}s spoken into {room:.1f}s")
        print(f"  {beat['id']:10s} at {start:5.1f}s  {secs:4.1f}s "
              f"of {room:4.1f}s{flag}")
        placed.append((start, dest))

    if overruns:
        raise SystemExit(
            "narration overruns its beats, so the voice would describe the next "
            "picture:\n  " + "\n  ".join(overruns))

    video_len = duration(HERE / "heatline-demo.mp4")
    inputs = ["-f", "lavfi", "-t", f"{video_len:.3f}", "-i", "anullsrc=r=24000:cl=mono"]
    filters, mixes = [], ["[0:a]"]
    for i, (start, path) in enumerate(placed, start=1):
        inputs += ["-i", str(path)]
        ms = int(start * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[d{i}]")
        mixes.append(f"[d{i}]")
    graph = (";".join(filters) + ";" + "".join(mixes)
             + f"amix=inputs={len(placed) + 1}:duration=first:normalize=0[out]")

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", graph, "-map", "[out]",
         "-c:a", "aac", "-b:a", "160k", str(OUT)], check=True)

    print(f"\n{OUT.name}  {duration(OUT):.1f}s against video {video_len:.1f}s"
          f"  ({fresh} lines synthesised, {len(placed) - fresh} cached)")


if __name__ == "__main__":
    main()
