#!/usr/bin/env python3
"""Render static and animated galleries from live Normal stage bosses."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from PIL import Image, ImageDraw

from make_stage_states import (
    advance_to_boss, advance_to_sanctuary, boot_to_stage, symbol_addresses,
    select_rom_topology,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROM = ROOT / "rom/working/quintra.gbc"
DEFAULT_OUT = ROOT / "docs/media/boss-gallery.png"
DEFAULT_ANIMATED_OUT = ROOT / "docs/media/boss-gallery.gif"
NAMES = (
    "CRYSTAL COLOSSUS", "STORM SERPENT", "KILNBACK > CINDER REX",
    "FROST SPIDER", "MIRE HEART", "SHADOW REAPER",
    "SUN GOLEM", "BLOOD HYDRA", "VOID LORD",
)
ROOM_TILES = 20 * 17
ANIMATION_STRIDE = 8
ANIMATION_FRAMES = 16
ANIMATION_FRAME_MS = 120


def digest(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def symbol_address(rom: Path, name: str) -> int:
    """Read one auxiliary symbol not needed by the checkpoint builder."""
    noi = rom.with_suffix(".noi")
    match = re.search(
        rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)", noi.read_text())
    if not match:
        raise RuntimeError(f"missing ROM symbol {name} in {noi}")
    return int(match.group(1), 16)


def gallery_canvas(panels: list[Image.Image]) -> Image.Image:
    """Compose nine native LCD frames with labels in a stable 3x3 atlas."""
    label_h = 16
    canvas = Image.new("RGB", (160 * 3, (144 + label_h) * 3), (2, 4, 8))
    draw = ImageDraw.Draw(canvas)
    for index, (name, panel) in enumerate(zip(NAMES, panels)):
        x = (index % 3) * 160
        y = (index // 3) * (144 + label_h)
        canvas.paste(panel, (x, y))
        draw.rectangle((x, y + 144, x + 159, y + 159), fill=(2, 4, 8))
        draw.text((x + 4, y + 147), f"{index + 1} {name}",
                  fill=(240, 244, 224))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--animated-out", type=Path,
                        default=DEFAULT_ANIMATED_OUT)
    args = parser.parse_args()
    args.rom = args.rom.resolve()
    select_rom_topology(args.rom)
    addrs = symbol_addresses(args.rom)
    tilemap = addrs["_room_tilemap"]
    entities = addrs["_entities"]
    player = addrs["_player"]
    screen = addrs["_loop_current_screen"]
    frame_counter = symbol_address(args.rom, "_loop_frame_counter")
    serpent_tail_visible = symbol_address(args.rom, "_serpent_tail_visible")
    cinder_phase = symbol_address(args.rom, "_cinder_phase")
    cinder_timer = symbol_address(args.rom, "_cinder_timer")

    panels: list[Image.Image] = []
    animated_panels: list[list[Image.Image]] = []
    counts: list[int] = []
    for stage, name in enumerate(NAMES):
        pyboy, _, _ = boot_to_stage(args.rom, addrs, stage, "normal", 0)
        try:
            advance_to_sanctuary(pyboy, addrs, stage)
            advance_to_boss(pyboy, addrs, stage)
            giants = [entities + slot * 28 for slot in range(32)
                      if pyboy.memory[entities + slot * 28] == 2
                      and pyboy.memory[entities + slot * 28 + 1] & 1
                      and pyboy.memory[entities + slot * 28 + 20] & 1]
            assert len(giants) == 1, \
                f"stage {stage + 1} gallery expected one live weak point"
            assert pyboy.memory[giants[0] + 19] == stage, \
                f"stage {stage + 1} gallery loaded the wrong boss pattern"
            body_tiles = 0
            selected_frame = 0
            selected_core = (0, 0)
            image = pyboy.screen.image.convert("RGB").copy()
            stage_animation: list[Image.Image] = []
            # Several bodies animate their footprint. In particular, Mire
            # deliberately clenches at 64x48 before expanding to 96x64; a
            # single entry-frame capture falsely presented it as the roster's
            # one small boss. Sample two seconds and retain the live frame
            # with the largest authored BG projection.
            for frame in range(121):
                assert pyboy.memory[screen] == 5, \
                    f"stage {stage + 1} left its live boss room during capture"
                if stage == 2:
                    # A full fair fight takes far longer than a gallery loop.
                    # Cross the real half-health threshold after five sampled
                    # pack frames, then let the cartridge execute its complete
                    # five-husk convergence and Cinder Rex metamorphosis.
                    pyboy.memory[player + 15] = 255
                    if frame == 40:
                        pyboy.memory[giants[0] + 14] = 120
                if frame % ANIMATION_STRIDE == 0:
                    stage_animation.append(
                        pyboy.screen.image.convert("RGB").copy())
                if stage == 2:
                    # This encounter owns ten visible OBJ pieces instead of
                    # painting the old rectangular projection into the BG.
                    # Select the fully formed Rex for the static panel.
                    current_tiles = (10 if pyboy.memory[cinder_phase] == 2
                                     and pyboy.memory[giants[0] + 24] == 0
                                     else 0)
                else:
                    current_tiles = sum(
                        55 <= pyboy.memory[tilemap + index] <= 63
                        for index in range(ROOM_TILES)
                    )
                if current_tiles > body_tiles:
                    body_tiles = current_tiles
                    selected_frame = frame
                    selected_core = (
                        pyboy.memory[giants[0] + 3]
                        | pyboy.memory[giants[0] + 4] << 8,
                        pyboy.memory[giants[0] + 7]
                        | pyboy.memory[giants[0] + 8] << 8,
                    )
                    image = pyboy.screen.image.convert("RGB").copy()
                if frame != 120:
                    # Metamorphosis is deliberately a long 64-gameplay-beat
                    # silhouette sequence. Sample twice as much cartridge time
                    # for Ember and compress it into the same 16-panel loop.
                    pyboy.tick(2 if stage == 2 else 1)
            if stage == 1 and pyboy.memory[giants[0] + 21] < 4:
                # The eight-row live upload deliberately spans safe VBlanks,
                # so a later compressed meal can land while the previous one
                # is still returning. Finish any missing meals one at a time,
                # synchronized to a complete gameplay loop, for the static
                # "final boss" panel. The 16-frame animation above remains a
                # truthful excerpt of the same growth process.
                while pyboy.memory[giants[0] + 21] < 4:
                    before_loop = (pyboy.memory[frame_counter]
                                   | pyboy.memory[frame_counter + 1] << 8)
                    for _ in range(240):
                        pyboy.tick()
                        now_loop = (pyboy.memory[frame_counter]
                                    | pyboy.memory[frame_counter + 1] << 8)
                        if now_loop != before_loop:
                            break
                    meal = pyboy.memory[giants[0] + 21]
                    food = ((60, 88), (76, 76), (92, 68), (100, 60))[meal]
                    pyboy.memory[giants[0] + 3] = food[0] - 12
                    pyboy.memory[giants[0] + 4] = 0
                    pyboy.memory[giants[0] + 7] = food[1] - 12
                    pyboy.memory[giants[0] + 8] = 0
                    # A compressed animation beat may have landed while the
                    # previous banked BG upload was still returning. Restore
                    # the exact pre-meal state used by the live-ROM contract.
                    pyboy.memory[giants[0] + 15] = 0
                    pyboy.memory[giants[0] + 16] = 1
                    pyboy.memory[giants[0] + 21] = meal
                    pyboy.memory[giants[0] + 11] = 3
                    target = meal + 1
                    for _ in range(240):
                        pyboy.tick()
                        if pyboy.memory[giants[0] + 21] == target:
                            break
                    assert pyboy.memory[giants[0] + 21] == target, \
                        (f"gallery could not resolve Serpent meal {target}: "
                         f"state={pyboy.memory[giants[0] + 15]} "
                         f"timer={pyboy.memory[giants[0] + 16]} "
                         f"growth={pyboy.memory[giants[0] + 21]} "
                         f"flags={pyboy.memory[giants[0] + 1]:02x}")
                for _ in range(240):
                    pyboy.memory[player + 15] = 255
                    pyboy.tick()
                    if pyboy.memory[serpent_tail_visible] == 20:
                        break
                assert pyboy.memory[serpent_tail_visible] == 20, \
                    "gallery Serpent never finished its one-scale growth"
                # Fill the full history with an inner loop plus a substantial
                # second coil. Verdant owns twenty repeated OBJ scales and
                # every synthetic step preserves their eight-pixel connection.
                pyboy.memory[giants[0] + 15] = 1
                pyboy.memory[giants[0] + 10] = 220
                for y in range(40, 57, 8):
                    pyboy.memory[giants[0] + 3] = 120
                    pyboy.memory[giants[0] + 4] = 0
                    pyboy.memory[giants[0] + 7] = y
                    pyboy.memory[giants[0] + 8] = 0
                    pyboy.memory[player + 15] = 255
                    pyboy.tick(4)
                for x in range(112, 79, -8):
                    pyboy.memory[giants[0] + 3] = x
                    pyboy.memory[giants[0] + 4] = 0
                    pyboy.memory[giants[0] + 7] = 56
                    pyboy.memory[giants[0] + 8] = 0
                    pyboy.memory[player + 15] = 255
                    pyboy.tick(4)
                for y in range(48, 31, -8):
                    pyboy.memory[giants[0] + 3] = 80
                    pyboy.memory[giants[0] + 4] = 0
                    pyboy.memory[giants[0] + 7] = y
                    pyboy.memory[giants[0] + 8] = 0
                    pyboy.memory[player + 15] = 255
                    pyboy.tick(4)
                for x in range(88, 105, 8):
                    pyboy.memory[giants[0] + 3] = x
                    pyboy.memory[giants[0] + 4] = 0
                    pyboy.memory[giants[0] + 7] = 32
                    pyboy.memory[giants[0] + 8] = 0
                    pyboy.memory[player + 15] = 255
                    pyboy.tick(4)
                for y in range(40, 49, 8):
                    pyboy.memory[giants[0] + 3] = 104
                    pyboy.memory[giants[0] + 4] = 0
                    pyboy.memory[giants[0] + 7] = y
                    pyboy.memory[giants[0] + 8] = 0
                    pyboy.memory[player + 15] = 255
                    pyboy.tick(4)
                for x in range(96, 87, -8):
                    pyboy.memory[giants[0] + 3] = x
                    pyboy.memory[giants[0] + 4] = 0
                    pyboy.memory[giants[0] + 7] = 48
                    pyboy.memory[giants[0] + 8] = 0
                    pyboy.memory[player + 15] = 255
                    pyboy.tick(4)
                # Capture the authored hood without an FX ring covering the
                # face. Damage now palette-flashes the hood without hiding it;
                # the animated gallery retains that live pulse.
                for slot in range(32):
                    ep = entities + slot * 28
                    if pyboy.memory[ep] == 4:
                        pyboy.memory[ep] = pyboy.memory[ep + 1] = 0
                pyboy.memory[giants[0] + 10] = 223
                # Let a complete banked draw beat land before taking the still.
                for _ in range(8):
                    pyboy.memory[giants[0] + 24] = 0
                    pyboy.memory[player + 15] = 255
                    pyboy.tick()
                body_tiles = pyboy.memory[serpent_tail_visible]
                selected_frame = 121
                selected_core = (
                    pyboy.memory[giants[0] + 3]
                    | pyboy.memory[giants[0] + 4] << 8,
                    pyboy.memory[giants[0] + 7]
                    | pyboy.memory[giants[0] + 8] << 8,
                )
                image = pyboy.screen.image.convert("RGB").copy()
            if stage == 1:
                assert body_tiles == 20, \
                    f"stage 2 lost its twenty-segment articulated body: {body_tiles}"
            elif stage == 2:
                assert body_tiles == 10, \
                    ("stage 3 never completed its live Kilnback-to-Rex "
                     f"metamorphosis: phase={pyboy.memory[cinder_phase]} "
                     f"timer={pyboy.memory[cinder_timer]} "
                     f"hp={pyboy.memory[giants[0] + 14]}")
            else:
                assert body_tiles >= 36, \
                    f"stage {stage + 1} lost its screen-scale BG body: {body_tiles}"
            assert len(stage_animation) == ANIMATION_FRAMES
            assert image.size == (160, 144)
            panels.append(image)
            animated_panels.append(stage_animation)
            counts.append(body_tiles)
            print(f"[boss-gallery] {stage + 1} {name}: {body_tiles} body tiles "
                  f"at frame {selected_frame}, core={selected_core}")
        finally:
            pyboy.stop(save=False)

    hashes = [digest(panel) for panel in panels]
    assert len(set(hashes)) == 9, "boss gallery contains duplicate live frames"

    canvas = gallery_canvas(panels)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    temp = args.out.with_suffix(args.out.suffix + ".tmp")
    canvas.save(temp, format="PNG", optimize=True)
    temp.replace(args.out)

    animation = [gallery_canvas([
        animated_panels[stage][frame] for stage in range(len(NAMES))
    ]).convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
        for frame in range(ANIMATION_FRAMES)]
    args.animated_out.parent.mkdir(parents=True, exist_ok=True)
    animated_temp = args.animated_out.with_suffix(
        args.animated_out.suffix + ".tmp")
    animation[0].save(
        animated_temp, format="GIF", save_all=True,
        append_images=animation[1:], duration=ANIMATION_FRAME_MS,
        loop=0, optimize=True, disposal=2,
    )
    animated_temp.replace(args.animated_out)
    print(f"[boss-gallery] wrote {args.out} and {args.animated_out} "
          f"frames={ANIMATION_FRAMES} bodies={counts}")


if __name__ == "__main__":
    main()
