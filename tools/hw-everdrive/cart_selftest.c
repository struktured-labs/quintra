#include <gb/gb.h>
#include <gb/cgb.h>
#include <stdio.h>
#include <stdint.h>
// Quintra cart self-test: ROM bank mapping, SRAM banks, double speed.
static const palette_color_t pal[4] = { RGB_WHITE, RGB_LIGHTGRAY, RGB_DARKGRAY, RGB_BLACK };
static uint8_t boot_a;
void main(void) {
    uint8_t nb, b, bad = 0, firstbad = 0, v, sbad = 0;
    volatile uint8_t *rom = (volatile uint8_t *)0x7FF0;
    volatile uint8_t *ram = (volatile uint8_t *)0xA000;
    boot_a = _cpu;
    set_bkg_palette(0, 1, pal);
    printf("QUINTRA CART TEST\n");
    printf("CPU A=%hx KEY1=%hx\n", boot_a, (uint8_t)KEY1_REG);
    nb = 2u << (*(volatile uint8_t *)0x0148);
    printf("HDR ROM BANKS=%hu\n", (uint8_t)nb);
    *(volatile uint8_t *)0x3000 = 0;   // MBC5 bank bit 8
    for (b = 1; b < nb && b != 0; ++b) {
        SWITCH_ROM_MBC5(b);
        if (rom[0] != 'B' || rom[1] != 'N' || rom[2] != 'K' || rom[3] != b) {
            if (!bad) firstbad = b;
            ++bad;
        }
    }
    SWITCH_ROM_MBC5(1);
    if (bad) printf("ROM BANKS BAD %hu\nFIRST BAD %hu\n", bad, firstbad);
    else printf("ROM BANKS OK\n");
    // high bank bit not written explicitly: check bank 17 again after 3000=1/0
    ENABLE_RAM_MBC5;
    for (b = 0; b < 4; ++b) { SWITCH_RAM_MBC5(b); ram[0] = 0x5A ^ b; ram[0x1FFF] = 0xA5 ^ b; }
    for (b = 0; b < 4; ++b) { SWITCH_RAM_MBC5(b); if (ram[0] != (0x5A ^ b) || ram[0x1FFF] != (0xA5 ^ b)) ++sbad; }
    SWITCH_RAM_MBC5(0);
    printf(sbad ? "SRAM 4 BANKS BAD %hu\n" : "SRAM 4 BANKS OK\n", sbad);
    DISABLE_RAM_MBC5;
    v = ram[0];
    printf("SRAM OFF READ=%hx\n", v);
    cpu_fast();
    printf("DOUBLE SPEED %s\n", (KEY1_REG & 0x80) ? "OK" : "NO");
    printf("\nALL DONE\n");
    while (1) wait_vbl_done();
}
