#!/usr/bin/env python3
"""Pure regression test for passive human-play session telemetry."""
from pathlib import Path
from tempfile import TemporaryDirectory

from quintra_playtest_report import (
    HumanPlaytestReport, remove_active_report, summary_line,
    write_active_report, write_report,
)


def obs(*, screen=5, stage=1, room=0, bosses=0, hp=14, hp_max=14,
        world=False, world_screen=0, giant_hp=None, projectiles=0,
        input_keys=0, input_pressed=0):
    hostiles = [] if giant_hp is None else [{
        "giant": True, "hp": giant_hp, "pattern": stage - 1,
    }]
    return {
        "screen": screen, "stage": stage, "room": room, "bosses": bosses,
        "world_mode": world, "world_screen": world_screen,
        "hp": hp, "hp_max": hp_max, "mp": 4, "mp_max": 4,
        "coins": 0, "score": 0, "weapon": 0, "victory": screen == 12,
        "hostiles": hostiles,
        "projectiles": [{"x": 0}] * projectiles,
        "input_keys": input_keys,
        "input_pressed": input_pressed,
    }


def main():
    metadata = {
        "stage": 1, "checkpoint": "sanctuary", "champion": "wolfkin",
        "difficulty": "normal", "rom_sha256": "abc", "state": "fixture",
        "session_id": "test-session",
    }
    report = HumanPlaytestReport(obs(room=5), metadata)
    report.sample(obs(screen=8, room=5, input_keys=0x40,
                      input_pressed=0x40), frames=10)
    report.sample(obs(room=5), frames=10)
    report.sample(obs(room=6, giant_hp=200, projectiles=2), frames=20)
    report.sample(obs(room=6, hp=12, giant_hp=90, projectiles=7), frames=120)
    live = report.snapshot()
    assert live["boss_attempts"][0]["status"] == "in-progress"
    assert live["boss_attempts"][0]["boss_hp_end"] == 90
    report.sample(obs(room=6, bosses=1, hp=13), frames=60)
    result = report.finish()

    assert result["frames"] == 220
    assert result["room_transitions"] == 1
    assert result["map_opens"] == 1 and result["inventory_opens"] == 0
    assert result["input_frames"] == 10 and result["input_edges"] == 1
    assert result["input_mask_seen"] == 0x40 and result["interaction_observed"]
    assert result["min_hp"] == 12 and result["damage_taken"] == 2
    assert result["healing_received"] == 1
    assert result["max_projectiles"] == 7
    assert len(result["boss_attempts"]) == 1
    boss = result["boss_attempts"][0]
    assert boss["status"] == "cleared" and boss["frames"] == 180
    assert boss["boss_hp_start"] == 200 and boss["boss_hp_low"] == 90
    assert boss["boss_hp_end"] == 0 and boss["hero_damage"] == 2
    assert "s1:cleared:3.00s:hp0/200" in summary_line(result)

    idle = HumanPlaytestReport(obs(room=7), metadata)
    idle.sample(obs(room=7, hp=12), frames=300)
    unattended = idle.snapshot()
    assert unattended["damage_taken"] == 2
    assert not unattended["interaction_observed"]
    assert unattended["input_frames"] == unattended["input_edges"] == 0

    with TemporaryDirectory() as directory:
        active = write_active_report(live, Path(directory))
        assert active.name == \
            "active-s01-sanctuary-wolfkin-normal-test-session.json"
        assert active.is_file() and active.read_text().endswith("\n")
        assert write_active_report(result, Path(directory)) == active
        second = dict(result)
        second["metadata"] = dict(result["metadata"], session_id="parallel")
        parallel = write_active_report(second, Path(directory))
        assert parallel != active and parallel.is_file(), \
            "concurrent checkpoint sessions reused one active report"
        path = write_report(result, Path(directory))
        assert path.is_file() and path.read_text().endswith("\n")
        remove_active_report(result, Path(directory))
        assert not active.exists() and parallel.exists(), \
            "finishing one session removed another session's evidence"

    print("[playtest-report] PASS passive map/room/HP/boss session telemetry")


if __name__ == "__main__":
    main()
