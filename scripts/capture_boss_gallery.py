#!/usr/bin/env python3
"""Render static and animated galleries from live Normal stage bosses."""
from __future__ import annotations

import argparse
import hashlib
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
    "CRYSTAL COLOSSUS", "STORM SERPENT", "CINDER MAW",
    "FROST SPIDER", "MIRE HEART", "SHADOW REAPER",
    "SUN GOLEM", "BLOOD HYDRA", "VOID LORD",
)
ROOM_TILES = 20 * 17
ANIMATION_STRIDE = 8
ANIMATION_FRAMES = 16
ANIMATION_FRAME_MS = 120


def digest(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


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
    screen = addrs["_loop_current_screen"]

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
                if frame % ANIMATION_STRIDE == 0:
                    stage_animation.append(
                        pyboy.screen.image.convert("RGB").copy())
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
                    pyboy.tick()
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
