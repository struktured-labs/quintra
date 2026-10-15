#!/usr/bin/env python3
"""Switch aim modes through the real pause menu within one run."""
import hashlib
import json
from pathlib import Path
from test_will_max import ROM, PLAYER as PL, SCREEN, addr, boot, clear_arena, player_shots

sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
out = Path('builds') / f'aim-toggle-{sha[:8]}'
out.mkdir(parents=True, exist_ok=True)
mode = addr('_player_penta_aim')
pb = boot(2)
results = []

def tap(key):
    pb.button_press(key); pb.tick(8); pb.button_release(key); pb.tick(12)

def signed(value):
    return value-256 if value>127 else value

try:
    assert pb.memory[mode] == 1
    for expected in (0, 1, 0):
        clear_arena(pb)
        for key in ('a','up','right'): pb.button_release(key)
        pb.tick(3)
        before = list(pb.memory[PL:PL+49])
        tap('start'); assert pb.memory[SCREEN] == 9
        tap('select')
        tap('a')
        assert pb.memory[mode] == expected
        assert list(pb.memory[PL+1:PL+9]) == before[1:9], 'Toggle spent resources or changed stats'
        pb.screen.image.save(str(out / ('penta.png' if expected else 'classic.png')))
        tap('b'); assert pb.memory[SCREEN] == 5
        assert pb.memory[mode] == expected
        clear_arena(pb)
        pb.memory[PL+42] = pb.memory[PL+48] = 0
        pb.button_press('right'); pb.tick(5)
        pb.button_press('a'); pb.tick(3)
        pb.button_press('up'); pb.tick(5)
        assert pb.memory[PL+13] == (1 if expected else 2)
        pb.button_release('right'); pb.button_release('up'); pb.tick(3)
        for e in player_shots(pb): pb.memory[e] = pb.memory[e+1] = 0
        pb.memory[PL+22] = 0
        for _ in range(20):
            pb.tick()
            if player_shots(pb): break
        e = player_shots(pb)[0]
        velocity = [signed(pb.memory[e+10]), signed(pb.memory[e+11])]
        assert velocity[0] > 0 and velocity[1] == 0 if expected else velocity[0] == 0 and velocity[1] < 0
        results.append(dict(mode=expected, neutral_velocity=velocity))
        pb.button_release('a'); pb.tick(3)
    # Existing pages remain available after the new aim page.
    tap('start')
    for _ in range(5):
        tap('select')
        assert pb.memory[SCREEN] == 9
    tap('b'); assert pb.memory[SCREEN] == 5
    assert pb.memory[mode] == 0
    print('[aim-toggle] PASS Classic/Penta/Classic live neutral fire, resources, page cycle, resume')
finally:
    pb.stop(save=False)
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha, results=results), indent=2))
