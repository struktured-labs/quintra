#!/usr/bin/env python3
"""Contract: the framework-neutral PyBoy environment uses real controller I/O."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Timer

from pyboy.utils import WindowEvent

from play_stage_state import wait_for_player_ready
from quintra_pyboy_env import (
    ACTION_A, ACTION_B, ACTION_RIGHT, SCREEN_GAMEOVER, SCREEN_VICTORY,
    QuintraPyBoyEnv,
)
from run_pyboy_checkpoints import WALKABLE, controller_action


def main():
    assert not QuintraPyBoyEnv.is_terminal({"screen": 7, "victory": False})
    assert QuintraPyBoyEnv.is_terminal({"screen": SCREEN_GAMEOVER, "victory": False})
    assert QuintraPyBoyEnv.is_terminal({"screen": SCREEN_VICTORY, "victory": False})
    assert QuintraPyBoyEnv.is_terminal({"screen": 5, "victory": True})
    env = QuintraPyBoyEnv()
    try:
        initial = env.reset(0)
        assert initial["screen"] == 5 and initial["class_id"] == 0
        assert len(initial["tiles"]) == 340 and initial["hp"] == initial["hp_max"] == 14
        assert initial["stage"] == 1 and not initial["world_mode"], \
            "fresh curriculum observation lost public dungeon context"
        observation, reward, terminal, info = env.step(ACTION_RIGHT | ACTION_A, 4)
        assert info == {"action": ACTION_RIGHT | ACTION_A, "frames": 4}
        assert observation["screen"] == 5 and not terminal
        assert observation["input_keys"], \
            "controller-held input is absent from passive observation"
        assert "input_pressed" in observation
        assert isinstance(reward, float) and len(observation["hostiles"]) >= 1
        assert {"vx", "vy", "pattern", "phase_timer"}.issubset(observation["hostiles"][0]), \
            "RL observation lost hostile motion/pattern state"
        assert isinstance(observation["projectiles"], list)
        assert isinstance(observation["pickups"], list)
        assert "entered_from" in observation
        assert "shield_timer" in observation
        compact = env.observe(include_tiles=False)
        assert compact["tiles"] == [] and compact["hp"] == observation["hp"], \
            "passive human telemetry cannot omit only the expensive tile grid"
        for projectile in observation["projectiles"]:
            assert {"x", "y", "vx", "vy", "damage", "ttl"}.issubset(projectile), \
                "RL observation lost hostile projectile state"
        assert set(range(55, 64)) <= WALKABLE, \
            "Penta-scale BG body tiles regressed to walls in controller pathing"
        assert observation["x"] >= initial["x"], "right-held controller action did not move Wolfkin"

        # The cartridge retains the outgoing room's table for a handful of
        # transition frames. An active body wholly outside the room is neither
        # visible nor actionable and must not leak into an RL observation.
        entities = env.addrs["_entities"]
        off_room = entities + 31 * 28
        env.pb.memory[off_room] = 2
        env.pb.memory[off_room + 1] = 1
        env.pb.memory[off_room + 3] = 200
        env.pb.memory[off_room + 4] = 0
        env.pb.memory[off_room + 7] = 200
        env.pb.memory[off_room + 8] = 0
        assert all(not (enemy["x"] == 200 and enemy["y"] == 200)
                   for enemy in env.observe()["hostiles"]), \
            "off-room transition entity leaked into observation"
        env.pb.memory[off_room] = env.pb.memory[off_room + 1] = 0

        # Enemy shots are part of the public dodge state, not a hidden
        # controller-only feature. A synthetic live projectile verifies its
        # signed velocity and combat fields survive JSON observation.
        shot = entities + 30 * 28
        env.pb.memory[shot] = 1
        env.pb.memory[shot + 1] = 1
        env.pb.memory[shot + 3] = 24
        env.pb.memory[shot + 4] = 0
        env.pb.memory[shot + 7] = 32
        env.pb.memory[shot + 8] = 0
        env.pb.memory[shot + 10] = 0xFE
        env.pb.memory[shot + 11] = 3
        env.pb.memory[shot + 14] = 2
        env.pb.memory[shot + 18] = 40
        assert {"x": 24, "y": 32, "vx": -2, "vy": 3, "damage": 2, "ttl": 40} \
            in env.observe()["projectiles"], "hostile projectile observation lost live state"
        env.pb.memory[shot] = env.pb.memory[shot + 1] = 0

        # A predicted horizontal lane should make Sauran press B alone. The
        # cartridge triggers signatures on a B edge with A released; the old
        # pilot's held A+B mask activated neither Stoneskin nor Convergence.
        shield_obs = dict(observation)
        shield_obs.update({"class_id": 1, "active_charge": 0,
                           "shield_timer": 0, "mp": 3, "hostiles": []})
        shield_obs["projectiles"] = [{
            "x": observation["x"] - 12, "y": observation["y"] + 6,
            "vx": 2, "vy": 0, "damage": 1, "ttl": 40,
        }]
        shield_action = controller_action(shield_obs, 12)
        assert shield_action & ACTION_B and not shield_action & ACTION_A, \
            f"Sauran threat response lost its B-only shield edge: {shield_action}"

        second_episode = env.reset(4)
        assert second_episode["screen"] == 5 and second_episode["class_id"] == 4
        assert second_episode["room"] == 0 and second_episode["score"] == 0, \
            "reset leaked a previous run into the next episode"

        easy_episode = env.reset(0, difficulty="easy")
        assert easy_episode["difficulty"] == "easy", \
            "Easy reset did not pass through the class-select mode toggle"
        assert (easy_episode["hp"] == easy_episode["hp_max"]
                and easy_episode["hp_max"] > initial["hp_max"]), \
            "Easy reset lost its full-health playtest cushion"

        # Generated curriculum states are tied to a ROM hash. Reject before
        # asking PyBoy to deserialize when a rebuilt cartridge and an old
        # checkpoint disagree; otherwise an RL run can silently observe a
        # shifted save-state layout.
        with TemporaryDirectory() as raw_dir:
            state_dir = Path(raw_dir)
            (state_dir / "manifest.json").write_text(
                json.dumps({"rom_sha256": "0" * 64}))
            try:
                env.load_state(state_dir / "stale.pyboy")
            except RuntimeError as exc:
                assert "ROM hash" in str(exc), "stale state failed for the wrong reason"
            else:
                raise AssertionError("stale generated state was accepted")

        # Deep-stage fixtures are external emulator state, never ROM/SRAM
        # writes. The environment must expose the restored stage normally.
        state = (Path(__file__).resolve().parent.parent / "tmp" / "stage-states"
                 / "quintra-stage-09-entry-wolfkin.pyboy")
        if state.exists():
            manifest = json.loads((state.parent / "manifest.json").read_text())
            expected_room = next(
                item["room_counter"] for item in manifest["states"]
                if item["file"] == state.name)
            deep = env.load_state(state)
            assert (deep["room"] == expected_room and deep["stage"] == 9
                    and deep["screen"] == 5), \
                "stage-nine checkpoint did not restore its public curriculum context"

            # Hands-on checkpoints must not run live while the player finds
            # the SDL window. An ordinary game control should safely release
            # the host pause without leaking that readiness press into WRAM.
            hp_before = deep["hp"]
            frame_before = env.pb.frame_count
            Timer(0.05, lambda: env.pb.send_input(
                WindowEvent.PRESS_BUTTON_A)).start()
            assert wait_for_player_ready(env.pb)
            ready = env.observe(include_tiles=False)
            assert ready["hp"] == hp_before, \
                "checkpoint took damage before the readiness gate opened"
            assert env.pb.frame_count <= frame_before + 1, \
                "paused checkpoint advanced cartridge frames before readiness"
            assert ready["input_keys"] == 0 and ready["input_pressed"] == 0, \
                "readiness press leaked into the live cartridge session"
    finally:
        env.close()
    print("[pyboy-env] PASS controller-only reset/observation/reward/step")


if __name__ == "__main__":
    main()
