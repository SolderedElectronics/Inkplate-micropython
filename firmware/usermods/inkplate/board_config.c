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

// INKPLATE10 (classic v1): MCP23017 internal expander @ 0x20 (V2 uses PCAL6416A there
// instead), MCP23017 external expander @ 0x22 (V2's is @ 0x21), onboard touchpad wired
// (boards/inkplate10/inkplate10.py TOUCH1/2/3 -- pure GPIO read via the internal
// expander, no C-side hook needed, same precedent as Inkplate6 classic). Real Arduino
// reference driver's pins.h: IO_INT_ADDR=0x20 both variants, IO_EXT_ADDR differs
// (0x21 V2, 0x22 classic) -- same split as Inkplate6/6V2. OE/GMODE/SPV/WAKEUP/PWRUP/VCOM
// pin numbers are identical between variants (no #ifdef branch touches them), so only
// name/has_touch differ here; partial_reps stays 5 for both (partialUpdate()/display1b()
// both hardcode _repeat=5 unconditionally in the real driver, no per-variant branch).
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

    .has_touch = 1,
    .has_frontlight = 0,
};

// INKPLATE10V2: PCAL6416A external expander @ 0x21, no touchpad (same expander pins
// 10/11/12 repurposed for SD_ENABLE in the Python driver instead, same precedent as
// Inkplate6V2). Otherwise identical to classic INKPLATE10 above.
const board_config_t board_config_inkplate10v2 = {
    .name = "inkplate10v2",

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

// INKPLATE6 (classic): MCP23017 internal expander @ 0x20 (V2 uses PCAL6416A there
// instead), MCP23017 external expander @ 0x22, onboard touchpad wired
// (boards/inkplate6/inkplate6.py TOUCH1/2/3 -- pure GPIO read via the internal expander,
// no C-side hook needed), 4 clean-cycle reps in display1b's full update (hardcoded in C,
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
// WAKEUP/PWRUP/VCOM (Inkplate6FLICKDriver's pins.h) -- and, per the real pins.h, also
// SD_PMOS_PIN (SD power MOSFET, pin 13) and most touchscreen lines (EN=pin 12, RST=pin
// 10, IO_EXPANDER=IO_INT_ADDR i.e. this same 0x20 expander; only TOUCHSCREEN_INT is a
// direct ESP32 GPIO, 36). SD is wired (boards/inkplate6flick/inkplate6_flick.py
// init_sd_card/sd_card_sleep/sd_card_wake). Touch/frontlight still explicitly deferred to
// Phase 11 (docs/REFACTOR-PLAN.md step 24); the second expander @ 0x21's actual purpose
// is still unconfirmed (not SD/touchscreen as previously assumed here -- those turned out
// to live on the internal expander instead). PMIC addr assumed 0x48 (TPS65186 default,
// not given in pins.h, same as every other board). 5 reps/frame in partialUpdate()'s
// for(k<5) loop.
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

// Real 3-bit/8-level waveform for Inkplate4TEMPERA, transcribed from the Arduino reference
// driver's waveforms.h WAVEFORM3BIT macro (user-supplied full 9-column version,
// superseding an earlier 8-column paste that turned out truncated). Standard bookend
// pattern like every other wired board: phase 0 and phase 8 are both all-zero
// (discharge/park) rows, transposed from waveform3Bit[color][phase] to this struct's
// [phase][color] convention. display3b()'s hardware push loop is for(k<8) -- one short
// of this table's 9 rows -- but phase 8 is all-zero (no-op/discharge for every gray
// level), so pushing it as a harmless extra pass keeps .phases=9 consistent with every
// other board's convention instead of a one-off .phases=8.
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
// pin/expander layout as every other board (PCAL6416A @ 0x20 for OE/GMODE/SPV, TPS65186
// assumed @ 0x48 -- not given in the pasted pins.h, same assumption made for every prior
// board). display1b() uses 10 black-push phases (not the usual 5) -- confirmed NOT a
// copy-paste artifact: this board's own GraphicsDefs.h LUTB/LUT2 arrays are byte-for-byte
// identical to inkplate_gen_mono_wave's standard op_blk/op_bw output (same bytes as
// test_waveform.c's expected_blk/expected_bw), so it's the standard scheme run 10 times,
// not a reversed-role variant like Inkplate6PLUSV2. See inkplatemodule.c's
// inkplate_mono_display board check. display3b() loops for(k<8); waveform.phases=9 (see
// above) pushes one harmless extra all-zero phase for consistency with every other
// board. partialUpdate() loops for(k<9) -> partial_reps=9. SD wired this pass (user
// request): SD_PMOS_PIN on the internal expander (pin 11), same P-MOS-gated pattern as
// Inkplate6/6FLICK/6PLUSV2, SPI pins (miso=12/mosi=13/sck=14/cs=15) match those boards'
// own already-verified numbers exactly. Touch/frontlight/battery/BME688/APDS9960/
// accelerometer/buzzer/VCOM-EEPROM out of scope this pass, same precedent as
// Inkplate6FLICK/6PLUSV2's first pass (docs/REFACTOR-PLAN.md Phase 8 step 26).
const board_config_t board_config_inkplate4tempera = {
    .name = "inkplate4tempera",

    .width = 600,
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

    .waveform = &wave_3b_inkplate4tempera,

    .partial_reps = 9,

    .has_touch = 0,
    .has_frontlight = 0,
};
