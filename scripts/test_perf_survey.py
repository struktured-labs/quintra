#!/usr/bin/env python3
"""Headless fps regression floors from scripts/perf_survey.py.

Room-loop fps = loop_frame_counter advance per 60 host LCD frames (60 = no
slowdown). Floors sit a few fps under the values measured when the stage-3
Fold Star fix landed (#170), so real regressions fail and emulator noise
does not. Bosses are not gated here (the forced half-HP fixture triggers a
phase-change reload stall that is not combat cost).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perf_survey as ps  # noqa: E402

# scenario name -> (min avg, min worst 0.5 s window)
FLOORS = {
    "opening room (generated)": (57.0, 54.0),
    "16 crawlers fixed": (28.0, 23.0),
    "Fold Star x6 (stage 3)": (52.0, 48.0),
    "Fold Star x10 (stage 3)": (44.0, 40.0),
}


def main():
    fails = []
    for name, fn in ps.SCENARIOS:
        if name not in FLOORS:
            continue
        avg, worst, n = ps.summarize(fn())
        lo_avg, lo_worst = FLOORS[name]
        ok = avg >= lo_avg and worst >= lo_worst
        print(f"[perf-survey] {name:28s} avg {avg:5.1f} (>= {lo_avg})  "
              f"worst {worst:5.1f} (>= {lo_worst})  {'ok' if ok else 'LOW'}")
        if not ok:
            fails.append(name)
    assert not fails, f"fps below floor: {fails}"
    print("[perf-survey] PASS")


if __name__ == "__main__":
    main()
