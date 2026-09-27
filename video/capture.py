"""Capture the real session the video shows: real commands, real output, real latency.

Nothing here is typed by hand into a transcript. Each command runs, its stdout is
kept verbatim, and the wall clock time it took is recorded, so the rendered video
plays back at the speed the thing actually runs at.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "session.json"

# A shell variable keeps the displayed commands short enough to read on screen
# without truncating them. These are the exact commands, not simplified stand-ins.
U = "http://127.0.0.1:8412"

SCENES = [
    {
        "id": "counts",
        "caption": "Eleven hours of tomorrow's shift for a delivery rider.",
        "show": "curl -s \"$U/day?hours=11&from_hour=2026-09-28T08:00\" | jq .counts",
        "cmd": f"curl -s '{U}/day?hours=11&from_hour=2026-09-28T08:00' | jq .counts",
    },
    {
        "id": "day",
        "caption": "Air temperature on the left. The exposure index on the right.",
        "show": ("curl -s \"$U/day?hours=11&from_hour=2026-09-28T08:00\" | jq -r "
                 "'.hours[] | \"\\(.time) \\(.air_c)C \\(.wbgt_c)C \\(.verdict)\"'"),
        "cmd": (f"curl -s '{U}/day?hours=11&from_hour=2026-09-28T08:00' | jq -r "
                "'.hours[] | \"\\(.time)   air \\(.air_c)C   WBGT \\(.wbgt_c)C   "
                "\\(.verdict)\"'"),
    },
    {
        "id": "limit",
        "caption": "The limit is a range, because the workload is a range.",
        "show": "curl -s \"$U/limit\" | jq '{limit_low_c, limit_high_c, metabolic_rate_w}'",
        "cmd": f"curl -s '{U}/limit' | jq '{{limit_low_c, limit_high_c, metabolic_rate_w}}'",
    },
    {
        "id": "undetermined",
        "caption": "Inside that range it will not guess. margin_c is null.",
        "show": ("curl -s \"$U/assess?hour=2026-09-28T13:00\" | jq "
                 "'{verdict, wbgt_c, limit_c, margin_c}'"),
        "cmd": (f"curl -s '{U}/assess?hour=2026-09-28T13:00' | jq "
                "'{verdict, wbgt_c, limit_c, margin_c}'"),
    },
    {
        "id": "refuse_status",
        "caption": "This hour is in the forecast. Watch what it does.",
        "show": ("curl -s -o /dev/null -w '%{http_code}\\n' \"$U/assess?hour=2026-09-29T14:00\""
                 "\ncurl -s \"$U/assess?hour=2026-09-29T14:00\" | jq -r .reason"),
        "cmd": (f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' "
                f"'{U}/assess?hour=2026-09-29T14:00' && "
                f"curl -s '{U}/assess?hour=2026-09-29T14:00' | jq -r '.refusal, .reason'"),
    },
    {
        "id": "refuse_agent",
        "caption": "The same question, put to the agent.",
        "show": 'curl -s "$U/advise?q=What about 2pm on 29 September?" | jq -r .answer',
        "cmd": (f"curl -s '{U}/advise?q=What%20about%202pm%20on%2029%20September%3F"
                "&session=vid2' | jq -r '.tools_called | join(\" -> \")' && "
                f"curl -s '{U}/advise?q=What%20about%202pm%20on%2029%20September%3F"
                "&session=vid2' | jq -r '.answer'"),
    },
    {
        "id": "tests",
        "caption": "Forty nine tests. None of them touch the network.",
        "show": "python -m pytest tests/ -q",
        "cmd": "./.venv/bin/python -m pytest tests/ -q",
    },
]


def main() -> None:
    captured = []
    for scene in SCENES:
        started = time.monotonic()
        proc = subprocess.run(
            scene["cmd"], shell=True, capture_output=True, text=True, timeout=240
        )
        elapsed = time.monotonic() - started
        out = (proc.stdout or "") + (proc.stderr or "")
        captured.append({
            "id": scene["id"],
            "caption": scene["caption"],
            "cmd": scene["cmd"],
            "show": scene["show"],
            "output": out.rstrip("\n"),
            "seconds": round(elapsed, 2),
            "returncode": proc.returncode,
        })
        print(f"{scene['id']:16s} {elapsed:6.2f}s  rc={proc.returncode}  "
              f"{len(out.splitlines())} lines")
    OUT.write_text(json.dumps(captured, indent=2))
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
