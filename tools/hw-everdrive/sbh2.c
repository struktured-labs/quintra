#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "gb.h"
typedef struct GB_gameboy_internal_s GBI;
static uint32_t pixels[160*144]; static int vbl;
static uint32_t rgb(GB_gameboy_t *gb, uint8_t r, uint8_t g, uint8_t b){ return (r<<16)|(g<<8)|b; }
static void vblank(GB_gameboy_t *gb, GB_vblank_type_t t){ vbl = 1; }
static void logcb(GB_gameboy_t *gb, const char *s, GB_log_attributes_t a){}
GB_gameboy_t *s2_open(const char *rom, const char *boot, int model){
    GB_gameboy_t *gb = GB_alloc(); GB_init(gb, (GB_model_t)model);
    if (GB_load_boot_rom(gb, boot)) return NULL;
    GB_set_vblank_callback(gb, vblank); GB_set_pixels_output(gb, pixels);
    GB_set_rgb_encode_callback(gb, rgb); GB_set_log_callback(gb, logcb);
    GB_set_color_correction_mode(gb, GB_COLOR_CORRECTION_DISABLED);
    if (GB_load_rom(gb, rom)) return NULL;
    return gb;
}
int s2_load_rom(GB_gameboy_t *gb, const char *rom){ return GB_load_rom(gb, rom); }
void s2_reset_keep(GB_gameboy_t *gb){ GB_reset(gb); }
void s2_frame(GB_gameboy_t *gb, int keys){
    for (int k = 0; k < 8; k++) GB_set_key_state(gb, k, (keys >> k) & 1);
    vbl = 0; int guard = 0;
    while (!vbl && guard++ < 2000000) GB_run(gb);
}
uint32_t *s2_pixels(void){ return pixels; }
uint8_t *s2_direct(GB_gameboy_t *gb, int which, size_t *size){ uint16_t bank; return GB_get_direct_access(gb, which, size, &bank); }
uint8_t s2_read(GB_gameboy_t *gb, uint16_t a){ return GB_safe_read_memory(gb, a); }
uint16_t s2_pc(GB_gameboy_t *gb){ return ((GBI*)gb)->pc; }
int s2_bank(GB_gameboy_t *gb){ return ((GBI*)gb)->mbc_rom_bank; }
void s2_quick_reset(GB_gameboy_t *gb){ GB_quick_reset(gb); }
#include <stdio.h>
static FILE *iolog; static long iocount;
static bool s2_wcb(GB_gameboy_t *gb, uint16_t addr, uint8_t val){
    GBI *g=(GBI*)gb;
    if (iolog && ((addr>=0xFF00 && addr<0xFF80) || addr==0xFFFF || addr<0x8000 || (addr>=0xA000&&addr<0xC000)) && iocount<2000000){
        iocount++;
        fprintf(iolog,"%d %02x:%04x %04x=%02x ly=%d lcdc=%02x ds=%d\n", 0, g->mbc_rom_bank, g->pc, addr, val, g->io_registers[GB_IO_LY], g->io_registers[GB_IO_LCDC], g->cgb_double_speed?1:0);
    }
    return true;
}
static uint8_t s2_rcb(GB_gameboy_t *gb, uint16_t addr, uint8_t data){
    GBI *g=(GBI*)gb;
    if (iolog && ((addr>=0xA000&&addr<0xC000) || (addr>=0xD5BD && addr<0xE000 && addr < g->sp) || (addr>=0xFF93 && addr<0xFFFF)) && iocount<2000000){
        iocount++;
        fprintf(iolog,"R %02x:%04x %04x->%02x sp=%04x\n", g->mbc_rom_bank, g->pc, addr, data, g->sp);
    }
    return data;
}
void s2_iolog(GB_gameboy_t *gb, const char *path){ iolog=fopen(path,"w"); iocount=0; GB_set_write_memory_callback(gb, s2_wcb); GB_set_read_memory_callback(gb, s2_rcb);}
void s2_iolog_close(void){ if(iolog) fclose(iolog); iolog=0; }
