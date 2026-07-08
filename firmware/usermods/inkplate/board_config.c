#include "board_config.h"

// WAVE_2B from boards/inkplate10/inkplateGS.py, 4-level grayscale.
// Order per phase row: blk, dk-grey, light-grey, white (pixel values 0-3).
static const waveform_table_t wave_2b_inkplate10 = {
    .levels = 4,
    .phases = 8,
    .table =
        {
            {0, 1, 0, 0},
            {0, 2, 0, 0},
            {0, 2, 0, 2},
            {0, 1, 2, 2},
            {0, 2, 1, 2},
            {0, 2, 1, 2},
            {1, 1, 2, 2},
            {0, 0, 0, 0},
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

    .waveform = &wave_2b_inkplate10,

    .has_touch = 0,
    .has_frontlight = 0,
};
