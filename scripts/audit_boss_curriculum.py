#!/usr/bin/env python3
"""Run the controller-only pilot against progression-matched bosses.

Normal is the default and canonical balance target. Easy runs are comparative
diagnostics for the broad human-test assist, never a second release gate.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from quintra_pyboy_env import ACTION_A, ACTION_B, DEFAULT_ROM, QuintraPyBoyEnv
from run_pyboy_checkpoints import controller_action


ROOT = Path(__file__).resolve().parent.parent
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")


def giant_hp(obs: dict) -> int:
    giants = [enemy for enemy in obs["hostiles"] if enemy["giant"]]
    return giants[0]["hp"] if giants else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--state-dir", type=Path,
                        default=ROOT / "tmp" / "stage-states")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "tmp" / "boss-curriculum-audit.csv")
    parser.add_argument("--frames", type=int, default=3600,
                        help="maximum frames per matchup (default: 3600/60 sec)")
    parser.add_argument("--step-frames", type=int, default=1,
                        help="controller decision interval (default: every frame)")
    parser.add_argument("--difficulty", choices=("normal", "easy"),
                        default="normal",
                        help="checkpoint mode to measure (default: normal)")
    parser.add_argument("--stage", type=int, action="append", dest="stages",
                        help="stage number to sample; repeatable (default: all)")
    args = parser.parse_args()
    stages = args.stages or list(range(1, 10))
    if any(not 1 <= stage <= 9 for stage in stages):
        parser.error("--stage must be in 1..9")
    if not 1 <= args.step_frames <= 4:
        parser.error("--step-frames must be in 1..4")

    rows = []
    env = QuintraPyBoyEnv(args.rom)
    try:
        for stage in stages:
            for champion in CHAMPIONS:
                suffix = "-easy" if args.difficulty == "easy" else ""
                state = args.state_dir / (
                    f"quintra-stage-{stage:02d}-boss-{champion}{suffix}.pyboy")
                obs = env.load_state(state)
                if obs["difficulty"] != args.difficulty:
                    raise RuntimeError(
                        f"{state.name}: restored {obs['difficulty']} instead of "
                        f"{args.difficulty}")
                initial_hp = giant_hp(obs)
                before_bosses = obs["bosses"]
                elapsed = 0
                attack_frames = signature_frames = movement_frames = 0
                projectile_frames = 0
                min_reach = 999
                max_reach = 0
                while elapsed < args.frames:
                    frames = min(args.step_frames, args.frames - elapsed)
                    giants = [enemy for enemy in obs["hostiles"] if enemy["giant"]]
                    if giants:
                        reach = max(abs(giants[0]["x"] - obs["x"]),
                                    abs(giants[0]["y"] - obs["y"]))
                        min_reach = min(min_reach, reach)
                        max_reach = max(max_reach, reach)
                    action = controller_action(obs, elapsed)
                    if action & ACTION_A:
                        attack_frames += frames
                    if action & ACTION_B:
                        signature_frames += frames
                    if action & 0x0F:
                        movement_frames += frames
                    if obs["projectiles"]:
                        projectile_frames += frames
                    obs, _, terminal, _ = env.step(action, frames)
                    elapsed += frames
                    if obs["bosses"] > before_bosses or terminal:
                        break
                cleared = obs["bosses"] > before_bosses
                remaining = 0 if cleared else giant_hp(obs)
                row = {
                    "difficulty": args.difficulty,
                    "stage": stage,
                    "champion": champion,
                    "cleared": int(cleared),
                    "survived": int(not env.is_terminal(obs)),
                    "frames": elapsed,
                    "player_hp": obs["hp"],
                    "player_hp_max": obs["hp_max"],
                    "boss_hp_start": initial_hp,
                    "boss_hp_end": remaining,
                    "damage": max(0, initial_hp - remaining),
                    "attack_frames": attack_frames,
                    "signature_frames": signature_frames,
                    "movement_frames": movement_frames,
                    "projectile_frames": projectile_frames,
                    "min_reach": 0 if min_reach == 999 else min_reach,
                    "max_reach": max_reach,
                }
                rows.append(row)
                print(f"[boss-audit] {args.difficulty} s{stage} {champion}: "
                      f"{'CLEAR' if cleared else 'alive' if row['survived'] else 'down'} "
                      f"t={elapsed} hero={obs['hp']}/{obs['hp_max']} "
                      f"boss={remaining}/{initial_hp} "
                      f"A={attack_frames} B={signature_frames} "
                      f"move={movement_frames} reach={row['min_reach']}..{max_reach}")
    finally:
        env.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(args.out.suffix + ".tmp")
    with temp.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(args.out)
    clears = sum(row["cleared"] for row in rows)
    survived = sum(row["survived"] for row in rows)
    print(f"[boss-audit] wrote {args.out}: mode={args.difficulty} "
          f"clears={clears}/{len(rows)}, "
          f"survived={survived}/{len(rows)}")


if __name__ == "__main__":
    main()
