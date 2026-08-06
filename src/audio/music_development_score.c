#pragma bank 3
#include <gb/gb.h>

#include "audio/music_score.h"

BANKREF(music_development_score)

// Every gameplay track has four additional development sections (E–H).
// Combined with the four opening sections in banks 6/7, these make each
// minute-long form a 128-row composition rather than a padded short loop.
const u8 stage_development_melody[MUSIC_STAGE_COUNT][64] = {
    { // Crystal Caverns — reflected facets, ascent, echo, homeward cadence
        T_D6,T_HOLD,T_C6,T_A5, T_F5,T_A5,T_E5,T_D5,
        T_C5,T_E5,T_G5,T_B5, T_A5,T_G5,T_E5,T_REST,
        T_F5,T_HOLD,T_C6,T_REST, T_C6,T_A5,T_HOLD,T_F5,
        T_E5,T_REST,T_B5,T_C6, T_B5,T_HOLD,T_E5,T_REST,
        T_D5,T_HOLD,T_F5,T_A5, T_REST,T_C6,T_A5,T_F5,
        T_G5,T_HOLD,T_B5,T_D6, T_C6,T_A5,T_G5,T_E5,
        T_C6,T_HOLD,T_A5,T_REST, T_F5,T_E5,T_HOLD,T_C5,
        T_D5,T_REST,T_A5,T_C6, T_A5,T_HOLD,T_D5,T_REST,
    },
    { // Verdant Hollow — new shoot, canopy dance, rain, rooted return
        T_C5,T_E5,T_G5,T_HOLD, T_G5,T_FS5,T_REST,T_D5,
        T_E5,T_HOLD,T_C6,T_B5, T_A5,T_G5,T_HOLD,T_REST,
        T_A5,T_C6,T_E6,T_HOLD, T_B5,T_G5,T_A5,T_FS5,
        T_E5,T_FS5,T_G5,T_B5, T_A5,T_FS5,T_E5,T_REST,
        T_G5,T_HOLD,T_E5,T_REST, T_C5,T_HOLD,T_D5,T_E5,
        T_FS5,T_A5,T_C6,T_REST, T_B5,T_G5,T_E5,T_REST,
        T_D5,T_E5,T_FS5,T_HOLD, T_A5,T_G5,T_REST,T_E5,
        T_C5,T_HOLD,T_G5,T_C6, T_B5,T_A5,T_HOLD,T_REST,
    },
    { // Ember Depths — flare, running fire, ash hush, rekindling
        T_C6,T_HOLD,T_E5,T_A5, T_D6,T_C6,T_A5,T_G5,
        T_F5,T_A5,T_C6,T_E6, T_D6,T_C6,T_A5,T_REST,
        T_E5,T_E5,T_G5,T_A5, T_C6,T_AS5,T_A5,T_G5,
        T_F5,T_E5,T_D5,T_E5, T_G5,T_A5,T_REST,T_REST,
        T_A5,T_HOLD,T_E5,T_REST, T_F5,T_HOLD,T_C5,T_REST,
        T_D5,T_F5,T_A5,T_REST, T_G5,T_E5,T_D5,T_REST,
        T_C5,T_REST,T_E5,T_G5, T_A5,T_REST,T_AS5,T_A5,
        T_F5,T_E5,T_REST,T_C5, T_E5,T_HOLD,T_E5,T_REST,
    },
    { // Frost Vault — thawing bell, prismatic run, whiteout, stillness
        T_D6,T_HOLD,T_B5,T_G5, T_E6,T_HOLD,T_CS6,T_A5,
        T_B5,T_G5,T_FS5,T_E5, T_D5,T_FS5,T_A5,T_REST,
        T_G5,T_HOLD,T_B5,T_REST, T_E6,T_HOLD,T_CS6,T_REST,
        T_A5,T_HOLD,T_FS5,T_REST, T_FS5,T_A5,T_HOLD,T_REST,
        T_E5,T_HOLD,T_G5,T_REST, T_CS6,T_HOLD,T_A5,T_REST,
        T_FS5,T_HOLD,T_D5,T_REST, T_G5,T_B5,T_D6,T_HOLD,
        T_D6,T_HOLD,T_B5,T_REST, T_G5,T_HOLD,T_E5,T_REST,
        T_FS5,T_HOLD,T_CS6,T_REST, T_G5,T_D5,T_HOLD,T_REST,
    },
    { // Toxic Mire — bubble line, crooked waltz, sinking, surface light
        T_C5,T_HOLD,T_G5,T_GS5, T_C6,T_GS5,T_F5,T_DS5,
        T_D5,T_F5,T_GS5,T_D6, T_C6,T_GS5,T_G5,T_REST,
        T_F5,T_HOLD,T_C6,T_GS5, T_REST,T_DS5,T_F5,T_HOLD,
        T_C5,T_REST,T_G5,T_AS5, T_GS5,T_HOLD,T_DS5,T_REST,
        T_F5,T_HOLD,T_DS5,T_REST, T_D5,T_HOLD,T_C5,T_REST,
        T_GS5,T_HOLD,T_G5,T_F5, T_DS5,T_C5,T_HOLD,T_REST,
        T_C5,T_HOLD,T_F5,T_GS5, T_REST,T_D6,T_C6,T_HOLD,
        T_G5,T_REST,T_DS5,T_D5, T_C5,T_HOLD,T_C5,T_REST,
    },
    { // Shadow Keep — watch patrol, stairwell flight, apparition, resolve
        T_A5,T_HOLD,T_D5,T_F5, T_CS6,T_A5,T_G5,T_E5,
        T_D5,T_E5,T_G5,T_AS5, T_A5,T_G5,T_E5,T_REST,
        T_D5,T_HOLD,T_A5,T_REST, T_CS6,T_A5,T_F5,T_E5,
        T_HOLD,T_AS5,T_REST,T_D6, T_AS5,T_G5,T_F5,T_REST,
        T_D5,T_HOLD,T_A5,T_REST, T_CS6,T_HOLD,T_F5,T_REST,
        T_E5,T_G5,T_AS5,T_REST, T_A5,T_F5,T_D5,T_REST,
        T_CS5,T_HOLD,T_F5,T_REST, T_G5,T_E5,T_D5,T_CS5,
        T_HOLD,T_F5,T_REST,T_CS6, T_A5,T_E5,T_D5,T_REST,
    },
    { // Golden Temple — herald, procession, inner sanctum, benediction
        T_E5,T_G5,T_C6,T_E6, T_HOLD,T_C6,T_A5,T_G5,
        T_FS5,T_A5,T_D6,T_C6, T_B5,T_G5,T_E5,T_REST,
        T_C5,T_HOLD,T_C6,T_D6, T_E6,T_D6,T_C6,T_B5,
        T_A5,T_C6,T_E6,T_C6, T_G5,T_E5,T_G5,T_REST,
        T_C6,T_HOLD,T_G5,T_REST, T_E5,T_HOLD,T_D5,T_REST,
        T_FS5,T_REST,T_A5,T_C6, T_B5,T_G5,T_E5,T_REST,
        T_C5,T_HOLD,T_G5,T_B5, T_REST,T_D6,T_HOLD,T_C6,
        T_A5,T_FS5,T_HOLD,T_REST, T_E5,T_G5,T_HOLD,T_REST,
    },
    { // Bloodmoon — second rite, chase, eclipse hush, final invocation
        T_E6,T_HOLD,T_A5,T_E5, T_GS5,T_B5,T_D6,T_B5,
        T_A5,T_C6,T_E6,T_D6, T_C6,T_B5,T_A5,T_REST,
        T_A5,T_REST,T_E6,T_HOLD, T_C6,T_A5,T_REST,T_E5,
        T_D5,T_HOLD,T_B5,T_D6, T_REST,T_A5,T_GS5,T_REST,
        T_A5,T_HOLD,T_C6,T_REST, T_E6,T_HOLD,T_D6,T_REST,
        T_GS5,T_REST,T_E5,T_REST, T_D5,T_E5,T_GS5,T_REST,
        T_E5,T_REST,T_A5,T_HOLD, T_B5,T_A5,T_REST,T_E5,
        T_A5,T_HOLD,T_E6,T_C6, T_REST,T_GS5,T_A5,T_REST,
    },
    { // Void Sanctum — inversion, broken orbit, null field, uneasy return
        T_DS6,T_HOLD,T_B5,T_F5, T_C6,T_REST,T_GS5,T_D5,
        T_A5,T_DS5,T_REST,T_B5, T_F5,T_C6,T_REST,T_REST,
        T_D5,T_FS5,T_A5,T_C6, T_DS6,T_REST,T_D6,T_B5,
        T_GS5,T_HOLD,T_C5,T_DS5, T_B5,T_REST,T_F5,T_REST,
        T_C5,T_HOLD,T_REST,T_GS5, T_REST,T_REST,T_D6,T_HOLD,
        T_A5,T_REST,T_DS5,T_REST, T_B5,T_F5,T_REST,T_REST,
        T_C6,T_A5,T_F5,T_D5, T_DS5,T_GS5,T_B5,T_D6,
        T_C6,T_REST,T_GS5,T_DS5, T_C5,T_REST,T_REST,T_REST,
    },
};

const u8 stage_development_bass[MUSIC_STAGE_COUNT][16] = {
    { T_D3,T_C3,T_F3,T_E3, T_G3,T_D3,T_A3,T_C3, T_D3,T_F3,T_G3,T_A3, T_C3,T_G3,T_A3,T_D3 },
    { T_E3,T_D3,T_C3,T_B3, T_E3,T_FS3,T_G3,T_B3, T_C3,T_E3,T_FS3,T_D3, T_C3,T_D3,T_B3,T_E3 },
    { T_A3,T_AS3,T_F3,T_E3, T_A3,T_G3,T_AS3,T_A3, T_E3,T_F3,T_C3,T_E3, T_A3,T_AS3,T_E3,T_A3 },
    { T_G3,T_FS3,T_CS3,T_D3, T_G3,T_A3,T_CS3,T_G3, T_D3,T_A3,T_CS3,T_G3, T_A3,T_CS3,T_D3,T_G3 },
    { T_F3,T_DS3,T_C3,T_F3, T_F3,T_AS3,T_DS3,T_C3, T_F3,T_DS3,T_AS3,T_F3, T_C3,T_DS3,T_C3,T_F3 },
    { T_D3,T_CS3,T_AS3,T_D3, T_A3,T_G3,T_CS3,T_D3, T_D3,T_AS3,T_G3,T_A3, T_CS3,T_AS3,T_A3,T_D3 },
    { T_C3,T_G3,T_FS3,T_C3, T_C3,T_A3,T_D3,T_G3, T_E3,T_B3,T_FS3,T_G3, T_C3,T_A3,T_G3,T_C3 },
    { T_A3,T_GS3,T_F3,T_E3, T_A3,T_E3,T_F3,T_GS3, T_E3,T_F3,T_D3,T_A3, T_A3,T_GS3,T_E3,T_A3 },
    { T_C3,T_FS3,T_DS3,T_C3, T_C3,T_GS3,T_FS3,T_C3, T_D3,T_GS3,T_F3,T_C3, T_C3,T_DS3,T_FS3,T_C3 },
};

const u8 boss_development_melody[MUSIC_STAGE_COUNT][64] = {
    { // Crystal Colossus — fracture and accelerating recombination
        T_A5,T_D6,T_HOLD,T_F5, T_E5,T_REST,T_C6,T_G5,
        T_D5,T_F5,T_HOLD,T_C6, T_D6,T_REST,T_A5,T_REST,
        T_D5,T_HOLD,T_E5,T_F5, T_G5,T_A5,T_C6,T_D6,
        T_C6,T_A5,T_G5,T_F5, T_E5,T_D5,T_REST,T_REST,
        T_C6,T_HOLD,T_A5,T_D6, T_REST,T_G5,T_C6,T_REST,
        T_F5,T_A5,T_D6,T_C6, T_A5,T_G5,T_E5,T_REST,
        T_D5,T_F5,T_HOLD,T_D6, T_C6,T_REST,T_E5,T_D5,
        T_A5,T_C6,T_HOLD,T_C6, T_A5,T_REST,T_D5,T_REST,
    },
    { // Briar Crown — thorn spiral and snapping canopy
        T_G5,T_B5,T_G5,T_HOLD, T_D5,T_FS5,T_REST,T_FS5,
        T_E5,T_HOLD,T_B5,T_A5, T_G5,T_E5,T_D5,T_REST,
        T_E5,T_FS5,T_G5,T_B5, T_A5,T_G5,T_FS5,T_E5,
        T_D5,T_E5,T_G5,T_FS5, T_E5,T_D5,T_REST,T_REST,
        T_B5,T_HOLD,T_G5,T_E5, T_A5,T_REST,T_FS5,T_D5,
        T_E5,T_G5,T_B5,T_G5, T_FS5,T_E5,T_D5,T_REST,
        T_B5,T_E5,T_G5,T_HOLD, T_A5,T_FS5,T_REST,T_B5,
        T_E5,T_HOLD,T_G5,T_A5, T_B5,T_G5,T_E5,T_REST,
    },
    { // Cinder Maw — stoked furnace and collapsing flame
        T_E5,T_A5,T_REST,T_E5, T_G5,T_AS5,T_A5,T_REST,
        T_E5,T_C5,T_HOLD,T_D5, T_F5,T_REST,T_G5,T_REST,
        T_A5,T_C5,T_E5,T_G5, T_A5,T_AS5,T_A5,T_G5,
        T_E5,T_D5,T_C5,T_F5, T_A5,T_E5,T_REST,T_REST,
        T_A5,T_HOLD,T_E5,T_A5, T_G5,T_REST,T_D5,T_G5,
        T_C5,T_E5,T_A5,T_G5, T_E5,T_C5,T_AS5,T_REST,
        T_A5,T_E5,T_REST,T_A5, T_AS5,T_A5,T_G5,T_REST,
        T_C5,T_D5,T_HOLD,T_G5, T_A5,T_REST,T_A5,T_REST,
    },
    { // Frost Wyrm — icefall, sweep, suspended breath, impact
        T_D6,T_HOLD,T_D6,T_B5, T_G5,T_B5,T_E6,T_B5,
        T_G5,T_A5,T_B5,T_D6, T_E6,T_D6,T_B5,T_REST,
        T_G5,T_G5,T_B5,T_D6, T_E6,T_FS5,T_E6,T_D6,
        T_B5,T_A5,T_G5,T_FS5, T_G5,T_D6,T_REST,T_REST,
        T_FS5,T_HOLD,T_D6,T_REST, T_B5,T_HOLD,T_G5,T_REST,
        T_A5,T_B5,T_D6,T_E6, T_D6,T_B5,T_G5,T_REST,
        T_G5,T_HOLD,T_D6,T_FS5, T_REST,T_D6,T_HOLD,T_A5,
        T_G5,T_A5,T_REST,T_D6, T_B5,T_HOLD,T_D5,T_REST,
    },
    { // Mire Sovereign — heave, lunge, submerge, eruption
        T_C6,T_HOLD,T_F5,T_GS5, T_DS6,T_C6,T_GS5,T_G5,
        T_F5,T_G5,T_GS5,T_C6, T_AS5,T_G5,T_F5,T_REST,
        T_F5,T_GS5,T_C6,T_DS6, T_C6,T_GS5,T_G5,T_F5,
        T_DS5,T_F5,T_G5,T_AS5, T_GS5,T_F5,T_REST,T_REST,
        T_C6,T_HOLD,T_F5,T_REST, T_GS5,T_HOLD,T_DS6,T_REST,
        T_C6,T_GS5,T_G5,T_F5, T_DS5,T_F5,T_GS5,T_REST,
        T_F5,T_G5,T_HOLD,T_C6, T_REST,T_C6,T_HOLD,T_GS5,
        T_G5,T_REST,T_DS5,T_HOLD, T_F5,T_C6,T_F5,T_REST,
    },
    { // Shadow Reaper — pursuit, crossing blades, silence, return
        T_F5,T_D6,T_HOLD,T_D6, T_REST,T_CS6,T_A5,T_F5,
        T_G5,T_HOLD,T_D6,T_F5, T_REST,T_D6,T_A5,T_REST,
        T_D5,T_F5,T_A5,T_CS6, T_D6,T_E6,T_F5,T_E6,
        T_D6,T_AS5,T_A5,T_F5, T_E5,T_D5,T_REST,T_REST,
        T_F5,T_HOLD,T_D6,T_REST, T_A5,T_HOLD,T_E5,T_REST,
        T_AS5,T_D6,T_F5,T_E6, T_D6,T_AS5,T_A5,T_REST,
        T_D5,T_A5,T_HOLD,T_F5, T_REST,T_CS6,T_A5,T_F5,
        T_G5,T_HOLD,T_D6,T_E6, T_REST,T_A5,T_D5,T_REST,
    },
    { // Sun Golem — wheel turn, hammer march, corona, decree
        T_G5,T_E6,T_C6,T_E6, T_HOLD,T_C6,T_A5,T_C6,
        T_G5,T_FS5,T_E6,T_D6, T_C6,T_B5,T_G5,T_REST,
        T_C6,T_E6,T_G5,T_FS5, T_E6,T_C6,T_B5,T_A5,
        T_G5,T_B5,T_D6,T_FS5, T_E6,T_C6,T_REST,T_REST,
        T_G5,T_HOLD,T_C6,T_G5, T_REST,T_FS5,T_C6,T_REST,
        T_A5,T_C6,T_FS5,T_E6, T_C6,T_A5,T_G5,T_REST,
        T_G5,T_HOLD,T_D6,T_FS5, T_G5,T_FS5,T_REST,T_C6,
        T_B5,T_C6,T_HOLD,T_D6, T_C6,T_REST,T_C6,T_REST,
    },
    { // Blood Hydra — many heads, interlock, severance, regrowth
        T_E6,T_REST,T_E6,T_C6, T_HOLD,T_F5,T_A5,T_REST,
        T_B5,T_D6,T_HOLD,T_D6, T_A5,T_C6,T_E6,T_REST,
        T_A5,T_B5,T_C6,T_D6, T_E6,T_F5,T_GS5,T_A5,
        T_GS5,T_F5,T_D6,T_C6, T_B5,T_A5,T_REST,T_REST,
        T_A5,T_HOLD,T_E6,T_REST, T_C6,T_HOLD,T_GS5,T_REST,
        T_D6,T_F5,T_A5,T_GS5, T_E6,T_D6,T_B5,T_REST,
        T_A5,T_REST,T_GS5,T_A5, T_HOLD,T_F5,T_D6,T_REST,
        T_A5,T_C6,T_HOLD,T_GS5, T_E6,T_B5,T_A5,T_REST,
    },
    { // Void Lord — impossible ascent, collapse, singularity, defiance
        T_DS6,T_HOLD,T_DS5,T_B5, T_D6,T_A5,T_D5,T_A5,
        T_C6,T_GS5,T_C5,T_GS5, T_F5,T_B5,T_DS6,T_REST,
        T_C5,T_D5,T_FS5,T_A5, T_C6,T_D6,T_DS6,T_D6,
        T_B5,T_GS5,T_DS5,T_D5, T_C5,T_GS5,T_REST,T_REST,
        T_DS6,T_HOLD,T_REST,T_D6, T_REST,T_REST,T_B5,T_HOLD,
        T_GS5,T_REST,T_DS5,T_REST, T_C5,T_D5,T_FS5,T_REST,
        T_C5,T_HOLD,T_REST,T_DS6, T_REST,T_A5,T_F5,T_HOLD,
        T_B5,T_REST,T_DS5,T_REST, T_C5,T_DS5,T_REST,T_REST,
    },
};

const u8 boss_development_bass[MUSIC_STAGE_COUNT][16] = {
    { T_D3,T_C3,T_G3,T_A3, T_D3,T_F3,T_G3,T_C3, T_D3,T_C3,T_A3,T_G3, T_D3,T_F3,T_A3,T_D3 },
    { T_E3,T_D3,T_C3,T_B3, T_E3,T_G3,T_FS3,T_B3, T_E3,T_D3,T_C3,T_G3, T_B3,T_FS3,T_D3,T_E3 },
    { T_A3,T_AS3,T_F3,T_E3, T_A3,T_F3,T_AS3,T_G3, T_A3,T_E3,T_F3,T_C3, T_AS3,T_E3,T_A3,T_A3 },
    { T_G3,T_FS3,T_CS3,T_D3, T_G3,T_D3,T_A3,T_CS3, T_G3,T_E3,T_D3,T_A3, T_CS3,T_D3,T_G3,T_G3 },
    { T_F3,T_DS3,T_C3,T_AS3, T_F3,T_C3,T_DS3,T_AS3, T_F3,T_GS3,T_DS3,T_C3, T_F3,T_AS3,T_C3,T_F3 },
    { T_D3,T_CS3,T_AS3,T_A3, T_D3,T_A3,T_G3,T_CS3, T_D3,T_AS3,T_G3,T_A3, T_CS3,T_A3,T_D3,T_D3 },
    { T_C3,T_G3,T_FS3,T_E3, T_C3,T_A3,T_D3,T_G3, T_C3,T_E3,T_FS3,T_A3, T_D3,T_G3,T_C3,T_C3 },
    { T_A3,T_GS3,T_F3,T_E3, T_A3,T_E3,T_F3,T_GS3, T_A3,T_D3,T_F3,T_E3, T_GS3,T_E3,T_A3,T_A3 },
    { T_C3,T_FS3,T_DS3,T_C3, T_D3,T_GS3,T_FS3,T_C3, T_C3,T_DS3,T_GS3,T_D3, T_FS3,T_C3,T_C3,T_C3 },
};

// Full forms use all eight ideas. Intro/base material (A–D), new bridge and
// development material (E–H), and a concise recapitulation are track-specific.
const u8 stage_forms[MUSIC_STAGE_COUNT][MUSIC_FORM_SECTIONS] = {
    { 0,0,1,0, 2,1,3,0, 1,2,3,1, 4,5,4,6, 5,6,7,4, 2,5,3,6, 0,2,1,3, 6,7,1,0 },
    { 0,1,0,1, 2,0,3,1, 0,2,1,3, 4,4,5,6, 5,7,6,4, 1,5,2,7, 0,2,1,3, 7,6,1,0 },
    { 0,0,2,1, 0,2,3,1, 2,0,3,2, 4,5,6,4, 7,5,6,7, 2,4,3,6, 0,1,2,3, 7,5,1,0 },
    { 0,1,0,2, 1,0,3,1, 0,2,1,3, 4,6,5,4, 6,7,5,6, 1,4,2,7, 0,2,3,1, 7,5,1,0 },
    { 0,0,1,2, 0,1,3,2, 1,0,2,3, 4,5,4,7, 6,5,7,4, 2,6,1,5, 0,2,3,1, 6,7,1,0 },
    { 0,1,1,0, 2,0,3,1, 1,2,0,3, 4,6,5,7, 4,5,7,6, 2,4,3,5, 0,1,2,3, 7,6,1,0 },
    { 0,0,1,3, 0,2,1,3, 1,0,2,3, 4,5,6,7, 5,4,7,6, 1,5,3,6, 0,2,1,3, 7,6,1,0 },
    { 0,1,0,3, 1,0,2,3, 0,2,1,3, 4,6,4,5, 7,6,5,7, 1,4,3,6, 0,1,3,2, 7,5,1,0 },
    { 0,0,2,0, 1,3,0,2, 2,0,3,1, 4,5,7,4, 6,7,5,6, 2,4,3,7, 1,0,2,3, 7,6,1,0 },
};

const u8 boss_forms[MUSIC_STAGE_COUNT][MUSIC_FORM_SECTIONS] = {
    { 0,0,1,0, 1,2,1,3, 0,2,1,3, 4,5,4,6, 5,6,7,5, 2,4,3,7, 0,1,2,3, 6,7,2,0 },
    { 0,1,0,1, 2,1,3,2, 1,0,2,3, 4,6,5,4, 7,5,6,7, 2,4,3,6, 1,2,3,2, 7,6,2,0 },
    { 0,0,2,1, 1,0,3,2, 2,1,0,3, 4,5,6,4, 5,7,6,7, 1,4,3,5, 1,0,2,3, 7,6,1,0 },
    { 0,1,1,0, 2,0,2,3, 1,2,1,3, 4,6,5,7, 4,5,6,7, 2,4,3,6, 0,1,2,3, 7,5,1,0 },
    { 0,0,1,2, 1,0,3,2, 0,2,1,3, 4,5,7,4, 6,5,7,6, 2,4,3,5, 0,2,3,1, 7,6,1,0 },
    { 0,1,0,2, 1,2,3,1, 0,1,2,3, 4,6,5,4, 7,5,6,7, 2,4,3,6, 0,2,1,3, 7,5,1,0 },
    { 0,0,2,1, 0,3,1,2, 1,2,0,3, 4,5,6,7, 5,4,7,6, 2,5,3,4, 1,0,2,3, 7,6,2,0 },
    { 0,1,2,0, 1,0,3,2, 2,1,3,0, 4,6,5,7, 4,5,7,6, 1,4,3,5, 0,2,1,3, 7,6,1,0 },
    { 0,0,1,3, 1,2,0,3, 2,1,3,0, 4,5,7,6, 4,6,5,7, 2,4,3,6, 1,2,3,2, 7,6,1,0 },
};

// Compact non-gameplay cues live here too, preserving always-mapped ROM for
// the sequencer while keeping title/ending behavior unchanged.
const u8 title_melody[32] = {
    T_A5,T_REST,T_C6,T_REST, T_E6,T_REST,T_C6,T_REST,
    T_B5,T_REST,T_G5,T_REST, T_A5,T_REST,T_REST,T_REST,
    T_A5,T_REST,T_D6,T_REST, T_C6,T_REST,T_A5,T_REST,
    T_G5,T_REST,T_E5,T_REST, T_A5,T_REST,T_REST,T_REST,
};
const u8 title_bass[8] = { T_A3,T_A3,T_G3,T_G3,T_C3,T_C3,T_D3,T_A3 };
const u8 victory_melody[32] = {
    T_C5,T_E5,T_G5,T_C6, T_G5,T_C6,T_E6,T_C6,
    T_D5,T_G5,T_B5,T_D6, T_B5,T_D6,T_D6,T_REST,
    T_C5,T_E5,T_G5,T_C6, T_E6,T_C6,T_G5,T_E5,
    T_C6,T_C6,T_C6,T_REST, T_C6,T_REST,T_REST,T_REST,
};
const u8 gameover_melody[32] = {
    T_A5,T_REST,T_G5,T_REST, T_F5,T_REST,T_E5,T_REST,
    T_D5,T_REST,T_C5,T_REST, T_D5,T_REST,T_REST,T_REST,
    T_A5,T_REST,T_G5,T_REST, T_E5,T_REST,T_D5,T_REST,
    T_C5,T_REST,T_C5,T_REST, T_REST,T_REST,T_REST,T_REST,
};
