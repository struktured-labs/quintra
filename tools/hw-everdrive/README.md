# EverDrive GB (original, OS v4) bisect kit — 2026-11-15

Symptom: on a real CGB with an original-series EverDrive GB, the 512 KB builds
stop at the boot screen with the logo garbled under "GAME BOY"; the Sept 3
256 KB build (sha256 eeaef228…, commit 4158f8d3) booted fine.

What emulation showed (none reproduce the hang):
- SameBoy (CGB-C/D/E, real reset-line `GB_quick_reset` after running GBOS.GB,
  SRAM = none/00/FF/3 random/4 real .srm images): sept and main reach the title
  in all 56 combinations.
- IO-register write sequence from 0x100 to the title is identical between
  Sept and main except one OAM DMA and one bank number. Boot-to-title never
  touches ROM banks >= 16. crt0 (GBDK 4.5.0) and the double-speed switch are
  byte-identical to the Sept build. The MiSTer (FPGA CGB) also runs main.
- GBOS.GB derives the ROM-size mask from the FILE size (64 KB doubled until it
  covers the file), not header byte 0x148; 256 KB -> 2, 512 KB -> 3, 1 MB -> 4.
  Zelda DX (1 MB, MBC5+RAM+BATT, RAM 0x03) and the 256 KB images work, so a
  512 KB image is the one configuration this cart has not been seen to run.

Card files (all CGB, MBC5+RAM+BATT, RAM 32 KB):
- qt-0-cart-selftest-512k / qt-0b-…-1mb: tiny test ROM; checks every ROM bank
  signature, 4 SRAM banks, double speed; prints OK/BAD.
- qt-1-sept-known-good: the Sept ROM (control).
- qt-2-sept-padded-512k / qt-3-sept-padded-1mb: Sept code mirrored to 512 KB /
  1 MB with header fixed. Isolates file/ROM size from code.
- qt-4-sep20-last-256k (e2820d3b) / qt-5-oct14-first-512k (9bd176e6):
  committed cartridges either side of the 256 KB -> 512 KB jump.
- qt-6-main-padded-1mb: main c707712c mirrored to 1 MB (fix candidate).
- qt-7-main-diag-colors: main with screen-colour checkpoints: RED = game code
  running, GREEN = double speed OK, YELLOW = input init, BLUE = audio init,
  then the title.
- qt-8-main-diag-no-double-speed: same, no cpu_fast (MAGENTA instead of GREEN).
