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
SRT = HERE / "heatline-demo.srt"

ENGINE = os.environ.get("HEATLINE_TTS", "say")

# macOS, local, no quota. Aman is en_IN and is one of the neural Siri voices,
# which is why it does not have the broken, formant quality of Rishi; Aashan
# picked it from a four-way blind comparison on 2026-09-27.
#
# The rate flag does not work on this voice. Measured on one sentence, -r 150
# through -r 185 all came out between 205 and 215 words per minute, and -r 190
# truncated the sentence outright. So -r is left at the value that measured
# most consistently and the pace is set afterwards, per line, from the
# measured rate of that line. That also flattens the spread between lines:
# commas and full stops made otherwise identical settings read anywhere from
# 80 to 259 wpm, which is audible as the voice lurching.
SAY_VOICE = os.environ.get("HEATLINE_VOICE", "Aman (English (India))")
SAY_RATE = int(os.environ.get("HEATLINE_RATE", "175"))

# Words per minute, after stretching. Documentary narration sits at 140 to 160
# and product demos a little quicker. The shipped cut measured 197 to 283.
TARGET_WPM = float(os.environ.get("HEATLINE_TARGET_WPM", "165"))
# atempo below about 0.75 starts to sound processed, so the stretch is clamped
# and a line that would need more than this is a writing problem to fix in the
# cue sheet instead.
MIN_TEMPO, MAX_TEMPO = 0.74, 1.30

# This voice is not reliable clip to clip. The same sentence at the same
# setting measured 171 wpm on one run and 90 on another, and -r 190 once
# returned a 14 word line in 2.2s, which is it giving up part way through.
# Outside this band the clip is wrong rather than merely fast or slow, and
# since clips are cached by content hash a bad one would otherwise be pinned
# in place for good. So: measure, reject, speak it again.
PLAUSIBLE_WPM = (130.0, 320.0)
SYNTH_ATTEMPTS = 6

# A gap longer than this reads as the audio having failed.
MAX_SILENCE = float(os.environ.get("HEATLINE_MAX_SILENCE", "2.2"))
# Speech as a share of the running time. The previous cut was 60 percent, with
# two stretches of ten and nine seconds carrying nothing at all.
MIN_COVERAGE = float(os.environ.get("HEATLINE_MIN_COVERAGE", "0.82"))

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
# Levels, all set by measurement.
#
# Two earlier mixes were wrong in ways worth recording. The first came out at
# -31.8 LUFS integrated, close to inaudible. The second fixed the level but put
# the bed only 4.6 dB under the voice, and ran loudnorm across the finished mix,
# which lifts quiet passages: the music-only gaps measured louder than the
# speech and the bed audibly swelled between lines.
#
# So: the voice is the loud element, the music is set by a **static** gain
# computed from its own measured loudness, and nothing dynamic touches the mix.
# A static gain cannot pump, which is the whole reason for doing it this way.
VOICE_LUFS = float(os.environ.get("HEATLINE_VOICE_LUFS", "-16"))
# 18 dB under the voice. Below about 15 the bed starts competing with speech.
MUSIC_LUFS = float(os.environ.get("HEATLINE_MUSIC_LUFS", "-34"))

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


# Breath between two lines on the same picture, and before the first one.
BREATH = 0.35


def cues_for(facts: dict) -> list[tuple[str, str]]:
    """The script, as (beat, line), in order.

    Anchored to each beat's **at**, the moment its picture changes, not to its
    ready time. Keying to ready was the sync bug: the ask beat's picture
    changed at 4.5s and its line spoke at 15.8s, because ready was held back
    by the agent's latency. A line describes what is on screen while it is on
    screen, so it belongs at at.

    Lines on the same beat are chained one after another with a breath
    between, rather than each carrying a hand written offset. Hand written
    offsets have to be re-derived every time a line is edited, and getting one
    wrong is inaudible until someone watches the whole thing.

    Every number spoken is read from what this recording put on screen.
    """
    air = say_number(facts.get("air_c") or "")
    wbgt = say_number(facts.get("wbgt_c") or "")
    counts = facts.get("counts") or {}
    undet = ONES.get(str(counts.get("undetermined", "")),
                     str(counts.get("undetermined", "")))
    return [
        ("open",
         "A delivery rider in Karachi wants to know if they can work this "
         "afternoon."),

        ("ask",
         "They ask in their own words, the way they would ask a person."),
        ("ask",
         "The agent does not answer from memory. It works out which hour this "
         "afternoon means, reads the published forecast, and computes the "
         "heat exposure."),

        ("verdict",
         f"The thermometer reads {air} degrees, and nobody issues a heat "
         "warning about that."),
        ("verdict",
         f"The exposure index reads {wbgt}, and that is the one the "
         "occupational limit is set against."),

        ("band",
         "Blue is the exposure. The amber band is the limit published by "
         "NIOSH."),
        ("band",
         "It is a band and not a line, because the limit depends on how hard "
         "the work is."),

        ("strip",
         f"For {undet} of these hours the tool will not call it either way."),
        ("strip",
         "Inside the band it depends on how hard this rider is really "
         "working, and a forecast cannot know that."),

        ("refuse",
         "Now they ask about an hour further out than the forecast it trusts "
         "goes."),

        ("withheld",
         "It declines, and it does not soften it. Every reading is withheld, "
         "in both languages."),

        ("close",
         "Every formula is quoted from the document it came from. The code "
         "and the sources are open."),
    ]


def schedule(cues, clip_secs):
    """Place each cue, chaining lines that share a beat.

    Returns (beat, offset, text) with the offset measured from that beat's at,
    and the room each beat therefore needs.
    """
    placed, needed, running = [], {}, {}
    for beat, text in cues:
        offset = running.get(beat, 0.0) + BREATH
        placed.append((beat, offset, text))
        running[beat] = offset + clip_secs(text)
        needed[beat] = running[beat] + BREATH
    return placed, needed


def clip_path(text: str) -> Path:
    key = hashlib.sha256(
        f"{ENGINE}|{SAY_VOICE}|{SAY_RATE}|{TARGET_WPM}|{GEMINI_VOICE}"
        f"|{GEMINI_TEMPO}|{text}"
        .encode()).hexdigest()[:16]
    return CLIPS / f"{key}.wav"


def ff(args: list[str]) -> None:
    """Run ffmpeg, keeping stderr. A swallowed error has cost a batch before."""
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{r.stderr.strip()}")


def normalise(src: Path, dest: Path, tempo: float = 1.0) -> None:
    """One pace and one loudness for every line, so no line jumps out.

    The leading and trailing silence goes too. A clip that opens with half a
    second of padding lands half a second late however carefully it was placed,
    which is the kind of drift that reads as the voice being out of sync.
    """
    stretch = "" if abs(tempo - 1.0) < 0.005 else f"atempo={tempo:.4f},"
    ff(["-i", str(src), "-af",
        "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0"
        ":stop_periods=-1:stop_threshold=-50dB:stop_silence=0.25,"
        + stretch
        + f"loudnorm=I={VOICE_LUFS}:TP=-1.5:LRA=7",
        "-ar", "24000", "-ac", "1", str(dest)])


def synth_say(text: str, dest: Path) -> None:
    """Speak it, measure it, then stretch it to the target pace.

    Two passes because the pace cannot be asked for: the first pass is only
    there to find out how fast this voice happened to read this line.
    """
    words = len(text.split())
    aiff = dest.with_suffix(".aiff")
    probe = dest.with_suffix(".probe.wav")
    low, high = PLAUSIBLE_WPM

    measured = 0.0
    for attempt in range(1, SYNTH_ATTEMPTS + 1):
        subprocess.run(["say", "-v", SAY_VOICE, "-r", str(SAY_RATE),
                        "-o", str(aiff), text], check=True)
        normalise(aiff, probe)
        measured = words / duration(probe) * 60
        probe.unlink()
        if low <= measured <= high:
            break
        print(f"      read at {measured:5.1f} wpm, outside {low:.0f} to "
              f"{high:.0f}, speaking it again ({attempt}/{SYNTH_ATTEMPTS})")
    else:
        aiff.unlink(missing_ok=True)
        raise SystemExit(
            f"the voice would not read this line plausibly in "
            f"{SYNTH_ATTEMPTS} attempts, last at {measured:.0f} wpm:\n  "
            f"{text}")

    tempo = min(MAX_TEMPO, max(MIN_TEMPO, TARGET_WPM / measured))
    normalise(aiff, dest, tempo)
    aiff.unlink()

    got = words / duration(dest) * 60
    print(f"      {words:3d}w read at {measured:5.1f} wpm, "
          f"tempo {tempo:.2f} to {got:5.1f} wpm")


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


def loudness(path: Path, seconds: float | None = None) -> float:
    """Integrated loudness in LUFS, measured rather than assumed."""
    args = ["ffmpeg", "-hide_banner", "-nostats"]
    if seconds:
        args += ["-t", f"{seconds}"]
    args += ["-i", str(path), "-af", "ebur128=framelog=quiet", "-f", "null", "-"]
    r = subprocess.run(args, capture_output=True, text=True)
    m = re.search(r"I:\s*(-?\d+\.\d+) LUFS", r.stderr)
    if not m:
        raise SystemExit(f"could not measure loudness of {path.name}")
    return float(m.group(1))


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
    cues = cues_for(facts)
    video_len = duration(VIDEO)
    at_of = {b["id"]: b["at"] for b in beats}
    order = [b["id"] for b in beats]

    CLIPS.mkdir(exist_ok=True)
    print(f"engine {ENGINE}"
          + (f", voice {SAY_VOICE} at {SAY_RATE} wpm" if ENGINE == "say" else ""))

    fresh = 0
    for beat_id, text in cues:
        if beat_id not in at_of:
            raise SystemExit(f"cue anchored to unknown beat {beat_id!r}")
        dest = clip_path(text)
        if not dest.exists():
            (synth_say if ENGINE == "say" else synth_gemini)(text, dest)
            fresh += 1

    scheduled, needed = schedule(cues, lambda t: duration(clip_path(t)))
    placed = [{
        "beat": beat_id,
        "start": lead_in + at_of[beat_id] + offset,
        "secs": duration(clip_path(text)),
        "path": clip_path(text),
        "words": len(text.split()),
        "text": text,
    } for beat_id, offset, text in scheduled]
    placed.sort(key=lambda c: c["start"])

    # Each beat must hold long enough for its own lines. This is the number to
    # put in the beat's hold in demo.js if it does not.
    room = {}
    for i, beat_id in enumerate(order):
        nxt = at_of[order[i + 1]] if i + 1 < len(order) else scene
        room[beat_id] = nxt - at_of[beat_id]

    # Checks, in the order the faults were found in the shipped cut.
    faults: list[str] = []
    previous = None
    for cue in placed:
        cue["wpm"] = cue["words"] / cue["secs"] * 60
        cue["end"] = cue["start"] + cue["secs"]
        cue["gap"] = cue["start"] - (previous["end"] if previous else 0.0)
        # 1. Overlap. Two voices at once is worse than either alone.
        if previous and cue["start"] < previous["end"] - 0.05:
            faults.append(
                f"{previous['beat']} runs {previous['end'] - cue['start']:.1f}s "
                f"into {cue['beat']}")
        # 2. Dead air.
        if cue["gap"] > MAX_SILENCE:
            faults.append(f"{cue['gap']:.1f}s of silence before {cue['beat']} "
                          f"at {cue['start']:.1f}s")
        # 3. Rushed. Measured, not assumed: say does not read at its nominal
        #    rate, and the shipped cut had lines at 283 wpm.
        # The floor is the synthesiser's, not the writer's: some lines come out
        # of say at 250 wpm and the stretch is clamped at 0.74, so a short
        # punchy line can land here at 185. The average is checked below.
        if cue["wpm"] > 190:
            faults.append(f"{cue['beat']} at {cue['start']:.1f}s reads at "
                          f"{cue['wpm']:.0f} wpm")
        previous = cue

    # 4. A line must still be on its own picture when it finishes.
    for cue in placed:
        nxt = [at_of[i] for i in order
               if at_of[i] > at_of[cue["beat"]] + 0.001]
        if nxt:
            boundary = lead_in + min(nxt)
            if cue["end"] > boundary + 0.6:
                faults.append(
                    f"{cue['beat']} at {cue['start']:.1f}s is still speaking "
                    f"{cue['end'] - boundary:.1f}s after the picture changed")

    tail = (lead_in + scene) - placed[-1]["end"] if placed else 0.0
    spoken = sum(c["secs"] for c in placed)
    coverage = spoken / video_len
    if tail > MAX_SILENCE:
        faults.append(f"{tail:.1f}s of silence at the end")
    if coverage < MIN_COVERAGE:
        faults.append(f"speech covers {coverage:.0%} of the running time, "
                      f"under {MIN_COVERAGE:.0%}")
    average = sum(c["words"] for c in placed) / spoken * 60
    if average > 175:
        faults.append(f"the whole script averages {average:.0f} wpm")

    for beat_id, want in needed.items():
        if room[beat_id] < want - 0.05:
            faults.append(
                f"beat {beat_id} holds {room[beat_id]:.1f}s but its lines need "
                f"{want:.1f}s: raise its hold in demo.js by "
                f"{want - room[beat_id]:.1f}s")

    print(f"  {'beat':10s} {'in':>6s} {'out':>6s} {'gap':>5s} {'secs':>5s} "
          f"{'wpm':>4s}")
    for cue in placed:
        print(f"  {cue['beat']:10s} {cue['start']:6.1f} {cue['end']:6.1f} "
              f"{cue['gap']:5.1f} {cue['secs']:5.1f} {cue['wpm']:4.0f}")
    print(f"  speech {spoken:.1f}s of {video_len:.1f}s ({coverage:.0%}), "
          f"average {average:.0f} wpm, tail {tail:.1f}s")

    if faults:
        raise SystemExit(
            "the narration does not fit the picture:\n  " + "\n  ".join(faults))

    # Subtitles from the same cue sheet the voice was built from, so the
    # transcript cannot drift from what is said. The file that was here before
    # belonged to the first cut, a terminal screencast, and described entirely
    # different content at timings from an 88s edit.
    def stamp(t: float) -> str:
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600_000)
        m, ms = divmod(ms, 60_000)
        sec, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    SRT.write_text("\n".join(
        f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n"
        for i, c in enumerate(placed, start=1)), encoding="utf-8")
    print(f"  subtitles {SRT.name}, {len(placed)} cues")

    placed = [(c["start"], c["path"]) for c in placed]

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
        # Measure the track, then apply one fixed gain. No compressor keyed on
        # the voice: at 18 dB down the bed does not need ducking, and ducking is
        # what made the previous mix breathe in and out.
        src = loudness(MUSIC, seconds=video_len)
        gain = MUSIC_LUFS - src
        inputs += ["-i", str(MUSIC)]
        fade_out = max(0.0, video_len - 2.8)
        filters.append(
            f"[{music_idx}:a]aformat=sample_rates=24000:channel_layouts=mono,"
            f"atrim=0:{video_len:.3f},asetpts=N/SR/TB,"
            f"volume={gain:.2f}dB,"
            f"afade=t=in:st=0:d=2.0,afade=t=out:st={fade_out:.2f}:d=2.8[bed]")
        filters.append("[bed][vo]amix=inputs=2:duration=first:normalize=0,"
                       "alimiter=limit=0.95[out]")
        print(f"music  {MUSIC.name}")
        print(f"       measured {src:.1f} LUFS, gain {gain:+.1f} dB "
              f"to sit at {MUSIC_LUFS:.0f} LUFS, "
              f"{abs(MUSIC_LUFS - VOICE_LUFS):.0f} dB under the voice")
    else:
        filters.append("[vo]alimiter=limit=0.95[out]")
        print("music  none found, voice only")

    ff([*inputs, "-filter_complex", ";".join(filters), "-map", "[out]",
        "-t", f"{video_len:.3f}", "-c:a", "aac", "-b:a", "192k", str(OUT)])

    loud = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(OUT),
         "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"I:\s*(-?\d+\.\d+) LUFS", loud.stderr)
    if m:
        print(f"integrated loudness {float(m.group(1)):.1f} LUFS")

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
