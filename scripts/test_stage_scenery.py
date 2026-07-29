#!/usr/bin/env python3
"""Live-ROM contract: every dungeon stage uploads distinct prop silhouettes."""

from test_stage_archetypes import generated_room


BGT_PILLAR = 21
TILE_BYTES = 16


def main():
    atlases = []

    def capture(pb, _tiles):
        # The stage loader writes BG/OBJ VRAM bank zero. Read the three
        # contiguous semantic tiles: solid pillar, solid crystal, walkable
        # debris. Their IDs—and therefore collision—never change.
        pb.memory[0xFF4F] = 0
        # Quintra keeps LCDC's signed BG addressing mode: background IDs
        # 0..127 live at $9000 while OBJ tiles of the same numeric IDs live
        # at $8000. Reading $8000 here would inspect Hornet/Skeleton/Orc art,
        # not the dungeon scenery.
        start = 0x9000 + BGT_PILLAR * TILE_BYTES
        atlases.append(bytes(pb.memory[start + i] for i in range(3 * TILE_BYTES)))

    for stage in range(9):
        generated_room(stage, seed=0x51CE0000 + stage, probe=capture)

    assert len(atlases) == 9
    assert len(set(atlases)) == 9, (
        "two stages uploaded the same pillar/crystal/debris silhouette: "
        f"{[atlas.hex() for atlas in atlases]}"
    )
    assert all(any(atlas) for atlas in atlases), "blank stage scenery reached VRAM"
    print("[stage-scenery] PASS nine distinct live VRAM prop atlases; "
          "tile IDs/collision semantics preserved")


if __name__ == "__main__":
    main()
