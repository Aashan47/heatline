"""Narration and music, built to Hackathons/DEMO-RECORDING/RECORDING-PROMPT.md.

Two engines. `say` is the default: macOS voices are local, need no quota, and
**Rishi is South Asian English**, which is closer to the person whose project
this is than any of the cloud voices. `gemini` is kept because the house
standard specifies Charon, and because the option should not vanish.

Whichever engine runs, the voice is synthetic and disclosed. Aashan reading
these lines himself is still the better answer, and the placement makes that a
drop-in: every line is a separate clip at its own beat's ready time.

Rules taken from the standard and enforced here:

- Lines are keyed to the beat's "ready" time from narration.json, the moment
  that picture was actually on screen in this recording.
- **A line that overruns its beat is a build error**, not a warning.
- Numbers are spelled out, and any number spoken is read from the recording's
  own captured readings, so the voice cannot contradict the screen.
- Music is hard-capped to the video length and faded before the end, so the
  streams finish together with no tail.
- Clips are content-hash cached: editing one line re-synthesises that line only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIPS = HERE / "voice"
MARKS = HERE / "narration.json"
OUT = HERE / "narration.m4a"
VIDEO = HERE / "heatline-demo.mp4"

ENGINE = os.environ.get("HEATLINE_TTS", "say")

# macOS. Rishi is en_IN, male, and reads level. Rate is words per minute; 178
# is a measured product-demo pace rather than the 175 default.
SAY_VOICE = os.environ.get("HEATLINE_VOICE", "Rishi")
SAY_RATE = int(os.environ.get("HEATLINE_RATE", "178"))

# Gemini, per the house standard.
GEMINI_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_VOICE = "Charon"
GEMINI_TEMPO = 1.15
GEMINI_STYLE = (
    "Read this as the narrator of a software product demo: calm, precise and "
    "unhurried, stating facts rather than selling. Neutral professional tone, "
    "no excitement, no upsell."
)

# Chosen by measurement, not by title. Loudness range across the twelve tracks
# in the library ran from 3.0 to 12.7 LU; this is the flattest, which is what
# sits under a voice without fighting it.
MUSIC = Path("/Users/aashanjaved/Desktop/Drive -D - Aashan/Valfirst/"
             "Music for Reels/ES_Towntones - Dusty Decks.mp3")
# Levels. Voice clips are normalised to a common loudness so one line is not
# noticeably louder than the next, the bed sits well under it, and the finished
# mix is brought to a web delivery target. Measured, because the first cut came
# out at -31.8 LUFS integrated, which is close to inaudible on a laptop.
VOICE_LUFS = -18.0
MUSIC_DB = float(os.environ.get("HEATLINE_MUSIC_DB", "-13"))
TARGET_LUFS = float(os.environ.get("HEATLINE_TARGET_LUFS", "-16"))

ONES = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
        "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
        "10": "ten", "11": "eleven", "12": "twelve"}
TENS = {"20": "twenty", "26": "twenty six", "27": "twenty seven",
        "28": "twenty eight", "29": "twenty nine", "30": "thirty",
        "31": "thirty one", "32": "thirty two", "33": "thirty three"}


def say_number(text: str) -> str:
    whole, _, frac = text.partition(".")
    words = TENS.get(whole) or ONES.get(whole) or whole
    if frac:
        words += " point " + " ".join(ONES.get(d, d) for d in frac)
    return words


def lines_for(facts: dict) -> dict[str, str]:
    """Narration. Every number comes from what the recording put on screen."""
    air = say_number(facts.get("air_c") or "")
    wbgt = say_number(facts.get("wbgt_c") or "")
    counts = facts.get("counts") or {}
    undet = ONES.get(str(counts.get("undetermined", "")),
                     str(counts.get("undetermined", "")))
    return {
        "open": "A delivery rider in Karachi wants to know about this afternoon.",
        "ask": "They ask in the words they would actually use.",
        "tools": "The agent reads the forecast and computes the exposure.",
        "verdict": f"The thermometer reads {air}. The exposure index reads {wbgt}.",
        "band": "Blue is exposure. The amber band is the limit, and it is a band "
                "because the workload is.",
        "strip": f"For {undet} of these hours it will not call it either way.",
        "refuse": "Now they ask about the day after tomorrow.",
        "withheld": "It declines. Every reading is withheld, in both languages.",
        "close": "Every formula quoted from its source. The code is open.",
    }


def clip_path(text: str) -> Path:
    key = hashlib.sha256(
        f"{ENGINE}|{SAY_VOICE}|{SAY_RATE}|{GEMINI_VOICE}|{GEMINI_TEMPO}|{text}"
        .encode()).hexdigest()[:16]
    return CLIPS / f"{key}.wav"


def ff(args: list[str]) -> None:
    """Run ffmpeg, keeping stderr. A swallowed error has cost a batch before."""
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{r.stderr.strip()}")


def normalise(src: Path, dest: Path) -> None:
    """One loudness for every line, so no line jumps out against the next."""
    ff(["-i", str(src), "-af",
        f"loudnorm=I={VOICE_LUFS}:TP=-1.5:LRA=11", "-ar", "24000", "-ac", "1",
        str(dest)])


def synth_say(text: str, dest: Path) -> None:
    aiff = dest.with_suffix(".aiff")
    subprocess.run(["say", "-v", SAY_VOICE, "-r", str(SAY_RATE),
                    "-o", str(aiff), text], check=True)
    normalise(aiff, dest)
    aiff.unlink()


def synth_gemini(text: str, dest: Path) -> None:
    import wave

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    for _ in range(8):
        try:
            r = client.models.generate_content(
                model=GEMINI_MODEL, contents=f"{GEMINI_STYLE}\n\n{text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=GEMINI_VOICE)))))
            raw = dest.with_suffix(".raw.wav")
            with wave.open(str(raw), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                w.writeframes(r.candidates[0].content.parts[0].inline_data.data)
            tmp = dest.with_suffix(".t.wav")
            ff(["-i", str(raw), "-filter:a", f"atempo={GEMINI_TEMPO}", str(tmp)])
            normalise(tmp, dest)
            raw.unlink()
            tmp.unlink()
            return
        except Exception as exc:  # noqa: BLE001
            if "429" not in str(exc) and "RESOURCE_EXHAUSTED" not in str(exc):
                raise
            m = re.search(r"retryDelay['\"]:\s*['\"](\d+)", str(exc))
            wait = (int(m.group(1)) + 3) if m else 30
            print(f"      quota, waiting {wait}s", flush=True)
            time.sleep(wait)
    raise SystemExit("TTS quota did not clear. Try HEATLINE_TTS=say.")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def main() -> None:
    if not MARKS.exists():
        raise SystemExit("run record.py first: narration is timed to its beats")
    data = json.loads(MARKS.read_text())
    beats, facts = data["beats"], data.get("facts") or {}
    lead_in, scene = data["lead_in"], data["elapsed"]
    text_for = lines_for(facts)
    video_len = duration(VIDEO)

    CLIPS.mkdir(exist_ok=True)
    print(f"engine {ENGINE}"
          + (f", voice {SAY_VOICE} at {SAY_RATE} wpm" if ENGINE == "say" else ""))

    placed, overruns, fresh = [], [], 0
    for i, beat in enumerate(beats):
        text = text_for.get(beat["id"])
        if not text:
            continue
        dest = clip_path(text)
        if not dest.exists():
            (synth_say if ENGINE == "say" else synth_gemini)(text, dest)
            fresh += 1
        secs = duration(dest)
        start = lead_in + beat["ready"] + 0.25
        nxt = beats[i + 1]["ready"] if i + 1 < len(beats) else scene
        room = (lead_in + nxt) - start
        over = secs > room
        if over:
            overruns.append(f"{beat['id']}: {secs:.1f}s spoken into {room:.1f}s")
        print(f"  {beat['id']:10s} at {start:5.1f}s  {secs:4.1f}s of {room:4.1f}s"
              + ("  OVERRUN" if over else ""))
        placed.append((start, dest))

    if overruns:
        raise SystemExit("narration overruns its beats, so the voice would "
                         "describe the next picture:\n  " + "\n  ".join(overruns))

    # Voice bed, then music ducked beneath it by the voice itself.
    inputs = ["-f", "lavfi", "-t", f"{video_len:.3f}", "-i", "anullsrc=r=24000:cl=mono"]
    filters, mixes = [], ["[0:a]"]
    for i, (start, path) in enumerate(placed, start=1):
        inputs += ["-i", str(path)]
        ms = int(start * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[d{i}]")
        mixes.append(f"[d{i}]")
    filters.append("".join(mixes)
                   + f"amix=inputs={len(placed) + 1}:duration=first:normalize=0[vo]")

    music_idx = len(placed) + 1
    if MUSIC.exists():
        inputs += ["-i", str(MUSIC)]
        fade_out = max(0.0, video_len - 2.6)
        filters.append(
            f"[{music_idx}:a]aformat=sample_rates=24000:channel_layouts=mono,"
            f"atrim=0:{video_len:.3f},asetpts=N/SR/TB,"
            f"volume={MUSIC_DB}dB,"
            f"afade=t=in:st=0:d=1.6,afade=t=out:st={fade_out:.2f}:d=2.6[bed]")
        # The voice keys a compressor on the music, so the bed steps back under
        # speech and comes forward between lines.
        filters.append("[bed][vo]sidechaincompress=threshold=0.02:ratio=9:"
                       "attack=18:release=380[ducked]")
        filters.append(
            "[ducked][vo]amix=inputs=2:duration=first:normalize=0,"
            f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,"
            "alimiter=limit=0.95[out]")
        print(f"music  {MUSIC.name}  at {MUSIC_DB} dB, ducked under the voice")
    else:
        filters.append(f"[vo]loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,"
                       "alimiter=limit=0.95[out]")
        print("music  none found, voice only")

    ff([*inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
        "-t", f"{video_len:.3f}", "-c:a", "aac", "-b:a", "192k", str(OUT)])

    loud = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(OUT),
         "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"I:\s*(-?\d+\.\d+) LUFS", loud.stderr)
    if m:
        print(f"integrated loudness {float(m.group(1)):.1f} LUFS "
              f"(target {TARGET_LUFS})")

    got = duration(OUT)
    print(f"\n{OUT.name}  {got:.2f}s against video {video_len:.2f}s"
          f"  ({fresh} synthesised, {len(placed) - fresh} cached)")
    if abs(got - video_len) > 0.25:
        raise SystemExit("audio and video do not end together")

    # Mux here rather than in record.py: the narration is timed to the beats of
    # the recording that already exists, so re-recording to attach it would
    # invalidate the timings it was built from.
    final = HERE / "heatline-demo-voiced.mp4"
    ff(["-i", str(VIDEO), "-i", str(OUT), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-movflags", "+faststart", str(final)])
    VIDEO.unlink()
    final.rename(VIDEO)

    v = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=duration", "-of", "csv=p=0", str(VIDEO)],
        capture_output=True, text=True, check=True).stdout.strip()
    a = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=duration", "-of", "csv=p=0", str(VIDEO)],
        capture_output=True, text=True, check=True).stdout.strip()
    print(f"{VIDEO.name}  video {float(v):.2f}s  audio {float(a):.2f}s")
    if abs(float(v) - float(a)) > 0.3:
        raise SystemExit("streams do not end together in the muxed file")


if __name__ == "__main__":
    main()
