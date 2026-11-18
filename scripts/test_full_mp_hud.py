#!/usr/bin/env python3
"""Live-ROM contract: a full MP meter visibly advertises Convergence readiness."""

from test_convergence_transform import ENTITIES, PLAYER, boot


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

        # Raven Mark deliberately refuses an empty target table. Give Corvin
        # one visible dummy so this remains a HUD/spend contract instead of
        # contradicting the signature's no-wasted-resource behavior.
        if class_id == 2:
            pb.memory[ENTITIES] = 2       # ENT_ENEMY
            pb.memory[ENTITIES + 1] = 7   # active, alive, on screen
            pb.memory[ENTITIES + 3] = 96
            pb.memory[ENTITIES + 7] = 64
            pb.memory[ENTITIES + 14] = 30
            pb.memory[ENTITIES + 25] = 0x88

        # B is now MP magic (2026-11-17 magic spec): a tap spell spends one
        # MP, so the icy full-MP cue must drop with it; refilling restores it.
        pb.button_press("b")
        for _ in range(3):
            pb.tick()
        pb.button_release("b")
        for _ in range(8):
            pb.tick()
        assert pb.memory[PLAYER + 4] == pb.memory[PLAYER + 3] - 1, (
            f"class {class_id} B tap did not spend one MP")
        assert READY not in mp_colors(pb), (
            f"class {class_id} kept the full-MP cue below full MP")
        pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]   # back to full for A+B

        # The chord still owns the actual MP spend and returns the meter to
        # ordinary blue. Free the B cooldown/entity table so this checks only
        # the live simultaneous-input contract.
        pb.memory[PLAYER + 19] = 0
        for i in range(32 * 28):
            pb.memory[ENTITIES + i] = 0
        pb.button_press("a")
        pb.button_press("b")
        try:
            for _ in range(24):
                pb.tick()
                if pb.memory[PLAYER + 4] == 0:
                    break
        finally:
            pb.button_release("a")
            pb.button_release("b")
        assert pb.memory[PLAYER + 4] == 0, (
            f"class {class_id} full-MP A+B did not spend Convergence magic: mp {pb.memory[PLAYER + 4]}/{pb.memory[PLAYER + 3]} cd {pb.memory[PLAYER + 19]}")
        for _ in range(8):
            pb.tick()
        colors = mp_colors(pb)
        assert SPENT in colors and READY not in colors, (
            f"class {class_id} spent meter retained its full-ready cue: {colors}")
        pb.stop(save=False)

    print("[full-mp-hud] PASS free B preserves ready; A+B returns MP to blue")


if __name__ == "__main__":
    main()
