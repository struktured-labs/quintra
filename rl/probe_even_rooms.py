"""Probe: write FFCE = 2/4/6 from gameplay_start, see if Sara appears in even rooms
and if anything special happens (arena trigger, teleporter visible, etc).
"""
import sys
sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from pyboy import PyBoy
from penta_rl.state import read_state

REAL = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
SAVE = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/gameplay_start.state"

for target_room in [2, 4, 6]:
    print(f"\n=== Force FFCE={target_room} ===")
    pb = PyBoy(REAL, window="null", sound_emulated=False, cgb=True)
    with open(SAVE, "rb") as fh:
        pb.load_state(fh)
    for _ in range(8): pb.tick()
    s = read_state(pb)
    print(f"start: scene={hex(s.scene)} sect={s.section} room={s.room}")
    # Write FFCE
    pb.memory[0xFFCE] = target_room
    last = None
    for i in range(120):  # 2 seconds
        pb.tick()
        s = read_state(pb)
        sig = (s.section, hex(s.scene), s.room, s.miniboss)
        if sig != last:
            print(f"  frame {i}: section={sig[0]} scene={sig[1]} room={sig[2]} mb={sig[3]}")
            last = sig
    pb.stop()
