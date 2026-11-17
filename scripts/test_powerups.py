#!/usr/bin/env python3
"""ROM contract: Phase 1 temporary power-ups (AEGIS, LIMITLESS, MEND).

Spec: docs/superpowers/specs/2026-11-16-temporary-powerups.md.
Covers Capsule collection, long name+effect announcement, the HUD lane
widget (icon, seconds, Aegis charges), Aegis absorbing hostile hits with
an orbiting aura, Limitless refunding Oath-sized MP spends but not
Convergence, Mend healing over time, boss-room clipping and expiry.
Set QUINTRA_POWERUP_GIF_DIR to also write preview GIFs.
"""
import os
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
GIF_DIR = os.environ.get("QUINTRA_POWERUP_GIF_DIR")

PICKUP_POWERUP = 27
AEGIS, LIMITLESS, MEND = 1, 2, 3
HUD_BLANK, HUD_DIGIT_0 = 8, 9
HUD_OFFER_HEAL, HUD_OFFER_VITAL, HUD_OFFER_RUNE = 40, 42, 44
HUD_AEGIS_PIPS = 124
SPR_SHIELD_AURA = 127
ENT_PROJECTILE, ENT_PICKUP, ENT_FX = 1, 3, 4
NOTICE_POWERUP_FRAMES = 45 + 60 + 60
QSTATUS_MUTE, QSTATUS_CURSE = 7, 10

# player_state_t offsets
HP_MAX, HP, MP_MAX, MP, X, Y, IFRAMES, SHIELD_TIMER, WILL_CHARGE, WILL_LEVEL = (
    1, 2, 3, 4, 9, 11, 15, 20, 42, 48)


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def clear_entities(pb, entities):
    for _ in range(2):
        for i in range(32 * 28):
            pb.memory[entities + i] = 0
        pb.tick()


def boot_class(class_id, screen, player):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    for _ in range(class_id):
        pb.button("down")
        for _ in range(16): pb.tick()
    pb.button("a")
    for _ in range(80): pb.tick()
    assert pb.memory[screen] == 5 and pb.memory[player] == class_id, (
        f"could not enter live class-{class_id} room")
    return pb


class Frames:
    def __init__(self):
        self.frames = []

    def grab(self, pb, every=1, n=1):
        for i in range(n):
            pb.tick()
            if GIF_DIR and i % every == 0:
                self.frames.append(pb.screen.image.copy().convert("RGB")
                                   .resize((320, 288), 0))

    def save(self, name):
        if not GIF_DIR or not self.frames:
            return
        Path(GIF_DIR).mkdir(parents=True, exist_ok=True)
        self.frames[0].save(Path(GIF_DIR) / name, save_all=True,
                            append_images=self.frames[1:], duration=50, loop=0)
        self.frames = []


def player_pos(pb, player):
    px = pb.memory[player + X] | (pb.memory[player + X + 1] << 8)
    py = pb.memory[player + Y] | (pb.memory[player + Y + 1] << 8)
    return px, py


def drop_capsule(pb, player, entities, kind, slot=0):
    px, py = player_pos(pb, player)
    e = entities + slot * 28
    pb.memory[e] = ENT_PICKUP
    pb.memory[e + 1] = 0x03
    put_fix8(pb, e + 2, px + 4)
    put_fix8(pb, e + 6, py + 8)
    pb.memory[e + 12] = 35
    pb.memory[e + 13] = 5
    pb.memory[e + 16] = 255
    pb.memory[e + 17] = PICKUP_POWERUP
    pb.memory[e + 18] = kind
    pb.memory[e + 25] = 0x88
    return e


def hud_lane(pb):
    return [pb.memory[0x9C00 + 12 + i] for i in range(4)]


def wait_notices_clear(pb, notice):
    for _ in range(900):
        if pb.memory[notice] == 0:
            break
        pb.tick()
    for _ in range(3): pb.tick()


def hostile_shot_on_player(pb, player, entities, slot):
    px, py = player_pos(pb, player)
    e = entities + slot * 28
    for i in range(28): pb.memory[e + i] = 0
    pb.memory[e] = ENT_PROJECTILE
    pb.memory[e + 1] = 0x05             # EF_ACTIVE | EF_ON_SCREEN
    put_fix8(pb, e + 2, px + 4)
    put_fix8(pb, e + 6, py + 4)
    pb.memory[e + 12] = 33
    pb.memory[e + 16] = 60
    pb.memory[e + 25] = 0x66
    pb.memory[e + 26] = 2
    return e


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    pu_id, pu_ticks, pu_hits = map(addr, ("_powerup_id", "_powerup_ticks", "_powerup_aegis_hits"))
    notice = addr("_hud_notice_ticks")
    boss_flag = addr("_procgen_current_room_is_boss")
    transform = addr("_room_transform_ticks")
    gif = Frames()

    pb = boot_class(1, screen, player)          # Sauran: MP and Oath kit
    clear_entities(pb, entities)

    # ---- AEGIS: collect, announce, HUD lane, aura, absorb three hits ----
    cap = drop_capsule(pb, player, entities, AEGIS)
    gif.grab(pb, n=3)
    assert pb.memory[cap] == 0, "Aegis Capsule was not collected"
    assert pb.memory[pu_id] == AEGIS and pb.memory[pu_hits] == 3, "Aegis did not start with 3 charges"
    assert 85 <= pb.memory[pu_ticks] <= 90, f"Aegis duration {pb.memory[pu_ticks]} != 90 beats"
    assert pb.memory[notice] > NOTICE_POWERUP_FRAMES - 8, (
        f"power-up card not held {NOTICE_POWERUP_FRAMES} frames ({pb.memory[notice]})")
    gif.grab(pb, every=2, n=60)
    auras = [i for i in range(32) if pb.memory[entities + i * 28] == ENT_FX
             and pb.memory[entities + i * 28 + 12] == SPR_SHIELD_AURA]
    assert auras, "Aegis drew no orbiting ward shard"
    wait_notices_clear(pb, notice)
    lane = hud_lane(pb)
    assert lane[0] == HUD_OFFER_VITAL and lane[3] == HUD_AEGIS_PIPS, f"Aegis HUD pips wrong: {lane}"
    assert HUD_DIGIT_0 <= lane[1] <= HUD_DIGIT_0 + 9, f"Aegis HUD tens missing: {lane}"
    assert HUD_DIGIT_0 <= lane[2] <= HUD_DIGIT_0 + 9, f"Aegis HUD seconds missing: {lane}"
    # Zero-padded seconds must not kern into a fake two-digit "71".
    tens, units = lane[1] - HUD_DIGIT_0, lane[2] - HUD_DIGIT_0
    assert tens * 10 + units < 20, f"Aegis HUD seconds implausible: {lane}"
    hp0 = pb.memory[player + HP]
    for hit in range(3):
        pb.memory[player + IFRAMES] = 0
        shot = hostile_shot_on_player(pb, player, entities, 30)
        gif.grab(pb, every=1, n=4)
        assert pb.memory[player + HP] == hp0, f"Aegis hit {hit + 1} still cost HP"
        assert pb.memory[shot] == 0 or pb.memory[shot + 1] & 1 == 0, "absorbed shot survived"
    assert pb.memory[pu_id] == 0 and pb.memory[pu_hits] == 0, "Aegis did not end after 3 charges"
    gif.grab(pb, every=2, n=40)
    pb.memory[player + IFRAMES] = 0
    hostile_shot_on_player(pb, player, entities, 30)
    for _ in range(4): pb.tick()
    assert pb.memory[player + HP] < hp0, "a hit after Aegis ended was still absorbed"

    # Stoneskin (shield_timer) must consume a hit before Aegis spends a charge.
    clear_entities(pb, entities)
    drop_capsule(pb, player, entities, AEGIS)
    gif.grab(pb, n=3)
    wait_notices_clear(pb, notice)
    assert pb.memory[pu_id] == AEGIS and pb.memory[pu_hits] == 3
    hp1 = pb.memory[player + HP]
    pb.memory[player + IFRAMES] = 0
    pb.memory[player + SHIELD_TIMER] = 30
    shot = hostile_shot_on_player(pb, player, entities, 30)
    gif.grab(pb, n=4)
    assert pb.memory[player + HP] == hp1, "Stoneskin/Aegis overlap still cost HP"
    assert pb.memory[pu_hits] == 3, "Aegis spent a charge while Stoneskin was up"
    pb.memory[player + SHIELD_TIMER] = 0
    # Burn the refreshed Aegis so Limitless starts from a clean slot.
    pb.memory[pu_id] = 0
    pb.memory[pu_ticks] = 0
    pb.memory[pu_hits] = 0
    gif.save("aegis.gif")

    # ---- LIMITLESS: Oath-sized spends refunded, Convergence not ----
    clear_entities(pb, entities)
    for _ in range(60): pb.tick()
    pb.memory[player + IFRAMES] = 0
    mp_max = pb.memory[player + MP_MAX]
    assert mp_max >= 2, "Sauran needs MP for this test"
    pb.memory[player + MP] = 1
    pb.memory[player + WILL_LEVEL] = 0
    drop_capsule(pb, player, entities, LIMITLESS)
    gif.grab(pb, n=3)
    assert pb.memory[pu_id] == LIMITLESS, "Limitless not collected"
    assert pb.memory[player + WILL_LEVEL] >= 1, "Limitless did not bank a Will charge"
    assert 107 <= pb.memory[pu_ticks] <= 112, "Limitless is not 15 s (112 beats)"
    pb.memory[player + MP] = 0                   # an Oath spends 1 MP
    gif.grab(pb, every=2, n=4)
    assert pb.memory[player + MP] == 1, "Limitless did not refund an Oath spend"
    pb.memory[player + MP] = mp_max
    for _ in range(2): pb.tick()
    pb.memory[player + MP] = 0                   # Convergence drains full MP
    pb.memory[transform] = 135
    pb.tick()
    assert pb.memory[player + MP] <= 1, "Limitless refunded a full Convergence drain"
    # Same-frame beat may decrement 135 -> 134 before powerup_tick; still
    # must not refund a full drain as if it were a 1-MP Oath.
    pb.memory[player + MP] = mp_max
    for _ in range(2): pb.tick()
    pb.memory[player + MP] = 0
    pb.memory[transform] = 134
    pb.tick()
    assert pb.memory[player + MP] <= 1, "Limitless refunded Convergence at ticks=134"
    pb.memory[transform] = 0
    gif.grab(pb, every=2, n=40)
    wait_notices_clear(pb, notice)
    assert hud_lane(pb)[0] == HUD_OFFER_RUNE, f"Limitless HUD icon wrong: {hud_lane(pb)}"
    gif.save("limitless.gif")

    # ---- boss-room clip, then expiry ----
    pb.memory[pu_ticks] = 110
    pb.memory[boss_flag] = 1
    for _ in range(2): pb.tick()
    assert pb.memory[pu_ticks] <= 75, "boss room did not clip Limitless to 10 s"
    pb.memory[boss_flag] = 0
    pb.memory[pu_ticks] = 2
    for _ in range(24): pb.tick()
    assert pb.memory[pu_id] == 0, "power-up did not expire"

    # ---- MEND: heals over time ----
    clear_entities(pb, entities)
    hp_max = pb.memory[player + HP_MAX]
    pb.memory[player + HP] = max(1, hp_max - 6)
    hp_start = pb.memory[player + HP]
    drop_capsule(pb, player, entities, MEND)
    gif.grab(pb, n=3)
    assert pb.memory[pu_id] == MEND, "Mend not collected"
    gif.grab(pb, every=3, n=12 * 8 * 3 + 8)
    healed = pb.memory[player + HP] - hp_start
    assert healed >= 2, f"Mend healed only {healed} half-hearts in ~5 s"
    assert pb.memory[player + HP] <= hp_max
    pb.memory[pu_ticks] = 90        # outside the blinking last-3-seconds window
    wait_notices_clear(pb, notice)
    pb.memory[pu_ticks] = 90
    for _ in range(3): pb.tick()
    assert hud_lane(pb)[0] == HUD_OFFER_HEAL, f"Mend HUD icon wrong: {hud_lane(pb)}"

    # Curse blocks Mend healing; the timer keeps running and NO HEAL fires once.
    status_kind, status_ticks = map(
        addr, ("_player_status_kind", "_player_status_ticks"))
    hp_blocked = pb.memory[player + HP]
    pb.memory[status_kind] = QSTATUS_CURSE
    pb.memory[status_ticks] = 90
    gif.grab(pb, every=3, n=12 * 8 + 8)
    assert pb.memory[player + HP] == hp_blocked, "Mend healed through Curse"
    assert pb.memory[pu_id] == MEND, "Mend expired while blocked by Curse"
    pb.memory[status_kind] = 0
    pb.memory[status_ticks] = 0
    gif.save("mend.gif")

    # ---- same power-up again refreshes, capped at 1.5x ----
    drop_capsule(pb, player, entities, MEND)
    pb.tick(); pb.tick()
    assert pb.memory[pu_ticks] <= 135 and pb.memory[pu_ticks] > 90, "Mend refresh rule broken"

    # Muted heroes do not bank a Will charge on Limitless collect.
    clear_entities(pb, entities)
    pb.memory[pu_id] = 0
    pb.memory[pu_ticks] = 0
    for _ in range(20): pb.tick()
    wait_notices_clear(pb, notice)
    status_kind, status_ticks = map(addr, ("_player_status_kind", "_player_status_ticks"))
    pb.memory[status_kind] = QSTATUS_MUTE
    pb.memory[status_ticks] = 90
    pb.memory[player + WILL_LEVEL] = 0
    pb.memory[player + WILL_CHARGE] = 0
    drop_capsule(pb, player, entities, LIMITLESS)
    gif.grab(pb, n=3)
    assert pb.memory[pu_id] == LIMITLESS, "Limitless not collected while muted"
    assert pb.memory[player + WILL_LEVEL] == 0, "Limitless banked Will while muted"
    pb.memory[status_kind] = 0
    pb.memory[status_ticks] = 0

    pb.stop(save=False)
    print("[powerups] PASS Aegis/Limitless/Mend: collect, announce, HUD, absorb, refund, heal, clip, expiry, curse, mute")


if __name__ == "__main__":
    main()
