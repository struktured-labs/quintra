"""Probe: can random play damage Shalamar at all?"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import sys
sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from pyboy import PyBoy
from penta_rl.env import ACTION_BUTTONS
from penta_rl.godmode_env import godmode_step
import numpy as np

ROM = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
SHALAMAR = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/curriculum/arena_FFBA1_D880_0xd_FFD3_4.state"


def run(strategy, label):
    pb = PyBoy(ROM, window="null", sound_emulated=False, cgb=True)
    with open(SHALAMAR, "rb") as fh: pb.load_state(fh)
    rng = np.random.default_rng(42)
    held = []
    init_dcbb = pb.memory[0xDCBB]
    min_dcbb = init_dcbb
    init_ffba = pb.memory[0xFFBA]
    n_steps = 5000
    saw_advance = False
    for t in range(n_steps):
        if strategy == "random":
            a = int(rng.integers(0, 12))
        elif strategy == "spam_a":
            a = 0  # action 0 = A button
        elif strategy == "movement_a":
            # alternate movement and attack
            a = [0, 4, 0, 5, 0, 6, 0, 7][t % 8]
        elif strategy == "spam_combos":
            # combos that include A
            a = [8, 9, 10, 11, 0][t % 5]
        for b in held:
            pb.button_release(b)
        held = ACTION_BUTTONS[a]
        for b in held:
            pb.button_press(b)
        for _ in range(4):
            godmode_step(pb)
            pb.tick()
        cur_dcbb = pb.memory[0xDCBB]
        cur_d880 = pb.memory[0xD880]
        cur_ffba = pb.memory[0xFFBA]
        if cur_dcbb < min_dcbb:
            min_dcbb = cur_dcbb
        if cur_ffba > init_ffba:
            saw_advance = True
            print(f"  {label}: ADVANCE at t={t}!", flush=True)
            break
        if cur_d880 not in (0x0D,) and cur_d880 not in (0x0A, 0x0B):
            print(f"  {label}: D880 changed to {hex(cur_d880)} at t={t}", flush=True)
            break
    final_dcbb = pb.memory[0xDCBB]
    print(f"  {label}: init_DCBB={hex(init_dcbb)} min_DCBB={hex(min_dcbb)} final_DCBB={hex(final_dcbb)} damage={init_dcbb-min_dcbb} advance={saw_advance}", flush=True)
    pb.stop()


for strat in ["random", "spam_a", "movement_a", "spam_combos"]:
    print(f"\n=== {strat} ===", flush=True)
    run(strat, strat)
