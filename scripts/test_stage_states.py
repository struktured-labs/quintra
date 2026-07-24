#!/usr/bin/env python3
"""Contract for the complete manifest-bound deep-test checkpoint curriculum."""
from __future__ import annotations

import json
import re
from itertools import product
from pathlib import Path

from quintra_pyboy_env import (
    ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_UP, QuintraPyBoyEnv,
)
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, VILLAGE_ROOM, dungeon_direction,
    dungeon_size,
)


ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "tmp" / "stage-states"
CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")


def main() -> None:
    manifest = json.loads((STATE_DIR / "manifest.json").read_text())
    records = manifest["states"]
    noi = (ROOT / "rom/working/quintra.noi").read_text()

    def address(name: str) -> int:
        match = re.search(
            rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)", noi)
        assert match, f"missing {name}"
        return int(match.group(1), 16)

    large_room = address("_procgen_current_room_is_large")
    world_width = address("_room_world_width")
    world_height = address("_room_world_height")
    expected_stage = set(product(range(1, 10), CHAMPIONS,
                                 ("normal", "easy"),
                                 ("entry", "court", "sanctuary", "boss")))
    actual_stage = {(r["stage"], r.get("champion"), r["difficulty"],
                     r.get("checkpoint")) for r in records
                    if r.get("checkpoint")
                    in ("entry", "court", "sanctuary", "boss")}
    expected_riftwild = set(product(range(1, 9), CHAMPIONS, ("normal", "easy")))
    actual_riftwild = {(r.get("after_stage"), r.get("champion"), r["difficulty"])
                       for r in records if r.get("checkpoint") == "riftwild"}
    expected_village = set(product((3, 6), CHAMPIONS, ("normal", "easy")))
    actual_village = {(r.get("after_stage"), r.get("champion"), r["difficulty"])
                      for r in records if r.get("checkpoint") == "village"}
    assert (len(records) == 460 and actual_stage == expected_stage
            and actual_riftwild == expected_riftwild
            and actual_village == expected_village), (
        f"checkpoint curriculum drifted: {len(records)} records, "
        f"stage_missing={sorted(expected_stage - actual_stage)}, "
        f"stage_extra={sorted(actual_stage - expected_stage)}, "
        f"riftwild_missing={sorted(expected_riftwild - actual_riftwild)}, "
        f"riftwild_extra={sorted(actual_riftwild - expected_riftwild)}, "
        f"village_missing={sorted(expected_village - actual_village)}, "
        f"village_extra={sorted(actual_village - expected_village)}")

    env = QuintraPyBoyEnv()
    try:
        for record in records:
            state = STATE_DIR / record["file"]
            obs = env.load_state(state)
            stage = record["stage"]
            assert obs["stage"] == stage
            assert obs["difficulty"] == record["difficulty"]
            assert obs["class_id"] == record["class_id"]
            assert obs["room"] == record["room_counter"]
            assert obs["hp"] > 0 and obs["screen"] == 5
            giants = [enemy for enemy in obs["hostiles"] if enemy["giant"]]
            if record["checkpoint"] == "riftwild":
                assert record["after_stage"] in range(1, 9)
                assert record["room_counter"] == STAGE_BOSS_ROOM[record["after_stage"] - 1]
                assert obs["world_mode"] and obs["world_screen"] == 0
                assert not giants, f"{state.name}: Riftwild contains a giant"
                assert env.pb is not None
                rs = env.addrs["_run_state"]
                seen = env.pb.memory[rs + 21] | env.pb.memory[rs + 22] << 8
                assert seen == 1, f"{state.name}: Riftwild fog is not fresh"
            elif record["checkpoint"] == "boss":
                assert record["room_counter"] == STAGE_BOSS_ROOM[stage - 1]
                assert len(giants) == 1, (
                    f"{state.name}: expected one live giant, got {len(giants)}")
                assert giants[0]["pattern"] == stage - 1, (
                    f"{state.name}: wrong boss pattern {giants[0]['pattern']}")
            elif record["checkpoint"] == "court":
                assert record["room_counter"] == STAGE_START[stage - 1] + 5
                assert not obs["world_mode"]
                assert env.pb is not None
                assert env.pb.memory[large_room]
                assert env.pb.memory[world_width] == 224
                assert env.pb.memory[world_height] == 200
            elif record["checkpoint"] == "sanctuary":
                assert record["room_counter"] == STAGE_BOSS_ROOM[stage - 1] - 1
                assert not obs["hostiles"] and not giants
                assert obs["hp"] == obs["hp_max"] and obs["mp"] == obs["mp_max"]
                rs = env.addrs["_run_state"]
                assert env.pb is not None
                assert ((env.pb.memory[rs + 23] | env.pb.memory[rs + 24] << 8)
                        & (1 << (stage - 1))), f"{state.name}: missing Rift Sigil"
                env.pb.memory[0xFF4F] = 0
                visible = [env.pb.memory[0x9800 + y * 32 + x]
                           for y in range(18) for x in range(20)]
                assert all(tile in visible for tile in range(72, 76)), \
                    f"{state.name}: sanctuary gate is not marked"
                # Door/procgen suites own the generated room-wide route. Isolate
                # this checkpoint's threshold contract by positioning inside
                # the visible approach band, then cross it with ordinary input.
                # This proves every saved sanctuary leads to its corresponding
                # live Colossus instead of merely restoring an isolated scene.
                player = env.addrs["_player"]
                size = dungeon_size(stage - 1)
                direction = dungeon_direction(size - 2, size - 1)
                x, y, action = {
                    0: (72, 16, ACTION_UP),
                    1: (128, 60, ACTION_RIGHT),
                    2: (72, 104, ACTION_DOWN),
                    3: (16, 60, ACTION_LEFT),
                }[direction]
                env.pb.memory[player + 9] = x
                env.pb.memory[player + 10] = 0
                env.pb.memory[player + 11] = y
                env.pb.memory[player + 12] = 0
                for _ in range(30):
                    obs, _, terminal, _ = env.step(action, 4)
                    if obs["room"] == STAGE_BOSS_ROOM[stage - 1] or terminal:
                        break
                giants = [enemy for enemy in obs["hostiles"] if enemy["giant"]]
                assert obs["room"] == STAGE_BOSS_ROOM[stage - 1] and not terminal, (
                    f"{state.name}: marked gate did not enter boss room")
                # The counter commits before the banked room generation and
                # entry drama have necessarily crossed their next VBlank.
                # Release input and wait for the visible giant entity.
                for _ in range(180):
                    giants = [enemy for enemy in obs["hostiles"] if enemy["giant"]]
                    # entity_spawn publishes the active/giant bytes before
                    # procgen finishes applying this stage's skin, pattern,
                    # HP cap, and opening telegraph. A VBlank can land inside
                    # that banked transaction, so a base pattern-0 Sentinel
                    # is not yet a settled boss checkpoint.
                    if (len(giants) == 1
                            and giants[0]["pattern"] == stage - 1):
                        break
                    obs, _, terminal, _ = env.step(0, 1)
                assert len(giants) == 1 and giants[0]["pattern"] == stage - 1, (
                    f"{state.name}: sanctuary entered wrong live boss "
                    f"stage={obs['stage']} room={obs['room']} "
                    f"world={obs['world_mode']} terminal={terminal} "
                    f"giants={giants}")
            elif record["checkpoint"] == "entry":
                assert not giants, f"{state.name}: entry state already contains a giant"
            else:
                assert record["after_stage"] in (3, 6)
                assert record["room_counter"] == VILLAGE_ROOM[record["after_stage"]]
                assert not obs["world_mode"] and not obs["hostiles"]
                assert not giants, f"{state.name}: village contains a giant"
    finally:
        env.close()

    print("[stage-states] PASS 460 hash-bound five-champion Normal/Easy "
          "entry+court+sanctuary+boss+Riftwild+village states, "
          "all nine live boss patterns")


if __name__ == "__main__":
    main()
