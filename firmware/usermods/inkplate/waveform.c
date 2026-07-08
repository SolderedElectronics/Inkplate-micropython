#include "waveform.h"
#include <string.h>

void inkplate_gen_nibble_lut(const uint8_t *op, int bpp, uint8_t out[16])
{
    int pixels_per_nibble = 4 / bpp;
    uint8_t pixel_mask = (uint8_t)((1 << bpp) - 1);

    for (int nibble = 0; nibble < 16; nibble++) {
        uint8_t code_byte = 0;
        for (int p = 0; p < pixels_per_nibble; p++) {
            uint8_t pixel_val = (uint8_t)((nibble >> (p * bpp)) & pixel_mask);
            code_byte |= (uint8_t)(op[pixel_val] << (2 * p));
        }
        out[nibble] = code_byte;
    }
}

void inkplate_gen_wave_3bit(const uint8_t *table, int row_stride, uint8_t phases,
                            uint8_t out[][16])
{
    for (uint8_t phase = 0; phase < phases; phase++) {
        // inkplate_gen_nibble_lut(bpp=4) indexes op[] with a full nibble (0-15), but only
        // levels 0-7 are real gray levels -- pad the rest so the lookup stays in-bounds.
        uint8_t op[16] = {0};
        memcpy(op, &table[phase * row_stride], 8);
        inkplate_gen_nibble_lut(op, 4, out[phase]);
    }
}

void inkplate_gen_mono_wave(uint8_t out[INKPLATE_MONO_WAVE_PHASES][16])
{
    static const uint8_t op_blk[2] = {3, 1}; // white(0)->skip, black(1)->discharge/black
    static const uint8_t op_bw[2] = {2, 1};  // white(0)->white, black(1)->black

    for (int phase = 0; phase < INKPLATE_MONO_WAVE_PHASES - 1; phase++) {
        inkplate_gen_nibble_lut(op_blk, 1, out[phase]);
    }
    inkplate_gen_nibble_lut(op_bw, 1, out[INKPLATE_MONO_WAVE_PHASES - 1]);
}
