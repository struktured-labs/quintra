#!/usr/bin/env python3
"""Headless contracts for the hidden Hexa Dragmar colossus."""
import io
import re
from pathlib import Path

from pyboy import PyBoy

from test_boss_identity import EN, PL, RS, enter_boss

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ART = Path("/opt/cursor/artifacts")
SCREEN_ROOM = 5
SCREEN_VICTORY = 12
ENTITY = 28
BOSSES_TO_WIN = 9
RUN_REAPER = 1 << 2
RUN_HEXA = 1 << 4
COMPANION_DISCOVERED = 0x80
IDLE, TELEGRAPH, ACTIVE, RECOVERY = 0, 1, 2, 3
BGT_COLOSSUS_VOID = 55
BGT_COLOSSUS_HORN = 63


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


SCREEN = addr("_loop_current_screen")
BEAT = addr("_victory_ending_beat")
CLOCK = addr("_entity_anim_counter")
HEXA_ON = addr("_hexa_boss_active")
HEXA_CORE = addr("_hexa_core_entity")
SPOT = addr("_hexa_spotlight_limb")
SPOT_T = addr("_hexa_spotlight_timer")
PHASE = addr("_hexa_phase")
LIMB_STATE = addr("_hexa_limb_state")
LIMB_TIMER = addr("_hexa_limb_timer")
CH1 = addr("_hexa_audio_ch1_claims")
CH2 = addr("_hexa_audio_ch2_claims")
CH3 = addr("_hexa_audio_ch3_claims")
CH4 = addr("_hexa_audio_ch4_claims")
WORLD_W = addr("_room_world_width")
WORLD_H = addr("_room_world_height")
CAM_X = addr("_room_camera_x")
CAM_Y = addr("_room_camera_y")


def press(pb, button, held=4, released=6):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def boot_room():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    press(pb, "start")
    pb.tick(20)
    press(pb, "a")
    for _ in range(180):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            pb.tick(20)
            return pb
    raise AssertionError("boot did not reach a room")


def meta_open(pb, bank):
    pb.memory[0x0000] = 0x0A
    pb.memory[0x4000] = bank


def meta_close(pb):
    pb.memory[0x0000] = 0


def read_wins(pb):
    meta_open(pb, 1)
    wins = pb.memory[0xA007] | (pb.memory[0xA008] << 8)
    flags = pb.memory[0xA00B]
    meta_close(pb)
    return wins, flags


def offer_victory(pb, reaper=False, companion=False, bosses=9):
    pb.memory[RS + 10] = 1
    pb.memory[RS + 11] = bosses
    pb.memory[RS + 12] = 1
    if reaper:
        pb.memory[RS + 27] = pb.memory[RS + 27] | RUN_REAPER
    if companion:
        pb.memory[RS + 51] = pb.memory[RS + 51] | COMPANION_DISCOVERED
    for _ in range(40):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_VICTORY:
            pb.tick(12)
            return
    raise AssertionError(
        f"victory screen did not open (screen={pb.memory[SCREEN]})"
    )


def skip_to_results(pb):
    press(pb, "start")
    assert pb.memory[SCREEN] == SCREEN_VICTORY
    assert pb.memory[BEAT] == 3, f"START did not reach results ({pb.memory[BEAT]})"


def enter_sanctum(pb):
    press(pb, "a")
    for _ in range(120):
        pb.tick()
        if pb.memory[HEXA_ON] == 1 and pb.memory[SCREEN] == SCREEN_ROOM:
            pb.tick(8)
            return
    raise AssertionError(
        f"A did not enter Hexa Dragmar "
        f"(screen={pb.memory[SCREEN]} active={pb.memory[HEXA_ON]} "
        f"puzzles={pb.memory[RS + 27]:02x})"
    )


def hold_safe(pb):
    pb.memory[PL + 2] = pb.memory[PL + 1] or 8
    # Bit 2 of iframes hides the hero. Leave that bit clear after the
    # combat decrement so the occupied player slots stay measurable.
    pb.memory[PL + 15] = 2


def limb_states(pb):
    return [pb.memory[LIMB_STATE + i] for i in range(5)]


def limb_timers(pb):
    return [pb.memory[LIMB_TIMER + i] for i in range(5)]


def oam_sprites(pb):
    raw = [pb.memory[0xFE00 + i] for i in range(160)]
    sprites = []
    for i in range(40):
        y, x, tile, prop = raw[i * 4:i * 4 + 4]
        sprites.append((y, x, tile, prop))
    return sprites


def test_unlock_kill():
    pb, boss = enter_boss(8, keep_open=True)
    try:
        pb.memory[RS + 27] = pb.memory[RS + 27] | RUN_REAPER
        pb.memory[RS + 51] = COMPANION_DISCOVERED
        assert pb.memory[RS + 11] == 8
        # A player shot sitting on the Void Lord body.
        slot = None
        for i in range(32):
            base = EN + i * ENTITY
            if not (pb.memory[base + 1] & 1):
                slot = base
                break
        assert slot is not None
        for off in range(ENTITY):
            pb.memory[slot + off] = 0
        pb.memory[slot] = 1
        pb.memory[slot + 1] = 0x13
        pb.memory[slot + 3] = pb.memory[boss + 3]
        pb.memory[slot + 4] = pb.memory[boss + 4]
        pb.memory[slot + 7] = pb.memory[boss + 7]
        pb.memory[slot + 8] = pb.memory[boss + 8]
        pb.memory[slot + 14] = 1
        pb.memory[slot + 16] = 90
        pb.memory[slot + 25] = 0xFF
        pb.memory[slot + 26] = 255
        pb.memory[boss + 14] = 1
        for _ in range(90):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_VICTORY:
                pb.tick(12)
                break
        assert pb.memory[SCREEN] == SCREEN_VICTORY, "Void Lord kill did not open victory"
        assert pb.memory[RS + 11] == BOSSES_TO_WIN
        assert pb.memory[BEAT] == 0, "canonical epilogue did not start"
        wins, flags = read_wins(pb)
        assert wins == 1, f"canonical win count is {wins}"
        assert flags & 1, f"Void Lord meta flag missing ({flags:#x})"
        skip_to_results(pb)
        enter_sanctum(pb)
        core = EN + pb.memory[HEXA_CORE] * ENTITY
        assert pb.memory[core + 19] == 9, "sanctum boss is not stage 9"
        assert pb.memory[core + 20] & 1, "sanctum boss lost the giant flag"
        assert pb.memory[RS + 27] & RUN_HEXA, "sanctum bit was not set"
        assert pb.memory[WORLD_W] == 160 and pb.memory[WORLD_H] == 128
        assert pb.memory[CAM_X] == 0 and pb.memory[CAM_Y] == 0
        print("[hexa] PASS unlock from a real Void Lord kill, wins stay canonical")
    finally:
        pb.stop(save=False)


def test_descend_without_qualification():
    pb = boot_room()
    try:
        offer_victory(pb)
        assert pb.memory[BEAT] == 0
        skip_to_results(pb)
        press(pb, "a")
        for _ in range(80):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_ROOM:
                break
        assert pb.memory[HEXA_ON] == 0, "unqualified clear entered Hexa Dragmar"
        assert pb.memory[RS + 17] == 1, "A did not resume endless descent"
        print("[hexa] PASS unqualified results still descend")
    finally:
        pb.stop(save=False)


def qualified_sanctum():
    pb = boot_room()
    offer_victory(pb, reaper=True, companion=True)
    skip_to_results(pb)
    enter_sanctum(pb)
    return pb


def test_limbs_spotlight_and_shunt():
    pb = qualified_sanctum()
    try:
        visits = [{IDLE: 1, TELEGRAPH: 0, ACTIVE: 0, RECOVERY: 0} for _ in range(5)]
        prev = limb_states(pb)
        both_active = 0
        spot_edges = 0
        clean_edge = False
        prev_spot = pb.memory[SPOT]
        prev_timers = limb_timers(pb)
        for _ in range(600):
            hold_safe(pb)
            pb.tick()
            states = limb_states(pb)
            timers = limb_timers(pb)
            spot = pb.memory[SPOT]
            if all(s == ACTIVE for s in states):
                both_active += 1
            for i in range(5):
                if states[i] != prev[i] and states[i] in visits[i]:
                    visits[i][states[i]] += 1
            if prev_spot == 0xFF and spot != 0xFF:
                spot_edges += 1
                ok = True
                for i in range(5):
                    if i == spot:
                        continue
                    if states[i] != prev[i] or prev_timers[i] == 0:
                        continue
                    fell = timers[i] == ((prev_timers[i] - 1) & 0xFF)
                    # The fairness shunt may lengthen a telegraph on the
                    # same frame. A broken limb counts down every other tick.
                    shunted = (states[i] == TELEGRAPH and timers[i] > prev_timers[i]
                               and (timers[i] - prev_timers[i]) % 10 == 0)
                    broken = states[i] == 4
                    if not (fell or shunted or broken):
                        ok = False
                clean_edge = clean_edge or ok
            prev, prev_timers, prev_spot = states, timers, spot
        for i, counts in enumerate(visits):
            assert counts[ACTIVE] >= 4 and counts[RECOVERY] >= 4, (
                f"limb {i} did not finish four cycles: {counts}"
            )
        assert both_active == 0, f"all five limbs were ACTIVE together {both_active} times"
        assert spot_edges >= 1, "spotlight never armed"
        assert clean_edge, "spotlight edge rewrote another limb's countdown"
        # Forced shunt: three or more telegraphs at the same timer.
        for i in range(5):
            pb.memory[LIMB_STATE + i] = TELEGRAPH
            pb.memory[LIMB_TIMER + i] = 10
        hold_safe(pb)
        pb.tick()
        timers = limb_timers(pb)
        states = limb_states(pb)
        assert states[2] == TELEGRAPH and timers[2] >= 19, (
            f"third telegraph was not shunted: states={states} timers={timers}"
        )
        assert timers[0] < timers[2] and timers[1] < timers[2]
        print("[hexa] PASS five limbs, spotlight independence, fairness shunt "
              f"(spotlight edges={spot_edges})")
    finally:
        pb.stop(save=False)


def boss_bbox(pb):
    minx, miny, maxx, maxy = 999, 999, -1, -1
    for y in range(16):
        for x in range(20):
            tile = pb.memory[0x9800 + y * 32 + x]
            if BGT_COLOSSUS_VOID <= tile <= BGT_COLOSSUS_HORN:
                minx = min(minx, x * 8)
                miny = min(miny, y * 8)
                maxx = max(maxx, x * 8 + 8)
                maxy = max(maxy, y * 8 + 8)
    return maxx - minx, maxy - miny


def test_budget_and_stalls():
    pb = qualified_sanctum()
    ART.mkdir(parents=True, exist_ok=True)
    try:
        pb.screen.image.save(ART / "hexa-sanctum-open.png")
        width, height = boss_bbox(pb)
        assert width >= 128 and height >= 104, (
            f"carapace span is {width}x{height}, wanted at least 128x104"
        )
        assert width / 160 >= 0.75 and height / 128 >= 0.75
        peak_shots = 0
        worst_scan = 0
        shot = False
        presented = 0
        STAMP = addr("_hexa_draw_stamp")
        clock = pb.memory[STAMP]
        stall = streak = 0
        for frame in range(600):
            hold_safe(pb)
            pb.tick()
            now = pb.memory[STAMP]
            advanced = (now - clock) & 255
            clock = now
            if not advanced:
                streak += 1
                stall = max(stall, streak)
                continue
            streak = 0
            presented += 1
            sprites = oam_sprites(pb)
            live = [s for s in sprites if s[0] not in (0, 0) and 0 < s[0] < 160]
            assert len(live) <= 40, f"frame {frame} used {len(live)} sprites"
            for i in range(4):
                assert sprites[i][0] not in (0,), f"player sprite {i} hidden"
            limb = sprites[4:24]
            assert all(s[0] != 0 for s in limb), f"limb OAM vacated on frame {frame}"
            tops = [s[0] - 16 for s in limb]
            for scan in range(128):
                n = sum(1 for top in tops if top <= scan < top + 8)
                worst_scan = max(worst_scan, n)
                assert n <= 6, f"scanline {scan} held {n} limb sprites"
            shots = 0
            for i in range(32):
                base = EN + i * ENTITY
                if (pb.memory[base + 1] & 1) and pb.memory[base] == 1 and not (pb.memory[base + 1] & 0x10):
                    shots += 1
            peak_shots = max(peak_shots, shots)
            if frame == 180:
                pb.screen.image.save(ART / "hexa-limbs-live.png")
                shot = True
        assert presented >= 520, f"only {presented} frames finished a draw"
        assert stall <= 4, f"phase 0 stalled for {stall} frames"
        assert shot and peak_shots >= 1, "limbs never produced a hostile shot"
        # Densest phase: quarter HP, every limb still running.
        core = EN + pb.memory[HEXA_CORE] * ENTITY
        pb.memory[core + 14] = 40
        pb.memory[core + 23] = 255
        previous = pb.memory[CLOCK]
        updates = longest = streak = 0
        phase_shots = 0
        for _ in range(600):
            hold_safe(pb)
            pb.tick()
            current = pb.memory[CLOCK]
            advanced = (current - previous) & 255
            previous = current
            updates += 1 if advanced else 0
            streak = 0 if advanced else streak + 1
            longest = max(longest, streak)
            shots = 0
            for i in range(32):
                base = EN + i * ENTITY
                if (pb.memory[base + 1] & 1) and pb.memory[base] == 1 and not (pb.memory[base + 1] & 0x10):
                    shots += 1
            phase_shots = max(phase_shots, shots)
        pb.screen.image.save(ART / "hexa-phase2.png")
        assert pb.memory[PHASE] == 2, f"quarter HP did not reach phase 2 ({pb.memory[PHASE]})"
        assert updates >= 480, f"phase 2 updated only {updates}/600 frames"
        assert longest <= 8, f"phase 2 stalled for {longest} frames"
        print(
            "[hexa] PASS footprint "
            f"{width}x{height} scanline {worst_scan} "
            f"phase0-peak-shots {peak_shots} phase0-stall {stall} "
            f"phase2-peak-shots {phase_shots} longest-stall {longest} "
            f"updates {updates}/600"
        )
        return peak_shots, phase_shots, longest, updates
    finally:
        pb.stop(save=False)


def test_palette_and_audio():
    pb = qualified_sanctum()
    try:
        floor = []
        for offset in range(8):
            pb.memory[0xFF68] = offset
            floor.append(pb.memory[0xFF69])
        pb.memory[SPOT] = 0
        pb.memory[SPOT_T] = 120
        hold_safe(pb)
        pb.tick(2)
        assert pb.memory[SPOT] == 0
        # Wolfkin socket is the 4x4 at tile (3, 8). Others stay palette 5.
        def attr(x, y):
            return pb.memory[1, 0x9800 + y * 32 + x] & 7
        for y in range(8, 12):
            for x in range(3, 7):
                assert attr(x, y) == 6, f"wolfkin socket {(x, y)} pal {attr(x, y)}"
        for origin in ((13, 8), (2, 3), (14, 3), (7, 1)):
            assert attr(*origin) == 5, f"socket {origin} was not downplayed"
        assert attr(1, 8) != 6, "spotlight recolored the floor lane"
        after = []
        for offset in range(8):
            pb.memory[0xFF68] = offset
            after.append(pb.memory[0xFF69])
        assert tuple(after) == tuple(floor), "spotlight rewrote BG palette 0"
        sprites = oam_sprites(pb)
        wolf = [s[3] & 7 for s in sprites[4:8]]
        others = [s[3] & 7 for s in sprites[8:24]]
        assert wolf == [6, 6, 6, 6], f"wolfkin OBJ pal {wolf}"
        assert all(p == 5 for p in others), f"other limbs left palette 5: {others}"
        for _ in range(300):
            hold_safe(pb)
            pb.tick()
        assert pb.memory[CH2] == 0 and pb.memory[CH3] == 0, (
            f"boss SFX claimed music channels ch2={pb.memory[CH2]} ch3={pb.memory[CH3]}"
        )
        assert pb.memory[CH1] > 0 and pb.memory[CH4] > 0, (
            f"expected CH1/CH4 cues, got {pb.memory[CH1]}/{pb.memory[CH4]}"
        )
        print("[hexa] PASS local spotlight palettes and CH2/CH3 reservation")
    finally:
        pb.stop(save=False)


def test_hexa_kill_and_migration():
    pb = qualified_sanctum()
    try:
        wins_before, _ = read_wins(pb)
        core = EN + pb.memory[HEXA_CORE] * ENTITY
        pb.memory[core + 14] = 1
        slot = EN + 4 * ENTITY
        for off in range(ENTITY):
            pb.memory[slot + off] = 0
        pb.memory[slot] = 1
        pb.memory[slot + 1] = 0x13
        pb.memory[slot + 3] = 32
        pb.memory[slot + 7] = 72
        pb.memory[slot + 14] = 1
        pb.memory[slot + 16] = 90
        pb.memory[slot + 25] = 0xFF
        pb.memory[slot + 26] = 255
        # The Wolfkin limb's 16x16 head sits on this tile. Phase is irrelevant
        # for a limb hit; the shared HP pool still dies.
        pb.memory[LIMB_STATE] = ACTIVE
        for _ in range(120):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_VICTORY:
                pb.tick(8)
                break
        assert pb.memory[SCREEN] == SCREEN_VICTORY, "Hexa kill did not return to victory"
        assert pb.memory[BEAT] == 4, f"Hexa card missing ({pb.memory[BEAT]})"
        wins, flags = read_wins(pb)
        assert wins == wins_before, f"Hexa kill changed wins {wins_before} -> {wins}"
        assert flags & 2, f"HEXA_BEATEN missing ({flags:#x})"
        assert not (pb.memory[RS + 27] & RUN_HEXA), "sanctum bit survived the card"
        print(f"[hexa] PASS kill badge without a win increment (wins={wins})")
    finally:
        pb.stop(save=False)

    payload = bytearray(8)
    payload[0] = 50
    payload[4] = 3  # wins = 3
    payload[6] = 0xFF
    payload[7] = 0xFF
    ram = bytearray(32 * 1024)
    # SRAM bank 1 is the second 8 KiB of the cartridge RAM file.
    base = 0x2000
    ram[base + 0] = ord("Q")
    ram[base + 1] = ord("M")
    ram[base + 2] = 2
    ram[base + 3:base + 11] = payload
    ram[base + 11] = sum(payload) & 0xFF
    pb = PyBoy(str(ROM), window="null", cgb=True, ram_file=io.BytesIO(ram))
    try:
        pb.tick(180)
        press(pb, "select")
        pb.tick(20)
        meta_open(pb, 1)
        wins = pb.memory[0xA007] | (pb.memory[0xA008] << 8)
        flags = pb.memory[0xA00B]
        checksum = pb.memory[0xA00C]
        total = sum(pb.memory[0xA000 + i] for i in range(12)) & 0xFF
        meta_close(pb)
        assert wins == 3, f"migration changed wins to {wins}"
        assert flags & 1, "legacy win did not become VOID_LORD_CLEARED"
        assert not (flags & 2), "migration invented a Hexa badge"
        assert checksum == total, f"migrated checksum {checksum:#x} != {total:#x}"
        print("[hexa] PASS legacy meta migrates in place")
    finally:
        pb.stop(save=False)


def main():
    test_unlock_kill()
    test_descend_without_qualification()
    test_limbs_spotlight_and_shunt()
    test_budget_and_stalls()
    test_palette_and_audio()
    test_hexa_kill_and_migration()
    print("[hexa] PASS all contracts")


if __name__ == "__main__":
    main()
