#!/usr/bin/env python3
"""Headless fps regression floors from scripts/perf_survey.py.

Room-loop fps = loop_frame_counter advance per 60 host LCD frames (60 = no
slowdown). Floors sit a few fps under the values measured when the stage-3
Fold Star fix landed (#170), so real regressions fail and emulator noise
does not. Boss cases time 600 frames after a 120-frame settle so the
forced half-HP phase change (an arena rebuild on S8/S9) is not counted.
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
    # Bosses at half HP after the phase change settles (main-level floors;
    # raise them as the boss renderers land).
    "boss S1": (52.0, 44.0),
    "boss S2": (48.0, 36.0),
    "boss S3 Cinder Rex (S3)": (42.0, 22.0),
    "boss S4": (43.0, 32.0),
    "boss S5": (52.0, 36.0),
    "boss S6": (53.0, 34.0),
    "boss S7": (40.0, 30.0),
    "boss S8": (43.0, 32.0),
    "boss S9 Hexa Dragmar (S9)": (41.0, 28.0),
}


def main():
    fails = []
    for name, fn in ps.SCENARIOS:
        if name not in FLOORS:
            continue
        avg, worst, n = ps.summarize(fn())
        lo_avg, lo_worst = FLOORS[name]
        ok = avg >= lo_avg and worst >= lo_worst
        print(f"[perf-survey] {name:26s} avg {avg:5.1f} (>= {lo_avg})  "
              f"worst {worst:5.1f} (>= {lo_worst})  {'ok' if ok else 'LOW'}")
        if not ok:
            fails.append(name)
    assert not fails, f"fps below floor: {fails}"
    print("[perf-survey] PASS")


if __name__ == "__main__":
    main()
