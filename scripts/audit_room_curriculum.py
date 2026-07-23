#!/usr/bin/env python3
"""Measure progression-matched ordinary rooms with controller input.

This is a diagnostic, not a balance gate.  It starts from every manifest-bound
stage-entry state in the requested mode, stops at the first room transition or
death, and records survival pressure separately from the giant-boss curriculum.
Normal remains the default and canonical balance target; Easy comparison runs
only measure whether the broad human-test assist is doing its job.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from quintra_pyboy_env import DEFAULT_ROM, QuintraPyBoyEnv
from run_pyboy_checkpoints import controller_action


ROOT = Path(__file__).resolve().parent.parent
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--state-dir", type=Path,
                        default=ROOT / "tmp" / "stage-states")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "tmp" / "room-curriculum-audit.csv")
    parser.add_argument("--frames", type=int, default=1800,
                        help="maximum frames per room (default: 1800/30 sec)")
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
    if args.frames < 1:
        parser.error("--frames must be positive")
    if not 1 <= args.step_frames <= 4:
        parser.error("--step-frames must be in 1..4")

    rows: list[dict[str, int | str]] = []
    env = QuintraPyBoyEnv(args.rom)
    try:
        for stage in stages:
            for champion in CHAMPIONS:
                suffix = "-easy" if args.difficulty == "easy" else ""
                state = args.state_dir / (
                    f"quintra-stage-{stage:02d}-entry-{champion}{suffix}.pyboy")
                obs = env.load_state(state)
                if obs["difficulty"] != args.difficulty:
                    raise RuntimeError(
                        f"{state.name}: restored {obs['difficulty']} instead of "
                        f"{args.difficulty}")
                start_room = obs["room"]
                start_hp = obs["hp"]
                start_hostiles = len(obs["hostiles"])
                start_hostile_hp = sum(enemy["hp"] for enemy in obs["hostiles"])
                start_roster = ";".join(
                    f"{enemy['kind']}:{enemy['hp']}" for enemy in obs["hostiles"])
                if any(enemy["giant"] for enemy in obs["hostiles"]):
                    raise RuntimeError(f"{state.name}: entry fixture contains giant")

                elapsed = 0
                min_hp = start_hp
                damage_taken = 0
                previous_hp = start_hp
                max_hostiles = start_hostiles
                max_projectiles = len(obs["projectiles"])
                hostiles_defeated_at = -1
                hostiles_end = start_hostiles
                hostile_hp_end = start_hostile_hp
                while elapsed < args.frames:
                    frames = min(args.step_frames, args.frames - elapsed)
                    action = controller_action(obs, elapsed)
                    obs, _, terminal, _ = env.step(action, frames)
                    elapsed += frames
                    if obs["hp"] < previous_hp:
                        damage_taken += previous_hp - obs["hp"]
                    previous_hp = obs["hp"]
                    min_hp = min(min_hp, obs["hp"])
                    max_hostiles = max(max_hostiles, len(obs["hostiles"]))
                    max_projectiles = max(max_projectiles, len(obs["projectiles"]))
                    if hostiles_defeated_at < 0 and not obs["hostiles"]:
                        hostiles_defeated_at = elapsed
                    if obs["room"] == start_room:
                        hostiles_end = len(obs["hostiles"])
                        hostile_hp_end = sum(enemy["hp"] for enemy in obs["hostiles"])
                    if terminal or obs["room"] != start_room:
                        break

                exited = obs["room"] != start_room
                died = env.is_terminal(obs) and not obs["victory"]
                resolved = exited or hostiles_defeated_at >= 0
                row = {
                    "difficulty": args.difficulty,
                    "stage": stage,
                    "champion": champion,
                    "resolved": int(resolved),
                    "exited": int(exited),
                    "died": int(died),
                    "survived": int(not died),
                    "frames": elapsed,
                    "hp_start": start_hp,
                    "hp_end": obs["hp"],
                    "hp_min": min_hp,
                    "damage_taken": damage_taken,
                    "hostiles_start": start_hostiles,
                    "hostile_hp_start": start_hostile_hp,
                    "hostile_roster_start": start_roster,
                    "hostiles_end": hostiles_end,
                    "hostile_hp_end": hostile_hp_end,
                    "hostiles_max": max_hostiles,
                    "projectiles_max": max_projectiles,
                    "hostiles_defeated_at": hostiles_defeated_at,
                    "room_end": obs["room"],
                }
                rows.append(row)
                outcome = "EXIT" if exited else "CLEAR" if hostiles_defeated_at >= 0 \
                    else "DOWN" if died else "PRESSURE"
                print(f"[room-audit] {args.difficulty} s{stage} {champion}: {outcome} "
                      f"t={elapsed} hp={obs['hp']}/{start_hp} "
                      f"loss={damage_taken} foes={start_hostiles} "
                      f"foe_hp={start_hostile_hp} roster={start_roster} "
                      f"bullets<={max_projectiles}")
    finally:
        env.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(args.out.suffix + ".tmp")
    with temp.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(args.out)

    resolved = sum(int(row["resolved"]) for row in rows)
    exits = sum(int(row["exited"]) for row in rows)
    deaths = sum(int(row["died"]) for row in rows)
    print(f"[room-audit] wrote {args.out}: mode={args.difficulty} "
          f"resolved={resolved}/{len(rows)}, "
          f"exits={exits}, deaths={deaths}, "
          f"pressure-survivals={len(rows) - resolved - deaths}")


if __name__ == "__main__":
    main()
