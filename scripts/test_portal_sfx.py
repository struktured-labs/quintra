#!/usr/bin/env python3
"""A real portal crossing owns a distinct two-part sound, once per crossing."""
from test_dungeon_tools import PLAYER, SCREEN, TILEMAP, addr, boot, clear_entities

RS = addr('_run_state')


def put16(pb, address, value):
    pb.memory[address] = value & 255
    pb.memory[address + 1] = value >> 8


def main():
    pb = boot()
    try:
        clear_entities(pb)
        pb.memory[RS + 17] = 0
        pb.memory[RS + 1] = 2
        put16(pb, PLAYER + 9, 64)
        put16(pb, PLAYER + 11, 48)
        pb.memory[TILEMAP + 7 * 20 + 9] = 1
        before = []
        for _ in range(12):
            pb.tick()
            before.append(pb.memory[0xFF10] & 0x7F)
        assert 0x2B not in before, 'warp sound plays without a portal'
        pb.memory[TILEMAP + 7 * 20 + 9] = 34
        phases = []
        envelopes = []
        for _ in range(160):
            pb.memory[PLAYER + 15] = 120
            pb.tick()
            phases.append(pb.memory[0xFF10] & 0x7F)
            envelopes.append(pb.memory[0xFF12])
        assert pb.memory[RS + 1] == 8, 'portal did not reach its destination'
        assert pb.memory[SCREEN] == 5
        assert 0x2B in phases and 0x26 in phases, ('missing warp phase', phases)
        assert phases.index(0x2B) < phases.index(0x26), 'arrival precedes departure'
        assert 0xB2 in envelopes and 0xA2 in envelopes, 'warp envelopes missing'
        starts = sum(value == 0x2B and (i == 0 or phases[i-1] != 0x2B)
                     for i, value in enumerate(phases))
        assert starts == 1, ('portal retriggered', starts)
        print('[portal-sfx] PASS real 2->8 crossing, two warp phases, no idle/repeated trigger')
    finally:
        pb.stop(save=False)


if __name__ == '__main__':
    main()
