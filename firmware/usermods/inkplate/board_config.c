#include "board_config.h"

// Real 3-bit/8-level waveform for Inkplate10, transcribed from the Arduino reference
// driver's compiled-in default (waveforms.h's WAVEFORM3BIT macro == waveform1[8][9] in
// Inkplate10Driver.cpp -- the fallback used whenever no per-device EEPROM calibration is
// present). Arduino declares this as waveform3Bit[color][phase] (8 colors x 9 phases);
// transposed here to [phase][color] to match this struct's row-per-phase convention
// (same convention board_config.c already used for the now-removed 2-bit WAVE_2B table).
// Values are 2-bit drive op-codes (0=discharge,1=black,2=white,3=skip), NOT gray levels.
static const waveform_table_t wave_3b_inkplate10 = {
    .levels = 8,
    .phases = 9,
    .table =
        {
            {0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 1, 0, 2, 0, 0},
            {0, 0, 2, 2, 2, 2, 0, 0},
            {0, 2, 1, 2, 1, 2, 0, 2},
            {0, 2, 1, 1, 2, 2, 0, 2},
            {0, 2, 2, 2, 2, 2, 2, 2},
            {0, 1, 2, 2, 2, 2, 1, 2},
            {1, 1, 1, 1, 1, 1, 2, 2},
            {0, 0, 0, 0, 0, 0, 0, 0},
        },
};

const board_config_t board_config_inkplate10 = {
    .name = "inkplate10",

    .width = 1200,
    .height = 825,

    .data_pins = {4, 5, 18, 19, 23, 25, 26, 27},
    .data_mask = INKPLATE_DATA_MASK8(4, 5, 18, 19, 23, 25, 26, 27),

    .pin_cl = 0,
    .pin_le = 2,
    .pin_ckv = 32,
    .pin_sph = 33,

    .pin_oe = {.expander_addr = 0x20, .pin = 0},
    .pin_gmode = {.expander_addr = 0x20, .pin = 1},
    .pin_spv = {.expander_addr = 0x20, .pin = 2},

    .pmic_i2c_addr = 0x48,

    .waveform = &wave_3b_inkplate10,

    .partial_reps = 5,

    .has_touch = 0,
    .has_frontlight = 0,
};

// Real 3-bit/8-level waveform shared by INKPLATE6 and INKPLATE6V2, transcribed from the
// Arduino reference driver's waveforms.h WAVEFORM3BIT macro (identical for both variants
// in that header) -- declared as waveform3Bit[color][phase] (8 colors x 9 phases),
// transposed here to [phase][color] to match this struct's row-per-phase convention.
static const waveform_table_t wave_3b_inkplate6 = {
    .levels = 8,
    .phases = 9,
    .table =
        {
            {0, 0, 1, 1, 1, 0, 0, 0},
            {0, 0, 1, 1, 1, 1, 0, 0},
            {0, 0, 1, 1, 1, 1, 0, 0},
            {0, 1, 1, 2, 1, 1, 0, 0},
            {1, 1, 0, 2, 2, 2, 1, 0},
            {1, 1, 2, 1, 2, 2, 1, 0},
            {1, 1, 1, 1, 1, 1, 2, 2},
            {1, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 0, 0, 0},
        },
};

// INKPLATE6 (classic): PCAL6416A external expander at 0x22, onboard touchpad (driver not
// yet ported -- Phase 11), 4 clean-cycle reps in display1b's full update (hardcoded in C,
// same precedent as Inkplate10), 5 reps for partial update.
const board_config_t board_config_inkplate6 = {
    .name = "inkplate6",

    .width = 800,
    .height = 600,

    .data_pins = {4, 5, 18, 19, 23, 25, 26, 27},
    .data_mask = INKPLATE_DATA_MASK8(4, 5, 18, 19, 23, 25, 26, 27),

    .pin_cl = 0,
    .pin_le = 2,
    .pin_ckv = 32,
    .pin_sph = 33,

    .pin_oe = {.expander_addr = 0x20, .pin = 0},
    .pin_gmode = {.expander_addr = 0x20, .pin = 1},
    .pin_spv = {.expander_addr = 0x20, .pin = 2},

    .pmic_i2c_addr = 0x48,

    .waveform = &wave_3b_inkplate6,

    .partial_reps = 5,

    .has_touch = 0,
    .has_frontlight = 0,
};

// INKPLATE6V2: PCAL6416A external expander at 0x21, no touchpad, adds SD P-MOS gpio
// control (handled in board-level Python/driver code, not this struct). 5 clean-cycle
// reps in display1b's full update, 6 for partial.
const board_config_t board_config_inkplate6v2 = {
    .name = "inkplate6v2",

    .width = 800,
    .height = 600,

    .data_pins = {4, 5, 18, 19, 23, 25, 26, 27},
    .data_mask = INKPLATE_DATA_MASK8(4, 5, 18, 19, 23, 25, 26, 27),

    .pin_cl = 0,
    .pin_le = 2,
    .pin_ckv = 32,
    .pin_sph = 33,

    .pin_oe = {.expander_addr = 0x20, .pin = 0},
    .pin_gmode = {.expander_addr = 0x20, .pin = 1},
    .pin_spv = {.expander_addr = 0x20, .pin = 2},

    .pmic_i2c_addr = 0x48,

    .waveform = &wave_3b_inkplate6,

    .partial_reps = 6,

    .has_touch = 0,
    .has_frontlight = 0,
};

// Real 3-bit/8-level waveform for Inkplate5V2, transcribed from the Arduino reference
// driver's waveforms.h WAVEFORM3BIT macro -- declared as waveform3Bit[color][phase]
// (8 colors x 9 phases), transposed here to [phase][color] to match this struct's
// row-per-phase convention (same as step 15/22 did for Inkplate10/Inkplate6).
static const waveform_table_t wave_3b_inkplate5v2 = {
    .levels = 8,
    .phases = 9,
    .table =
        {
            {0, 1, 0, 0, 1, 0, 1, 0},
            {0, 1, 1, 0, 2, 1, 1, 0},
            {1, 2, 2, 1, 1, 1, 1, 0},
            {1, 2, 2, 1, 2, 1, 2, 0},
            {2, 1, 1, 1, 1, 2, 2, 0},
            {1, 2, 1, 1, 1, 0, 2, 0},
            {1, 1, 2, 1, 1, 1, 1, 0},
            {1, 1, 1, 2, 2, 2, 2, 0},
            {0, 0, 0, 0, 0, 0, 0, 0},
        },
};

// INKPLATE5V2 (1280x720): single PCAL6416A expander @ 0x20 (IO_INT_ADDR in the Arduino
// reference's pins.h) handles OE/GMODE/SPV plus TPS_*/VBAT_EN/SD_ENABLE lines -- unlike
// INKPLATE6/6V2 there's no separate external expander. No touch, no frontlight. 4 reps
// per frame in partial update (Arduino Inkplate5V2Driver.cpp's partialUpdate() for(k<4)
// loop -- distinct from the burn-in clean()-cycle rep count, which lives in the board's
// Python driver, not this struct, same as Inkplate6's precedent).
const board_config_t board_config_inkplate5v2 = {
    .name = "inkplate5v2",

    .width = 1280,
    .height = 720,

    .data_pins = {4, 5, 18, 19, 23, 25, 26, 27},
    .data_mask = INKPLATE_DATA_MASK8(4, 5, 18, 19, 23, 25, 26, 27),

    .pin_cl = 0,
    .pin_le = 2,
    .pin_ckv = 32,
    .pin_sph = 33,

    .pin_oe = {.expander_addr = 0x20, .pin = 0},
    .pin_gmode = {.expander_addr = 0x20, .pin = 1},
    .pin_spv = {.expander_addr = 0x20, .pin = 2},

    .pmic_i2c_addr = 0x48,

    .waveform = &wave_3b_inkplate5v2,

    .partial_reps = 4,

    .has_touch = 0,
    .has_frontlight = 0,
};

// Real 3-bit/8-level waveform for Inkplate6FLICK, transcribed from the Arduino reference
// driver's Inkplate6FLICK.h WAVEFORM3BIT macro -- declared as waveform3Bit[color][phase]
// (8 colors x 9 phases), transposed here to [phase][color] to match this struct's
// row-per-phase convention (same as prior boards).
static const waveform_table_t wave_3b_inkplate6flick = {
    .levels = 8,
    .phases = 9,
    .table =
        {
            {0, 0, 0, 1, 1, 0, 1, 0},
            {0, 0, 1, 1, 1, 1, 2, 0},
            {0, 1, 1, 1, 1, 1, 1, 0},
            {0, 2, 2, 2, 2, 2, 1, 0},
            {0, 1, 1, 2, 1, 1, 2, 0},
            {1, 1, 1, 1, 2, 2, 2, 0},
            {1, 2, 1, 1, 1, 1, 1, 0},
            {1, 1, 2, 2, 2, 2, 2, 2},
            {0, 0, 0, 0, 0, 0, 0, 0},
        },
};

// INKPLATE6FLICK (1024x758): PCAL6416A expander @ 0x20 handles OE/GMODE/SPV plus
// WAKEUP/PWRUP/VCOM (Inkplate6FLICKDriver's pins.h), second expander @ 0x21 reserved for
// SD/touchscreen -- not wired here, touch/frontlight explicitly deferred to Phase 11
// (docs/REFACTOR-PLAN.md step 24). PMIC addr assumed 0x48 (TPS65186 default, not given in
// pins.h, same as every other board). 5 reps/frame in partialUpdate()'s for(k<5) loop.
// Mono display1b() uses 4 black-push phases (not the usual 5) followed by its own
// discharge pass -- see waveform.c's inkplate_gen_mono_wave and inkplatemodule.c's
// inkplate_mono_display board check.
const board_config_t board_config_inkplate6flick = {
    .name = "inkplate6flick",

    .width = 1024,
    .height = 758,

    .data_pins = {4, 5, 18, 19, 23, 25, 26, 27},
    .data_mask = INKPLATE_DATA_MASK8(4, 5, 18, 19, 23, 25, 26, 27),

    .pin_cl = 0,
    .pin_le = 2,
    .pin_ckv = 32,
    .pin_sph = 33,

    .pin_oe = {.expander_addr = 0x20, .pin = 0},
    .pin_gmode = {.expander_addr = 0x20, .pin = 1},
    .pin_spv = {.expander_addr = 0x20, .pin = 2},

    .pmic_i2c_addr = 0x48,

    .waveform = &wave_3b_inkplate6flick,

    .partial_reps = 5,

    .has_touch = 0,
    .has_frontlight = 0,
};

// Real 3-bit/8-level waveform for Inkplate6PLUS(V2), transcribed from the Arduino
// reference driver's WAVEFORM3BIT macro -- declared as waveform3Bit[color][phase] (8
// colors x 9 phases), transposed here to [phase][color] to match this struct's
// row-per-phase convention (same as prior boards), via an independent python3 transpose
// script (same process as step 22/23/24).
static const waveform_table_t wave_3b_inkplate6plusv2 = {
    .levels = 8,
    .phases = 9,
    .table =
        {
            {0, 0, 0, 0, 0, 0, 0, 0},
            {0, 0, 2, 0, 0, 0, 0, 0},
            {0, 2, 2, 2, 0, 2, 2, 0},
            {0, 1, 2, 2, 0, 1, 2, 0},
            {0, 1, 1, 2, 2, 2, 2, 2},
            {2, 1, 1, 1, 2, 1, 1, 2},
            {1, 2, 2, 2, 2, 1, 1, 2},
            {1, 1, 1, 1, 1, 2, 2, 2},
            {0, 0, 0, 0, 0, 0, 0, 0},
        },
};

// INKPLATE6PLUS -- V2 revision only (this pass doesn't wire the classic/non-V2 board):
// same 1024x758 panel as Inkplate6FLICK (confirmed against the pasted Arduino reference
// driver's pins.h), same PCAL6416A expander @ 0x20 for OE/GMODE/SPV. The Arduino pins.h's
// IO_EXT_ADDR differs between revisions (0x22 classic INKPLATE6PLUS, 0x21 V2) but that
// address is only used for touch, which isn't part of this struct and stays out of
// scope this pass (deferred, same precedent as Inkplate6FLICK's second expander).
// PMIC addr assumed 0x48 (TPS65186 default, not given in the pasted pins.h, same
// assumption already made for every other board here). 5 reps/frame in
// partialUpdate()'s for(k<5) loop. Mono display1b() loops for(k<4) like Inkplate6FLICK,
// but HIL testing showed its phase *roles* are reversed from every other wired board
// (repeated phases push white/skip black, one final phase pushes black/skip white) --
// root-caused by decoding this board's own GraphicsDefs.h LUTW/LUTB against its
// ~dram/dram indexing scheme, after the naive black_phases=4 mapping (copying
// inkplate_gen_mono_wave's scheme) produced a uniformly dark/washed panel on real
// hardware. Handled via inkplatemodule.c's inkplate_mono_display special-casing this
// board onto inkplate_gen_mono_wave_white_first (waveform.c) instead. GS3 display3b() is
// the standard for(k<9) loop, no special-casing needed. Display-path only (mono/GS3/
// partial/clean) -- VCOM/
// EEPROM, SD, battery/temperature, touch and frontlight are all out of scope this pass.
const board_config_t board_config_inkplate6plusv2 = {
    .name = "inkplate6plusv2",

    .width = 1024,
    .height = 758,

    .data_pins = {4, 5, 18, 19, 23, 25, 26, 27},
    .data_mask = INKPLATE_DATA_MASK8(4, 5, 18, 19, 23, 25, 26, 27),

    .pin_cl = 0,
    .pin_le = 2,
    .pin_ckv = 32,
    .pin_sph = 33,

    .pin_oe = {.expander_addr = 0x20, .pin = 0},
    .pin_gmode = {.expander_addr = 0x20, .pin = 1},
    .pin_spv = {.expander_addr = 0x20, .pin = 2},

    .pmic_i2c_addr = 0x48,

    .waveform = &wave_3b_inkplate6plusv2,

    .partial_reps = 5,

    .has_touch = 0,
    .has_frontlight = 0,
};
