#!/usr/bin/env python3
"""Bit-compare two ROMs after the same number of room updates.

LCD-frame boots are not a fair compare: a faster cartridge completes more
updates before a frame-counted boot returns. This script waits until
room_tick is entered, writes the fixture there (before that update mutates
it), then snapshots on a later entry. Both ROMs therefore simulate the same
number of updates from the same entities, RNG, camera, and iframe seed.

The default gate is 20 updates on every injected scene. A second pass runs
200 updates on every injected scene, including missed shots, overlapping
shots, hostile bullets, and the pinned crawler, orc, and wisp crowds, so a
disagreement that shows up only after the short window still fails.

Natural and fixed-crawler scenes keep whatever the boot spawned, so they
are reported but not required to match. Injected scenes are the gate.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEFORE_ROM = Path(os.environ.get("QUINTRA_BEFORE_ROM", "/tmp/quintra-before.gbc"))
BEFORE_NOI = Path(os.environ.get("QUINTRA_BEFORE_NOI", "/tmp/quintra-before.noi"))
AFTER_ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
UPDATES = 20
LONG_UPDATES = 200
LONG_SCENES = (
    "empty_room",
    "dense12_stationary",
    "walkers8_pinned",
    "walkers16_pinned",
    "orcs8_pinned",
    "wisps6_live",
    "player_shots_miss",
    "player_shots_overlap",
    "hostile16_moving",
)
GATED = {
    "empty_room",
    "dense12_stationary",
    "walkers8_pinned",
    "walkers16_pinned",
    "orcs8_pinned",
    "wisps6_live",
    "player_shots_miss",
    "player_shots_overlap",
    "hostile16_moving",
}


def load_bench():
    spec = importlib.util.spec_from_file_location(
        "bench", ROOT / "scripts/bench_crowded_baseline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blob(pb, addr, size):
    return bytes(int(pb.memory[addr + i]) for i in range(size))


def take_snapshot(pb, sym):
    player = sym["_player"]
    return {
        "entities": blob(pb, sym["_entities"], 32 * 28),
        "player": blob(pb, player, sym["_run_state"] - player),
        "rng": blob(pb, sym["_rng_state"], 4),
        "oam": blob(pb, sym["_shadow_OAM"], 160),
        "tilemap": blob(pb, sym["_room_tilemap"], 20 * 17),
        "anim": pb.memory[sym["_entity_anim_counter"]],
    }


def first_diff(a, b):
    if not isinstance(a, bytes):
        return f"{a} -> {b}"
    for index, (left, right) in enumerate(zip(a, b)):
        if left != right:
            return f"@{index} {left} -> {right}"
    return "length"


def run_scene(bench, rom, sym, setup, updates):
    bank, addr = bench.cpu_site(sym["_room_tick"])
    state = {"phase": "wait", "seen": 0, "snap": None, "info": None}

    def on_tick(_ctx):
        if state["phase"] == "wait":
            return
        if state["phase"] == "arm":
            # Normalize clocks the boot can drift, then write the fixture
            # before this update's AI and combat read it.
            pb.memory[sym["_room_camera_x"]] = 0
            pb.memory[sym["_room_camera_y"]] = 0
            pb.memory[sym["_entity_anim_counter"]] = 0
            pb.memory[sym["_g_hitstop"]] = 0
            pb.memory[sym["_player"] + 15] = 80
            # will_charge ticks once per room update and drifts during the
            # frame-counted boot. Seed it so the measured updates start
            # from the same meter.
            pb.memory[sym["_player"] + 42] = 0
            if "_will_charge_fraction" in sym:
                pb.memory[sym["_will_charge_fraction"]] = 0
            for index, byte in enumerate((0x11, 0x22, 0x33, 0x44)):
                pb.memory[sym["_rng_state"] + index] = byte
            info = bench.room_info(pb, sym)
            setup(pb, sym, info)
            state["phase"] = "run"
            state["seen"] = 0
            return
        state["seen"] += 1
        if state["seen"] == updates:
            state["snap"] = take_snapshot(pb, sym)
            state["phase"] = "done"

    bench.ROM = rom
    pb = bench.boot_room()
    try:
        if bench.room_info(pb, sym)["screen"] != 5:
            raise RuntimeError(f"{rom} never reached the room")
        pb.hook_register(bank, addr, on_tick, None)
        state["phase"] = "arm"
        guard = 0
        while state["phase"] != "done":
            pb.tick(1, render=False, sound=False)
            guard += 1
            if guard > updates * 8 + 40:
                raise RuntimeError(f"did not finish {updates} aligned updates")
        pb.hook_deregister(bank, addr)
        return state["snap"]
    finally:
        pb.stop(save=False)


def main():
    bench = load_bench()
    before_syms = bench.load_noi(BEFORE_NOI)
    after_syms = bench.load_noi(AFTER_ROM.with_suffix(".noi"))
    for name in ("_entities", "_player", "_rng_state", "_shadow_OAM",
                 "_room_tilemap", "_run_state", "_entity_anim_counter"):
        if name not in before_syms or name not in after_syms:
            raise SystemExit(f"{name} missing from a ROM map")
    # A new BSS byte can slide absolute WRAM addresses. The player blob is
    # the span from _player to _run_state, so that distance is the layout gate.
    before_span = before_syms["_run_state"] - before_syms["_player"]
    after_span = after_syms["_run_state"] - after_syms["_player"]
    if before_span != after_span or before_span <= 0:
        raise SystemExit(
            f"player WRAM span changed ({before_span} -> {after_span})")
    catalog = {item[0]: item[1] for item in bench.build_scenes(None)}
    failed = False

    def compare(name, setup, updates, gated):
        nonlocal failed
        print(f"[equiv] {name} updates={updates}", flush=True)
        before = run_scene(bench, BEFORE_ROM, before_syms, setup, updates)
        after = run_scene(bench, AFTER_ROM, after_syms, setup, updates)
        scene_failed = False
        for field in before:
            if before[field] != after[field]:
                scene_failed = True
                print(f"  DIFF {field} {first_diff(before[field], after[field])}",
                      flush=True)
        if not gated:
            print("  (boot-seeded scene, not a gate)", flush=True)
            return
        failed = failed or scene_failed
        if not scene_failed:
            print(f"  match after {updates} room updates", flush=True)

    for name, setup in catalog.items():
        compare(name, setup, UPDATES, name in GATED)
    for name in LONG_SCENES:
        compare(name, catalog[name], LONG_UPDATES, True)
    if failed:
        raise SystemExit(1)
    print("[equiv] PASS", flush=True)


if __name__ == "__main__":
    main()
