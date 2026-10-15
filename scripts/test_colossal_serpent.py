#!/usr/bin/env python3
"""Current Serpent contract: broad moving body, retained growth, bounded cost."""
from test_serpent_body import main as body
from test_serpent_unwind import main as unwind


def main():
    body()
    unwind()
    print('[colossal-serpent] PASS moving body, growth, cycles, collision, OAM and menu')


if __name__ == '__main__':
    main()
