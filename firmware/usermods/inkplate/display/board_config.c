/**
 * @file board_config.c
 * @brief Board configuration data for every supported classic-ESP32 parallel-bus board.
 */
#include "board_config.h"

// Shared pin/expander layout for every classic-ESP32 parallel-bus board in this file --
// data bus, CL/LE/CKV/SPH GPIOs, OE/GMODE/SPV expander pins (all @ 0x20), and PMIC addr
// are identical across all 8 variants. Only name/width/height/waveform/partial_reps/
// has_touch/has_frontlight differ per board; a board whose layout genuinely diverges
// should stop using this macro and spell its fields out explicitly instead of forcing a
// fork of it.
#define INKPLATE_CLASSIC_PINS                                                                    \
    .data_pins = {4, 5, 18, 19, 23, 25, 26, 27},                                                 \
    .data_mask = INKPLATE_DATA_MASK8(4, 5, 18, 19, 23, 25, 26, 27), .pin_cl = 0, .pin_le = 2,    \
    .pin_ckv = 32, .pin_sph = 33, .pin_oe = {.expander_addr = 0x20, .pin = 0},                   \
    .pin_gmode = {.expander_addr = 0x20, .pin = 1},                                              \
    .pin_spv = {.expander_addr = 0x20, .pin = 2}, .pmic_i2c_addr = 0x48

// 3-bit/8-level waveform for Inkplate10 -- the fallback used whenever no per-device
// EEPROM calibration is present. Transposed from a [color][phase] source layout to this
// struct's [phase][color] row-per-phase convention. Values are 2-bit drive op-codes
// (0=discharge,1=black,2=white,3=skip), NOT gray levels.
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

// INKPLATE10 (classic v1): MCP23017 internal expander @ 0x20 (V2 uses PCAL6416A there
// instead), MCP23017 external expander @ 0x22 (V2's is @ 0x21). Onboard touchpad is a
// pure GPIO read via the internal expander (boards/inkplate10/inkplate10.py
// TOUCH1/2/3), no C-side hook needed. OE/GMODE/SPV/WAKEUP/PWRUP/VCOM pin numbers are
// identical between variants, so only name/has_touch differ here; partial_reps is 5
// for both.
const board_config_t board_config_inkplate10v1 = {
    .name = "inkplate10v1",

    .width = 1200,
    .height = 825,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate10,

    .partial_reps = 5,

    .has_touch = 1,
    .has_frontlight = 0,
};

// INKPLATE10V2: PCAL6416A external expander @ 0x21, no touchpad -- those same expander
// pins (10/11/12) are repurposed for SD_ENABLE in the Python driver instead. Otherwise
// identical to classic INKPLATE10 above.
const board_config_t board_config_inkplate10v2 = {
    .name = "inkplate10v2",

    .width = 1200,
    .height = 825,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate10,

    .partial_reps = 5,

    .has_touch = 0,
    .has_frontlight = 0,
};

// 3-bit/8-level waveform shared by INKPLATE6 and INKPLATE6V2 (identical for both
// variants). Transposed from a [color][phase] source layout to this struct's
// [phase][color] row-per-phase convention.
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

// INKPLATE6 (classic): MCP23017 internal expander @ 0x20 (V2 uses PCAL6416A there
// instead), MCP23017 external expander @ 0x22. Onboard touchpad is a pure GPIO read via
// the internal expander (boards/inkplate6/inkplate6.py TOUCH1/2/3), no C-side hook
// needed. 4 clean-cycle reps in display1b's full update (hardcoded), 5 reps for partial
// update.
const board_config_t board_config_inkplate6v1 = {
    .name = "inkplate6v1",

    .width = 800,
    .height = 600,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate6,

    .partial_reps = 5,

    .has_touch = 1,
    .has_frontlight = 0,
};

// INKPLATE6V2: PCAL6416A external expander at 0x21, no touchpad, adds SD P-MOS gpio
// control (handled in board-level Python/driver code, not this struct). 5 clean-cycle
// reps in display1b's full update, 6 for partial.
const board_config_t board_config_inkplate6v2 = {
    .name = "inkplate6v2",

    .width = 800,
    .height = 600,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate6,

    .partial_reps = 6,

    .has_touch = 0,
    .has_frontlight = 0,
};

// 3-bit/8-level waveform for classic Inkplate5 (non-V2). Transposed from a
// [color][phase] source layout to this struct's [phase][color] row-per-phase
// convention (cross-checked against wave_3b_inkplate5v2 below using the same method on
// its own known-good source table before applying it here).
static const waveform_table_t wave_3b_inkplate5v1 = {
    .levels = 8,
    .phases = 9,
    .table =
        {
            {0, 0, 1, 1, 0, 0, 1, 0},
            {0, 1, 2, 1, 1, 0, 1, 0},
            {1, 1, 2, 1, 1, 0, 1, 0},
            {1, 1, 0, 2, 1, 1, 2, 0},
            {0, 1, 2, 0, 2, 1, 0, 0},
            {1, 2, 1, 1, 0, 2, 2, 0},
            {1, 0, 1, 1, 1, 1, 1, 0},
            {1, 1, 1, 2, 2, 2, 2, 0},
            {0, 0, 0, 0, 0, 0, 0, 0},
        },
};

// INKPLATE5 (classic, 960x540): same single-PCAL6416A-expander layout as INKPLATE5V2
// (confirmed same chip, no separate external expander -- unlike INKPLATE6/6V2 there's
// no free expander-chip signal to auto-detect the variant by). Pin numbers assumed
// identical to INKPLATE5V2 (same macro names used in both boards' upstream Arduino
// headers) -- NOT yet HIL-confirmed on real v1 hardware. partial_reps=6 matches
// upstream Arduino's partialUpdate() for(k<6) loop (vs V2's for(k<4), already reflected
// in board_config_inkplate5v2.partial_reps=4 below). Mono display1b() uses the default
// 5 black-push phases (see inkplatemodule.c's inkplate_mono_display) -- matches
// upstream Arduino's for(k<5), no special-casing needed. gfx_set_mirror_x for this
// variant is set to False in boards/inkplate5/inkplate5.py -- UNCONFIRMED on real
// hardware, provisional based on the mirrored-text symptom seen running the V2 board
// config on v1 hardware; verify on real panel before trusting non-mirrored output.
const board_config_t board_config_inkplate5v1 = {
    .name = "inkplate5v1",

    .width = 960,
    .height = 540,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate5v1,

    .partial_reps = 6,

    .has_touch = 0,
    .has_frontlight = 0,
};

// 3-bit/8-level waveform for Inkplate5V2. Transposed from a [color][phase] source
// layout to this struct's [phase][color] row-per-phase convention.
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

// INKPLATE5V2 (1280x720): single PCAL6416A expander @ 0x20 handles OE/GMODE/SPV plus
// TPS_*/VBAT_EN/SD_ENABLE lines -- unlike INKPLATE6/6V2 there's no separate external
// expander. No touch, no frontlight. 4 reps per frame in partial update, distinct from
// the burn-in clean()-cycle rep count, which lives in the board's Python driver, not
// this struct.
const board_config_t board_config_inkplate5v2 = {
    .name = "inkplate5v2",

    .width = 1280,
    .height = 720,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate5v2,

    .partial_reps = 4,

    .has_touch = 0,
    .has_frontlight = 0,
};

// 3-bit/8-level waveform for Inkplate6FLICK. Transposed from a [color][phase] source
// layout to this struct's [phase][color] row-per-phase convention.
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
// WAKEUP/PWRUP/VCOM, SD_PMOS_PIN (SD power MOSFET, pin 13), and most touchscreen lines
// (EN=pin 12, RST=pin 10, IO_EXPANDER on this same 0x20 expander); only TOUCHSCREEN_INT
// is a direct ESP32 GPIO (36). SD is wired (boards/inkplate6flick/inkplate6_flick.py
// init_sd_card/sd_card_sleep/sd_card_wake). Touch/frontlight remain unwired; the second
// expander @ 0x21's purpose is unconfirmed -- SD and touchscreen both live on the
// internal expander instead. PMIC addr assumed 0x48 (TPS65186 default, not otherwise
// specified). 5 reps/frame in partial update.
// Mono display1b() uses 4 black-push phases (not the usual 5) followed by its own
// discharge pass -- see waveform.c's inkplate_gen_mono_wave and inkplatemodule.c's
// inkplate_mono_display board check.
const board_config_t board_config_inkplate6flick = {
    .name = "inkplate6flick",

    .width = 1024,
    .height = 758,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate6flick,

    .partial_reps = 5,

    .has_touch = 0,
    .has_frontlight = 0,
};

// 3-bit/8-level waveform for Inkplate6PLUS(V2). Transposed from a [color][phase] source
// layout to this struct's [phase][color] row-per-phase convention.
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

// INKPLATE6PLUS -- V2 revision only; the classic/non-V2 board isn't wired. Same
// 1024x758 panel as Inkplate6FLICK, same PCAL6416A expander @ 0x20 for OE/GMODE/SPV.
// IO_EXT_ADDR differs between revisions (0x22 classic, 0x21 V2), but that address is
// only used for touch, which isn't wired here. PMIC addr assumed 0x48 (TPS65186
// default, not otherwise specified). 5 reps/frame in partial update. Mono display1b()
// loops 4 times like Inkplate6FLICK, but its phase *roles* are reversed from every
// other wired board (repeated phases push white/skip black, one final phase pushes
// black/skip white) -- root-caused by decoding this board's own LUTW/LUTB tables
// against its dram indexing scheme; the naive black_phases=4 mapping (copying
// inkplate_gen_mono_wave's scheme) produced a uniformly dark/washed panel on real
// hardware. Handled via inkplatemodule.c's inkplate_mono_display special-casing this
// board onto inkplate_gen_mono_wave_white_first (waveform.c) instead. GS3 display3b()
// is the standard for(k<9) loop, no special-casing needed. Display-path only (mono/GS3/
// partial/clean) -- VCOM/EEPROM, SD, battery/temperature, touch and frontlight are not
// wired.
const board_config_t board_config_inkplate6plusv2 = {
    .name = "inkplate6plusv2",

    .width = 1024,
    .height = 758,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate6plusv2,

    .partial_reps = 5,

    .has_touch = 0,
    .has_frontlight = 0,
};

// 3-bit/8-level waveform for Inkplate4TEMPERA. Phase 0 and phase 8 are both all-zero
// (discharge/park) rows, transposed from a [color][phase] source layout to this
// struct's [phase][color] convention. display3b()'s hardware push loop is for(k<8) --
// one short of this table's 9 rows -- but phase 8 is all-zero (no-op/discharge for
// every gray level), so pushing it as a harmless extra pass keeps .phases=9 consistent
// with every other board's convention instead of a one-off .phases=8.
static const waveform_table_t wave_3b_inkplate4tempera = {
    .levels = 8,
    .phases = 9,
    .table =
        {
            {0, 0, 0, 0, 0, 0, 0, 0},
            {0, 1, 2, 0, 2, 1, 1, 0},
            {0, 1, 1, 0, 1, 2, 1, 0},
            {1, 1, 1, 0, 1, 1, 1, 0},
            {1, 2, 0, 1, 2, 1, 2, 0},
            {1, 1, 2, 1, 1, 2, 1, 0},
            {1, 1, 1, 1, 1, 1, 2, 2},
            {1, 0, 1, 2, 2, 2, 2, 2},
            {0, 0, 0, 0, 0, 0, 0, 0},
        },
};

// INKPLATE4TEMPERA (600x600, first square panel wired): same classic-ESP32 parallel-bus
// pin/expander layout as every other board. PMIC addr assumed 0x48 (not otherwise
// specified). display1b() uses 10 black-push phases (not the usual 5) -- this board's
// own LUTB/LUT2 tables are byte-for-byte identical to inkplate_gen_mono_wave's standard
// op_blk/op_bw output, so it's the standard scheme run 10 times, not a reversed-role
// variant like Inkplate6PLUSV2. See inkplatemodule.c's inkplate_mono_display board
// check. display3b() loops for(k<8); waveform.phases=9 (see above) pushes one harmless
// extra all-zero phase for consistency with every other board. partialUpdate() loops
// for(k<9) -> partial_reps=9. SD_PMOS_PIN sits on the internal expander (pin 11), same
// P-MOS-gated pattern as Inkplate6/6FLICK/6PLUSV2; SPI pins (miso=12/mosi=13/sck=14/
// cs=15) match those boards' numbers exactly. Touch/frontlight/battery/BME688/APDS9960/
// accelerometer/buzzer/VCOM-EEPROM are not wired.
const board_config_t board_config_inkplate4tempera = {
    .name = "inkplate4tempera",

    .width = 600,
    .height = 600,

    INKPLATE_CLASSIC_PINS,

    .waveform = &wave_3b_inkplate4tempera,

    .partial_reps = 9,

    .has_touch = 0,
    .has_frontlight = 0,
};
