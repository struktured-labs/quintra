#!/usr/bin/env python3
"""Open one manifest-verified five-minute Quintra training checkpoint."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from play_stage_state import CHAMPIONS, wait_for_player_ready
from quintra_playtest_report import (
    HumanPlaytestReport, remove_active_report, summary_line,
    write_active_report, write_report,
)
from quintra_pyboy_env import DEFAULT_ROM, QuintraPyBoyEnv


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--state-dir", type=Path,
                        default=ROOT / "tmp/timed-states")
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--check", action="store_true",
                        help="verify and restore headlessly, then exit")
    parser.add_argument("--report-dir", type=Path,
                        default=ROOT / "tmp" / "human-playtests",
                        help="write passive session JSON here when the window closes")
    parser.add_argument("--no-report", action="store_true",
                        help="disable the passive human-play session report")
    args = parser.parse_args()
    if args.minutes < 5 or args.minutes % 5:
        parser.error("--minutes must be a positive five-minute checkpoint")

    state = args.state_dir / f"quintra-training-{args.minutes:04d}m.pyboy"
    if not state.exists():
        parser.error(f"checkpoint is missing: {state}; run make timed-states")

    env = QuintraPyBoyEnv(args.rom, window="null" if args.check else "SDL2")
    reporter = None
    try:
        obs = env.load_state(state)
        champion = CHAMPIONS[obs["class_id"]] \
            if obs["class_id"] < len(CHAMPIONS) else f"class{obs['class_id']}"
        print(f"[play-timed-state] minute={args.minutes} stage={obs['stage']} "
              f"room={obs['room']} champion={champion} "
              f"mode={obs['difficulty']} hp={obs['hp']}/{obs['hp_max']} "
              f"state={state}")
        if args.check:
            return
        metadata = None if args.no_report else {
            "rom": str(args.rom.resolve()),
            "rom_sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
            "state": str(state.resolve()),
            "stage": obs["stage"],
            "checkpoint": f"timed-{args.minutes:04d}m",
            "champion": champion,
            "difficulty": obs["difficulty"],
        }
        assert env.pb is not None
        if not wait_for_player_ready(env.pb):
            return
        if metadata is not None:
            reporter = HumanPlaytestReport(obs, metadata)
            write_active_report(reporter.snapshot(), args.report_dir)
        while env.pb.tick():
            if reporter is not None:
                reporter.sample(env.observe(include_tiles=False))
                if reporter.frames % 300 == 0:
                    write_active_report(reporter.snapshot(), args.report_dir)
    except KeyboardInterrupt:
        print("[play-timed-state] window interrupted")
    finally:
        if reporter is not None and env.pb is not None:
            result = reporter.finish(env.observe(include_tiles=False))
            write_active_report(result, args.report_dir)
            report_path = write_report(result, args.report_dir)
            remove_active_report(result, args.report_dir)
            print(f"[play-timed-state] report {summary_line(result)}")
            print(f"[play-timed-state] wrote {report_path}")
        env.close()


if __name__ == "__main__":
    main()
