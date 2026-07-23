#!/usr/bin/env python3
"""Live-ROM contract: a full MP meter visibly advertises Convergence readiness."""

from test_convergence_transform import PLAYER, boot


READY = (192, 248, 248, 255)
SPENT = (64, 176, 248, 255)


def mp_colors(pb):
    # The bottom WINDOW owns MP columns 8-9. Sampling the rendered pixels pins
    # the real CGB palette result rather than merely trusting an attribute or
    # source-table value that could be overwritten before the LCD sees it.
    return set(pb.screen.image.crop((64, 136, 80, 144)).getdata())


def main():
    for class_id in range(5):
        pb = boot(class_id)
        assert pb.memory[PLAYER + 4] == pb.memory[PLAYER + 3]
        assert READY in mp_colors(pb), (
            f"class {class_id} full MP never reached the icy ready color")

        pb.button("b")
        for _ in range(8):
            pb.tick()
        assert pb.memory[PLAYER + 4] == pb.memory[PLAYER + 3] - 2, (
            f"class {class_id} signature did not spend the expected two MP")
        colors = mp_colors(pb)
        assert SPENT in colors and READY not in colors, (
            f"class {class_id} spent meter retained its full-ready cue: {colors}")
        pb.stop(save=False)

    print("[full-mp-hud] PASS five icy-ready meters return to blue after B")


if __name__ == "__main__":
    main()
