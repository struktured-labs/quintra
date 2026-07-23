#!/usr/bin/env python3
"""Live-ROM contract for the labelled, graphical three-node village map."""
from pathlib import Path

from quintra_pyboy_env import QuintraPyBoyEnv


ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "tmp/stage-states/quintra-village-after-stage-03-wolfkin.pyboy"
SCREEN_MAP = 8
BGT_SWITCH = 33
BGT_AREA_R = 76
BGT_AREA_I = 77
BGT_AREA_F = 78
BGT_AREA_T = 79
BGT_AREA_L = 81
BGT_AREA_V = 83
BGT_AREA_A = 84
BGT_AREA_G = 85
BGT_AREA_E = 86
BGT_AREA_M = 87
BGT_AREA_K = 88
BGT_AREA_O = 89


def row(pb, x, y, width):
    return bytes(pb.memory[0x9800 + y * 32 + x:
                           0x9800 + y * 32 + x + width])


def main():
    env = QuintraPyBoyEnv(window="null")
    try:
        env.load_state(STATE)
        assert env.pb is not None
        env.pb.button("select")
        env.pb.tick(40)
        assert env.observe(include_tiles=False)["screen"] == SCREEN_MAP
        env.pb.memory[0xFF4F] = 0
        assert env.pb.memory[0x9800 + 9 * 32 + 9] == BGT_SWITCH, \
            "village arrival node is not the cyan current marker"
        assert row(env.pb, 1, 13, 5) == bytes((
            BGT_AREA_F, BGT_AREA_O, BGT_AREA_R, BGT_AREA_G, BGT_AREA_E)), \
            "left civic node lost its FORGE label"
        assert row(env.pb, 7, 15, 7) == bytes((
            BGT_AREA_V, BGT_AREA_I, BGT_AREA_L, BGT_AREA_L,
            BGT_AREA_A, BGT_AREA_G, BGT_AREA_E)), \
            "central civic node lost its VILLAGE label"
        assert row(env.pb, 14, 13, 6) == bytes((
            BGT_AREA_M, BGT_AREA_A, BGT_AREA_R,
            BGT_AREA_K, BGT_AREA_E, BGT_AREA_T)), \
            "right civic node lost its MARKET label"
        env.pb.screen.image.save(ROOT / "tmp/town-map-current.png")
        env.pb.button("b")
        env.pb.tick(24)
        assert env.observe(include_tiles=False)["screen"] == 5, \
            "village Compass did not return to play"
    finally:
        env.close()
    print("[town-compass] PASS labelled graphical Forge/Village/Market map")


if __name__ == "__main__":
    main()
