import sys
sys.path.insert(0, "scripts")
from collections import Counter
from test_overworld import PL
from test_riftwild_setpiece import boot_seed, symbols, piece_state
from test_riftwild_landmarks import ROUTE, cross_to
pb = boot_seed(0x1234ABCD)
sym = symbols()
ids = []
seen = set()
def rec(s):
    st = piece_state(pb, sym)
    ids.append((s, st[0]))
    seen.add(s)
    print("field", s, "piece", st[0], "at", st[1], st[2], "stamps", st[4], flush=True)
rec(0)
for screen, x, y in ROUTE:
    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.memory[PL + 15] = 120
    cross_to(pb, screen, x, y)
    if screen not in seen:
        rec(screen)
print("kinds", Counter(i for s, i in ids if i != 255))
print("none", [s for s, i in ids if i == 255])
pb.stop(save=False)
