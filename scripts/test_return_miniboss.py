#!/usr/bin/env python3
"""Fresh-ROM return champion burst, entrance, escort, and art contracts."""
from test_stage_archetypes import EN, PL, RS, TM, addr, generated_room, put16

TARGET = addr('_room_encounter_target')
GUARD = addr('_room_return_guard_ticks')
TIMER = addr('_room_encounter_timer')
PHASE = addr('_room_encounter_phase')


def tick(pb, count):
    for _ in range(count):
        pb.memory[PL + 15] = 120
        pb.tick()


def shoot_burst(pb):
    slots = [EN + i * 28 for i in range(32) if pb.memory[EN + i * 28] == 0][:8]
    assert len(slots) == 8
    for shot in slots:
        for n in range(28):
            pb.memory[shot + n] = 0
        pb.memory[shot] = 1
        pb.memory[shot + 1] = 0x17
        put16(pb, shot + 3, 80)
        put16(pb, shot + 7, 64)
        pb.memory[shot + 12] = 28
        pb.memory[shot + 14] = 4
        pb.memory[shot + 16] = 60
        pb.memory[shot + 25] = 0x77
        pb.memory[shot + 26] = 100


def check(easy, stage=0):
    original_atlas = []
    def prepare(pb, _):
        original_atlas.append(bytes(pb.memory[0x8280:0x8310]))
        pb.memory[RS + 26] = easy
        pb.memory[RS + 23] |= 1 << stage
        pb.memory[RS + 53] |= 1 << 4

    def inspect(pb, _):
        target = EN + pb.memory[TARGET] * 28
        expected_hp, cap = (96 + stage * 8, 8) if easy else (144 + stage * 8, 6)
        assert pb.memory[target + 17] == 34
        assert pb.memory[target + 14] == expected_hp
        assert 0 < pb.memory[GUARD] <= 90, 'missing configured entrance protection'
        for y in range(3, 13):
            for x in range(3, 17):
                pb.memory[TM + y * 20 + x] = 1
        put16(pb, target + 3, 80)
        put16(pb, target + 7, 64)
        put16(pb, PL + 9, 40)
        put16(pb, PL + 11, 64)
        pb.memory[PL + 2] = 200
        pb.memory[target + 22] = 90
        pb.memory[GUARD] = 60
        shoot_burst(pb)
        tick(pb, 8)
        assert pb.memory[target + 14] == expected_hp, 'entrance takes damage'
        pb.memory[GUARD] = 0
        shoot_burst(pb)
        tick(pb, 8)
        assert pb.memory[target + 14] == expected_hp - cap, (
            'stacked/piercing burst bypassed armor', pb.memory[target + 14])
        tick(pb, 20)
        shoot_burst(pb)
        tick(pb, 8)
        assert pb.memory[target + 14] == expected_hp - cap * 2, 'guard never expires'
        pb.memory[target + 24] = 0
        pb.memory[target + 22] = 0
        put16(pb, TIMER, 31)
        tick(pb, 100)
        swarm = [EN + i * 28 for i in range(32)
                 if pb.memory[EN + i * 28] == 2
                 and pb.memory[EN + i * 28 + 17] == 2]
        assert len(swarm) == (4 if easy else 6), ('escort count', len(swarm))
        assert pb.memory[PHASE] == 1, 'escort wave can repeat'
        pb.memory[target + 24] = 0
        render_frames = []
        for _ in range(12):
            tick(pb, 1)
            tiles = {pb.memory[0xFE00 + i * 4 + 2] for i in range(4, 40)
                     if pb.memory[0xFE00 + i * 4]}
            render_frames.append(sorted(tiles))
            if set(range(40, 49)) <= tiles:
                pb.screen.image.save(f'/tmp/quintra-return-miniboss-{stage}-' + ('easy' if easy else 'normal') + '.png')
        assert any(set(range(40, 49)) <= set(t) for t in render_frames), (
            '24x24 champion not rendered across OAM rotation', render_frames)
        atlas = bytes(pb.memory[0x8280:0x8310])
        for button in ('start', 'b'):
            pb.button_press(button)
            tick(pb, 6)
            pb.button_release(button)
            tick(pb, 70)
        assert pb.memory[addr('_loop_current_screen')] == 5, 'menu failed to resume combat'
        assert bytes(pb.memory[0x8280:0x8310]) == atlas, 'menu resume lost champion art'
        assert pb.memory[PHASE] == 1, 'menu resume reset the escort wave'
        for e in swarm:
            pb.memory[e] = pb.memory[e + 1] = 0
        tick(pb, 150)
        assert not any(pb.memory[EN+i*28] == 2 and pb.memory[EN+i*28+17] == 2
                       for i in range(32)), 'escort wave repeated'
        for _ in range(40):
            if pb.memory[target] != 2:
                break
            for i in range(32):
                e = EN + i * 28
                if pb.memory[e] in (1, 4):
                    pb.memory[e] = pb.memory[e + 1] = 0
            put16(pb, PL + 9, 40)
            put16(pb, PL + 11, 64)
            pb.memory[PL + 15] = 120
            put16(pb, target + 3, 80)
            put16(pb, target + 7, 64)
            pb.memory[target + 22] = 90
            shoot_burst(pb)
            tick(pb, 20)
        assert pb.memory[target] != 2, ('champion cannot be defeated', pb.memory[target+14], pb.memory[GUARD])
        tick(pb, 30)
        assert pb.memory[PHASE] == 2, 'defeat did not finish the hunt'
        pb.memory[addr('_room_return_echo_kind')] = 0
        for button in ('start', 'b'):
            pb.button_press(button)
            tick(pb, 6)
            pb.button_release(button)
            tick(pb, 70)
        restored = bytes(pb.memory[0x8280:0x8310])
        assert restored != atlas, 'ordinary room retained champion tiles'
        if stage == 0:
            assert restored == original_atlas[0], 'ordinary room atlas changed'

    generated_room(stage, 0x51A70000, local_room=4, pre_cross=prepare, probe=inspect)


if __name__ == '__main__':
    check(0)
    check(1)
    check(0, 1)
    check(0, 2)
    print('[return-miniboss] PASS Normal/Easy entrance, burst armor, guard recovery, bounded swarm, 24x24 art')
