#!/usr/bin/env python3
"""Open one manifest-verified Quintra stage checkpoint in interactive PyBoy."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from pyboy.utils import WindowEvent

from quintra_pyboy_env import DEFAULT_ROM, QuintraPyBoyEnv
from quintra_playtest_report import (
    HumanPlaytestReport, remove_active_report, summary_line,
    write_active_report, write_report,
)


ROOT = Path(__file__).resolve().parent.parent
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
READY_PRESSES = {
    int(WindowEvent.PRESS_ARROW_UP), int(WindowEvent.PRESS_ARROW_RIGHT),
    int(WindowEvent.PRESS_ARROW_DOWN), int(WindowEvent.PRESS_ARROW_LEFT),
    int(WindowEvent.PRESS_BUTTON_A), int(WindowEvent.PRESS_BUTTON_B),
    int(WindowEvent.PRESS_BUTTON_SELECT), int(WindowEvent.PRESS_BUTTON_START),
}
READY_RELEASES = (
    WindowEvent.RELEASE_ARROW_UP, WindowEvent.RELEASE_ARROW_RIGHT,
    WindowEvent.RELEASE_ARROW_DOWN, WindowEvent.RELEASE_ARROW_LEFT,
    WindowEvent.RELEASE_BUTTON_A, WindowEvent.RELEASE_BUTTON_B,
    WindowEvent.RELEASE_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_START,
)


def wait_for_player_ready(pb) -> bool:
    """Freeze a loaded checkpoint until the SDL2 window has player focus."""
    print("[play-state] PAUSED — focus the game window and press any control "
          "(or P) to begin")
    pb.send_input(WindowEvent.PAUSE)
    if not pb.tick():
        return False
    while pb.paused:
        if not pb.tick():
            return False
        if any(int(event) in READY_PRESSES for event in pb.events):
            # Treat the first ordinary control as readiness, not gameplay.
            # Release the whole joypad before unpausing so a tester cannot
            # accidentally fire, open a menu, or walk into danger merely by
            # bringing the window to life.
            for event in READY_RELEASES:
                pb.send_input(event)
            pb.send_input(WindowEvent.UNPAUSE)
    print("[play-state] live — session reporting has begun")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Play a generated Normal/Easy dungeon, Riftwild, or village checkpoint")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--state-dir", type=Path,
                        default=ROOT / "tmp" / "stage-states")
    parser.add_argument("--stage", type=int, default=1)
    parser.add_argument("--difficulty", choices=("normal", "easy"),
                        default="normal")
    parser.add_argument("--checkpoint",
                        choices=("entry", "sanctuary", "boss", "riftwild", "village"),
                        default="entry")
    parser.add_argument("--champion", choices=CHAMPIONS, default="wolfkin")
    parser.add_argument("--check", action="store_true",
                        help="verify and restore the state headlessly, then exit")
    parser.add_argument("--report-dir", type=Path,
                        default=ROOT / "tmp" / "human-playtests",
                        help="write passive session JSON here when the window closes")
    parser.add_argument("--no-report", action="store_true",
                        help="disable the passive human-play session report")
    args = parser.parse_args()
    if not 1 <= args.stage <= 9:
        parser.error("--stage must be in 1..9")

    suffix = "-easy" if args.difficulty == "easy" else ""
    if args.checkpoint == "riftwild":
        if args.stage not in range(1, 9):
            parser.error("Riftwild checkpoints use --stage 1 through 8 (the dungeon just cleared)")
        state = args.state_dir / (
            f"quintra-riftwild-after-stage-{args.stage:02d}-"
            f"{args.champion}{suffix}.pyboy")
    elif args.checkpoint == "village":
        if args.stage not in (3, 6):
            parser.error("village checkpoints use --stage 3 or 6 (the dungeon just cleared)")
        state = args.state_dir / (
            f"quintra-village-after-stage-{args.stage:02d}-"
            f"{args.champion}{suffix}.pyboy")
    else:
        state = args.state_dir / (
            f"quintra-stage-{args.stage:02d}-{args.checkpoint}-"
            f"{args.champion}{suffix}.pyboy")
    if not state.exists():
        parser.error(f"checkpoint is missing: {state}; run make stage-states")

    env = QuintraPyBoyEnv(args.rom, window="null" if args.check else "SDL2")
    reporter = None
    try:
        obs = env.load_state(state)
        location = ((f"{args.checkpoint}-after-stage={args.stage} "
                     f"next-stage={obs['stage']}")
                    if args.checkpoint in ("riftwild", "village")
                    else f"stage={obs['stage']}")
        print(f"[play-state] {location} champion={args.champion} "
              f"checkpoint={args.checkpoint} mode={obs['difficulty']} "
              f"room={obs['room']} hp={obs['hp']}/{obs['hp_max']} state={state}")
        if args.check:
            return
        metadata = None if args.no_report else {
            "rom": str(args.rom.resolve()),
            "rom_sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(),
            "state": str(state.resolve()),
            "stage": args.stage,
            "checkpoint": args.checkpoint,
            "champion": args.champion,
            "difficulty": args.difficulty,
        }
        assert env.pb is not None
        if not wait_for_player_ready(env.pb):
            return
        if metadata is not None:
            reporter = HumanPlaytestReport(obs, metadata)
            # Create evidence before the first interactive frame, then refresh
            # every five seconds. A graphics crash, SIGKILL, or host-session
            # teardown can no longer erase the whole human playtest.
            write_active_report(reporter.snapshot(), args.report_dir)
        while env.pb.tick():
            if reporter is not None:
                reporter.sample(env.observe(include_tiles=False))
                if reporter.frames % 300 == 0:
                    write_active_report(reporter.snapshot(), args.report_dir)
    except KeyboardInterrupt:
        print("[play-state] window interrupted")
    finally:
        if reporter is not None and env.pb is not None:
            result = reporter.finish(env.observe(include_tiles=False))
            write_active_report(result, args.report_dir)
            report_path = write_report(result, args.report_dir)
            remove_active_report(result, args.report_dir)
            print(f"[play-state] report {summary_line(result)}")
            print(f"[play-state] wrote {report_path}")
        env.close()


if __name__ == "__main__":
    main()
