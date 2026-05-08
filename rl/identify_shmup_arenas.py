"""For each arena state, dump player sprite, scrolling, and movement to identify SHMUP vs action."""
import sys, os
sys.path.insert(0, "/home/struktured/projects/penta-dragon-dx-claude/rl")
from pyboy import PyBoy

REAL = "/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J) [A-fix].gb"
SAVE_DIR = "/home/struktured/projects/penta-dragon-dx-claude/rl/saves/curriculum"

arenas = [
    (1, "arena_FFBA1_D880_0xd_FFD3_4.state", "Shalamar"),
    (2, "arena_FFBA2_D880_0xe_full_init.state", "Riff"),
    (3, "arena_FFBA3_D880_0xf_FFD3_1.state", "Crystal?"),
    (4, "arena_FFBA4_D880_0x10_FFD3_6.state", "Cameo?"),
    (5, "arena_FFBA5_D880_0x11_full_init.state", "Ted"),
    (6, "arena_FFBA6_D880_0x12_full_init.state", "Troop"),
    (7, "arena_FFBA7_D880_0x13_FFD3_7.state", "Faze?"),
    (8, "arena_FFBA8_D880_0x14_FFD3_7.state", "Penta"),
]


print(f"{'FFBA':<5} {'name':<10} {'P_tile':<7} {'P_y':<5} {'P_x':<5} {'scroll_y':<9} {'scroll_x':<9} {'palette':<9} verdict")
for ffba, state_file, name in arenas:
    state_path = f"{SAVE_DIR}/{state_file}"
    if not os.path.exists(state_path):
        print(f"  {ffba} {name:<10} MISSING")
        continue
    pb = PyBoy(REAL, window="null", sound_emulated=False, cgb=True)
    with open(state_path, "rb") as fh: pb.load_state(fh)

    # OAM slot 0 is typically the player
    p_y = pb.memory[0xFE00]
    p_x = pb.memory[0xFE01]
    p_tile = pb.memory[0xFE02]
    p_attr = pb.memory[0xFE03]

    # Background scroll registers
    scy = pb.memory[0xFF42]
    scx = pb.memory[0xFF43]

    # Background palette base — first byte
    bgp_first = pb.memory[0xFF68]

    # Read FFXX values that may indicate SHMUP mode
    ffe7 = pb.memory[0xFFE7]  # often game mode flag
    ffe8 = pb.memory[0xFFE8]
    ffd0 = pb.memory[0xFFD0]  # tilemap pointer high byte

    verdict = "?"
    # Hypothesis: SHMUP stages might have continuous scrolling (scy != 0 and changing)
    # vs action stages typically have static SCY=0 in arena

    print(f"  {ffba:<5} {name:<10} 0x{p_tile:02x}    {p_y:<5} {p_x:<5} 0x{scy:02x}      0x{scx:02x}      "
          f"0x{bgp_first:02x}      ffe7=0x{ffe7:02x} ffd0=0x{ffd0:02x}")
    pb.stop()
