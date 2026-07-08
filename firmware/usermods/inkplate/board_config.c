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

    .has_touch = 0,
    .has_frontlight = 0,
};
