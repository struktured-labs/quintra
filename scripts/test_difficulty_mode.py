#!/usr/bin/env python3
"""Live-ROM contract: Normal is canonical; Easy only assists the tester."""
from __future__ import annotations

import json
from pathlib import Path

from quintra_pyboy_env import QuintraPyBoyEnv
from test_damage_hud import PL, take_hostile_hit


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "tmp" / "stage-states"


def stats(env: QuintraPyBoyEnv) -> tuple[int, int, int, int, str]:
    obs = env.observe()
    player = env.addrs["_player"]
    return (obs["hp_max"], env.pb.memory[player + 5], env.pb.memory[player + 6],
            obs["hp"], obs["difficulty"])


def world_signature(env: QuintraPyBoyEnv, state: Path) -> tuple[object, ...]:
    """Difficulty may help the hero, but may not author a different world."""
    obs = env.load_state(state)
    rs = env.addrs["_run_state"]
    # Transient timers and player stats intentionally differ. Generated tiles,
    # route/progression state, and the authored hostile roster must not.
    route = tuple(env.pb.memory[rs + offset] for offset in (
        0, 1, 2, 3, 4, 5, 11, 17, 18, 19, 20, 21, 22, 23, 24, 25))
    hostiles = tuple(sorted(
        (enemy["kind"], enemy["x"], enemy["y"], enemy["hp"],
         enemy["pattern"], enemy["giant"])
        for enemy in obs["hostiles"]))
    return (obs["stage"], obs["room"], obs["world_mode"],
            tuple(obs["tiles"]), route, hostiles)


def assert_paired_worlds_match(env: QuintraPyBoyEnv) -> int:
    manifest = json.loads((STATE_DIR / "manifest.json").read_text())
    pairs: dict[tuple[object, ...], dict[str, Path]] = {}
    for record in manifest["states"]:
        key = (record.get("stage"), record.get("after_stage"),
               record["champion"], record["checkpoint"])
        pairs.setdefault(key, {})[record["difficulty"]] = \
            STATE_DIR / record["file"]
    assert pairs and all(set(pair) == {"normal", "easy"}
                         for pair in pairs.values()), \
        "checkpoint curriculum lost a Normal/Easy pair"
    for key, pair in pairs.items():
        normal = world_signature(env, pair["normal"])
        easy = world_signature(env, pair["easy"])
        assert normal == easy, \
            f"Easy changed generated world or encounter at {key}"
    return len(pairs)


def main() -> None:
    env = QuintraPyBoyEnv()
    try:
        env.reset(0, difficulty="normal")
        normal = stats(env)
        env.reset(0, difficulty="easy")
        easy = stats(env)
        env.pb.memory[PL + 2] = 8
        easy_iframes = take_hostile_hit(env.pb, damage=10)
        easy_after_heavy_hit = env.pb.memory[PL + 2]
        pair_count = assert_paired_worlds_match(env)
    finally:
        env.close()
    assert normal == (14, 4, 1, 14, "normal"), f"Normal balance drifted: {normal}"
    assert easy == (16, 8, 3, 16, "easy"), f"Easy tester budget drifted: {easy}"
    assert (easy_after_heavy_hit, easy_iframes) == (7, 120), \
        "Easy no longer caps damage and quadruples the post-hit testing window"
    print(f"[difficulty] PASS Normal default + generous Easy tester mode; "
          f"{pair_count} paired checkpoints preserve world/encounter design")


if __name__ == "__main__":
    main()
