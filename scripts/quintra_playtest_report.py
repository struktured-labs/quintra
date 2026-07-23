#!/usr/bin/env python3
"""Passive, player-facing telemetry for an interactive Quintra checkpoint.

The reporter never presses a button or mutates cartridge memory.  It reduces
ordinary visible observations to a small JSON session record so human balance
feedback can be tied to the exact champion, mode, room, and boss timing that
produced it.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCREEN_MAP = 8
SCREEN_INVENTORY = 9
SCREEN_GAMEOVER = 11
SCREEN_VICTORY = 12


def _giant(observation: dict[str, Any]) -> dict[str, Any] | None:
    return next((enemy for enemy in observation["hostiles"]
                 if enemy["giant"]), None)


def _location(observation: dict[str, Any]) -> tuple[int, bool, int, int]:
    return (observation["stage"], observation["world_mode"],
            observation["world_screen"], observation["room"])


class HumanPlaytestReport:
    """Accumulate passive observations from one interactive emulator window."""

    def __init__(self, initial: dict[str, Any], metadata: dict[str, Any]):
        self.metadata = dict(metadata)
        # Several emulator windows may inspect the same checkpoint at once.
        # Give every reporter its own crash-safe path so an old idle window
        # cannot overwrite a new human session's evidence every five seconds.
        self.metadata.setdefault("session_id", uuid.uuid4().hex)
        self.frames = 0
        self.start = self._snapshot(initial)
        self.end = self._snapshot(initial)
        self.min_hp = initial["hp"]
        self.damage_taken = 0
        self.healing_received = 0
        self.room_transitions = 0
        self.map_opens = 0
        self.inventory_opens = 0
        self.input_frames = 0
        self.input_edges = 0
        self.input_mask_seen = 0
        self.max_hostiles = len(initial["hostiles"])
        self.max_projectiles = len(initial["projectiles"])
        self._last = initial
        self._locations = {_location(initial)}
        self._boss: dict[str, Any] | None = None
        self.boss_attempts: list[dict[str, Any]] = []
        if _giant(initial) is not None:
            self._start_boss(initial)

    @staticmethod
    def _snapshot(observation: dict[str, Any]) -> dict[str, Any]:
        return {
            "screen": observation["screen"],
            "stage": observation["stage"],
            "room": observation["room"],
            "bosses": observation["bosses"],
            "world_mode": observation["world_mode"],
            "world_screen": observation["world_screen"],
            "hp": observation["hp"],
            "hp_max": observation["hp_max"],
            "mp": observation["mp"],
            "mp_max": observation["mp_max"],
            "coins": observation["coins"],
            "score": observation["score"],
            "weapon": observation["weapon"],
            "victory": observation["victory"],
        }

    def _start_boss(self, observation: dict[str, Any]) -> None:
        giant = _giant(observation)
        assert giant is not None
        self._boss = {
            "stage": observation["stage"],
            "pattern": giant["pattern"],
            "start_frame": self.frames,
            "frames": 0,
            "boss_hp_start": giant["hp"],
            "boss_hp_low": giant["hp"],
            "hero_hp_start": observation["hp"],
            "hero_hp_low": observation["hp"],
            "bosses_before": observation["bosses"],
            "peak_projectiles": len(observation["projectiles"]),
        }

    def _finish_boss(self, observation: dict[str, Any], status: str | None = None) -> None:
        assert self._boss is not None
        # The first giant-free sample is the observable end of the encounter.
        # Include that final sample interval instead of freezing duration on
        # the last frame where the weak point was still alive.
        self._boss["frames"] = self.frames - self._boss["start_frame"]
        if status is None:
            if observation["bosses"] > self._boss["bosses_before"]:
                status = "cleared"
            elif observation["screen"] == SCREEN_GAMEOVER or observation["hp"] == 0:
                status = "death"
            else:
                status = "ended"
        attempt = dict(self._boss)
        attempt["status"] = status
        attempt["seconds"] = round(attempt["frames"] / 60.0, 2)
        attempt["boss_hp_end"] = 0 if status == "cleared" else attempt["boss_hp_low"]
        attempt["hero_hp_end"] = observation["hp"]
        attempt["hero_damage"] = max(0,
            attempt["hero_hp_start"] - attempt["hero_hp_low"])
        attempt.pop("bosses_before")
        self.boss_attempts.append(attempt)
        self._boss = None

    def sample(self, observation: dict[str, Any], *, frames: int = 1) -> None:
        """Record the next passive sample after ``frames`` emulated frames."""
        if frames < 0:
            raise ValueError("frames must be non-negative")
        self.frames += frames
        previous = self._last

        if observation["hp"] < previous["hp"]:
            self.damage_taken += previous["hp"] - observation["hp"]
        elif observation["hp"] > previous["hp"]:
            self.healing_received += observation["hp"] - previous["hp"]
        self.min_hp = min(self.min_hp, observation["hp"])
        self.max_hostiles = max(self.max_hostiles, len(observation["hostiles"]))
        self.max_projectiles = max(self.max_projectiles, len(observation["projectiles"]))

        if _location(observation) != _location(previous):
            self.room_transitions += 1
        self._locations.add(_location(observation))
        if observation["screen"] == SCREEN_MAP and previous["screen"] != SCREEN_MAP:
            self.map_opens += 1
        if (observation["screen"] == SCREEN_INVENTORY
                and previous["screen"] != SCREEN_INVENTORY):
            self.inventory_opens += 1
        keys = observation.get("input_keys", 0)
        pressed = observation.get("input_pressed", 0)
        if keys:
            self.input_frames += frames
        if pressed:
            self.input_edges += 1
        self.input_mask_seen |= keys | pressed

        giant = _giant(observation)
        if self._boss is None and giant is not None:
            self._start_boss(observation)
        if self._boss is not None:
            if giant is not None:
                self._boss["frames"] = self.frames - self._boss["start_frame"]
                self._boss["boss_hp_low"] = min(self._boss["boss_hp_low"], giant["hp"])
                self._boss["hero_hp_low"] = min(self._boss["hero_hp_low"], observation["hp"])
                self._boss["peak_projectiles"] = max(
                    self._boss["peak_projectiles"], len(observation["projectiles"]))
            else:
                self._finish_boss(observation)

        self.end = self._snapshot(observation)
        self._last = observation

    def _result(self, observation: dict[str, Any]) -> dict[str, Any]:
        """Build a serializable result without changing reporter state."""
        attempts = list(self.boss_attempts)
        if self._boss is not None:
            attempt = dict(self._boss)
            attempt["frames"] = self.frames - attempt["start_frame"]
            attempt["status"] = "in-progress"
            attempt["seconds"] = round(attempt["frames"] / 60.0, 2)
            attempt["boss_hp_end"] = attempt["boss_hp_low"]
            attempt["hero_hp_end"] = observation["hp"]
            attempt["hero_damage"] = max(
                0, attempt["hero_hp_start"] - attempt["hero_hp_low"])
            attempt.pop("bosses_before")
            attempts.append(attempt)
        locations = [
            {"stage": stage, "world_mode": world, "world_screen": screen,
             "room": room}
            for stage, world, screen, room in sorted(self._locations)
        ]
        return {
            "schema": 1,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "metadata": self.metadata,
            "frames": self.frames,
            "seconds": round(self.frames / 60.0, 2),
            "start": self.start,
            "end": self.end,
            "min_hp": self.min_hp,
            "damage_taken": self.damage_taken,
            "healing_received": self.healing_received,
            "room_transitions": self.room_transitions,
            "unique_locations": locations,
            "map_opens": self.map_opens,
            "inventory_opens": self.inventory_opens,
            "input_frames": self.input_frames,
            "input_edges": self.input_edges,
            "input_mask_seen": self.input_mask_seen,
            "interaction_observed": bool(
                self.input_frames or self.input_edges or self.map_opens
                or self.inventory_opens or self.room_transitions),
            "max_hostiles": self.max_hostiles,
            "max_projectiles": self.max_projectiles,
            "boss_attempts": attempts,
        }

    def snapshot(self) -> dict[str, Any]:
        """Return crash-safe live telemetry without closing an active boss."""
        return self._result(self._last)

    def finish(self, observation: dict[str, Any] | None = None) -> dict[str, Any]:
        """Close an interrupted attempt and return the serializable result."""
        if observation is not None:
            self.end = self._snapshot(observation)
        else:
            observation = self._last
        if self._boss is not None:
            self._finish_boss(observation, "window-closed")
        return self._result(observation)


def write_report(report: dict[str, Any], output_dir: Path) -> Path:
    """Atomically write one uniquely named human-play session report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = report["metadata"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = (f"{stamp}-s{meta['stage']:02d}-{meta['checkpoint']}-"
            f"{meta['champion']}-{meta['difficulty']}.json")
    path = output_dir / name
    serial = 2
    while path.exists():
        path = output_dir / name.replace(".json", f"-{serial}.json")
        serial += 1
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temp.replace(path)
    return path


def active_report_path(report: dict[str, Any], output_dir: Path) -> Path:
    """Return this session's unique crash-safe snapshot path."""
    meta = report["metadata"]
    session = str(meta["session_id"])
    if not session or any(not (ch.isalnum() or ch in "-_") for ch in session):
        raise ValueError("playtest session_id must be filename-safe")
    return output_dir / (
        f"active-s{meta['stage']:02d}-{meta['checkpoint']}-"
        f"{meta['champion']}-{meta['difficulty']}-{session}.json")


def write_active_report(report: dict[str, Any], output_dir: Path) -> Path:
    """Atomically refresh one session-unique crash-safe report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = active_report_path(report, output_dir)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temp.replace(path)
    return path


def remove_active_report(report: dict[str, Any], output_dir: Path) -> None:
    """Remove the live snapshot only after its final report is durable."""
    active_report_path(report, output_dir).unlink(missing_ok=True)


def summary_line(report: dict[str, Any]) -> str:
    """Return one terminal-friendly summary for the closed window."""
    bosses = report["boss_attempts"]
    boss_text = "none"
    if bosses:
        boss_text = ";".join(
            f"s{item['stage']}:{item['status']}:{item['seconds']:.2f}s:"
            f"hp{item['boss_hp_end']}/{item['boss_hp_start']}"
            for item in bosses)
    return (f"frames={report['frames']} rooms={report['room_transitions']} "
            f"hp={report['end']['hp']}/{report['end']['hp_max']} "
            f"lost={report['damage_taken']} map={report['map_opens']} "
            f"pack={report['inventory_opens']} "
            f"input={report['input_frames']}f/{report['input_edges']}e "
            f"bosses={boss_text}")
