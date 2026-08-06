#!/usr/bin/env python3
"""Live-ROM contract: Normal is canonical; Easy only assists the tester."""
from __future__ import annotations

import json
from collections import Counter
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
    """Difficulty may scale pressure, but may not author a different world."""
    obs = env.load_state(state)
    rs = env.addrs["_run_state"]
    # Transient timers and player stats intentionally differ. Generated tiles,
    # route/progression state, and the authored hostile identities must not.
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
        assert normal[:5] == easy[:5], \
            f"Easy changed generated geometry or route at {key}"
        # Easy now deliberately reduces crowd pressure: 9..12 bodies in a
        # wide ordinary district versus Normal's 12..16, and two versus three
        # in waypoint courts. It must still be the same generated encounter,
        # so every Easy body matches one of Normal's prefix identities and
        # roster. HP is allowed to differ because special encounter assists
        # are part of the difficulty contract; positions and the exported
        # pattern scratch byte are live AI state. Normal's larger population
        # can cross additional emulated VBlanks while a checkpoint settles,
        # so moving bodies need not retain byte-identical coordinates.
        assert len(normal[5]) >= len(easy[5]), \
            f"Easy added encounter pressure at {key}: {normal[5]} / {easy[5]}"
        if key[3] == "court":
            assert (len(normal[5]), len(easy[5])) == (3, 2), \
                f"Easy court reduction drifted at {key}: {normal[5]} / {easy[5]}"
        normal_roster = Counter((enemy[0], enemy[5]) for enemy in normal[5])
        easy_roster = Counter((enemy[0], enemy[5]) for enemy in easy[5])
        assert all(easy_roster[identity] <= normal_roster[identity]
                   for identity in easy_roster), \
            f"Easy changed encounter identity at {key}: {normal[5]} / {easy[5]}"
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
          f"{pair_count} paired checkpoints preserve geometry/routes and "
          "the documented Easy crowd reduction")


if __name__ == "__main__":
    main()
