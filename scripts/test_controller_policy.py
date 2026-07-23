#!/usr/bin/env python3
"""Pure policy contracts for the controller-only checkpoint trainer."""

from quintra_pyboy_env import ACTION_A, ACTION_DOWN
from run_pyboy_checkpoints import (
    ACTION_RIGHT, controller_action, giant_orbit_action,
    hostile_firing_action, ordinary_retreat_action, route_to_hostile,
)


def observation(player_x: int, enemy_x: int) -> tuple[dict, dict]:
    obs = {
        "x": player_x,
        "y": 56,
        "tiles": [1] * (20 * 17),
    }
    enemy = {"x": enemy_x, "y": 56}
    return obs, enemy


def main() -> None:
    obs, enemy = observation(40, 80)
    assert hostile_firing_action(obs, enemy, 52) == ACTION_RIGHT, \
        "cardinal in-range target should expose its firing direction"
    assert route_to_hostile(obs, enemy, 52) == 0, \
        "clear in-range firing lane should hold position"
    assert route_to_hostile(obs, enemy, 44) == 0, \
        "short physical weapon should hold inside its real lane"

    obs, enemy = observation(40, 88)
    assert route_to_hostile(obs, enemy, 44) == ACTION_RIGHT, \
        "short physical weapon should close a nominal-but-unhittable gap"

    obs, enemy = observation(16, 112)
    assert hostile_firing_action(obs, enemy, 52) == 0, \
        "out-of-range target must not be reported as fire-ready"
    assert route_to_hostile(obs, enemy, 52) == ACTION_RIGHT, \
        "out-of-range target should still be approached"

    obs, enemy = observation(40, 80)
    enemy["y"] = 80
    assert hostile_firing_action(obs, enemy, 52) == 0, \
        "diagonal line of sight is not a four-way firing lane"
    assert route_to_hostile(obs, enemy, 52) != 0, \
        "diagonal target should trigger alignment movement"

    # A full-height wall removes the direct goal set; the policy must seek a
    # lane rather than falsely reporting that the current pose is fire-ready.
    obs, enemy = observation(40, 80)
    for y in range(17):
        obs["tiles"][y * 20 + 7] = 2
    assert route_to_hostile(obs, enemy, 52) != 0, \
        "covered target should trigger repositioning"

    obs, enemy = observation(40, 80)
    live = {
        "x": 40, "y": 56, "class_id": 0, "tiles": [1] * (20 * 17),
        "projectiles": [], "hostiles": [{**enemy, "giant": False}],
        "pickups": [], "entered_from": 0xFF,
        "active_charge": 0, "shield_timer": 0, "mp": 0,
    }
    assert controller_action(live, 0) == ACTION_RIGHT | ACTION_A, \
        "first clear-lane beat should face the weak point while attacking"
    assert controller_action(live, 8) == ACTION_A, \
        "later clear-lane beats should turbo fire without advancing"

    live["hostiles"][0]["giant"] = True
    live["x"] = 65
    assert controller_action(live, 7) == ACTION_DOWN, \
        "too-close giant response should orbit instead of firing away"
    assert controller_action(live, 9) == ACTION_RIGHT | ACTION_A, \
        "aligned giant orbit should preserve bounded aimed pressure"

    # Direct retreat points left, but the two-cell body is flush with a wall;
    # ordinary contact avoidance must choose the open lower strafe instead of
    # holding a dead direction until the enemy consumes the whole heart bar.
    live["hostiles"][0]["giant"] = False
    live["x"], live["y"] = -2, 40
    live["hostiles"][0]["x"], live["hostiles"][0]["y"] = 12, 40
    assert ordinary_retreat_action(live, live["hostiles"][0]) == ACTION_DOWN, \
        "blocked ordinary retreat should strafe toward open arena space"
    live["x"] = 40
    assert ordinary_retreat_action(live, live["hostiles"][0]) == ACTION_RIGHT, \
        "unblocked ordinary retreat should still move directly away"

    live["x"], live["y"] = 40, 32
    live["hostiles"][0]["x"], live["hostiles"][0]["y"] = 80, 56
    assert not controller_action(live, 8) & ACTION_A, \
        "alignment path steps should not masquerade as attacks"

    print("[controller-policy] PASS cardinal aim + honest approach/retreat")


if __name__ == "__main__":
    main()
